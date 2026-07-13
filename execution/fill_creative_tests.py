#!/usr/bin/env python3
"""
fill_creative_tests.py
Fills Column A (TC group label) and performance metrics (Hook, Body75, CPM, CTR,
CPC, Gasto, Vendas, CPA, Initiate Checkout) of the '032026' sheet conditionally
based on User Column M (Status).

Logic:
1. Fetches USD->BRL quote from AwesomeAPI.
2. Fetches ALL campaigns directly via /campaigns to parse out names and TCs.
3. Reads each Excel test row, parses its specific 'Início' date (Col C / Col P).
4. Fetches targeted /insights and /report (RedTrack) dynamically for that exact date range.
5. Col A Logic: Fills Col A if blank and not already merged.
6. Metrics Logic: Fills financial and performance columns ONLY if Col M contains 'TESTE'.
"""

import re
import sys
import os
import requests
import datetime
import time
import gspread

MAIN_SHEET = "032026"
DATA_START_ROW = 4

DEFAULT_FB_TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facebook_redtrack_importer_v2 import FacebookAdsAPI

def parse_campaign_name(campaign_name: str):
    if not campaign_name: return None
    tc_match = re.search(r'TC(\d+)', campaign_name, re.IGNORECASE)
    if not tc_match: return None
    tc_label = f"TC{tc_match.group(1)}"
    bracket_match = re.search(r'\]([^[]*?)TC\d+', campaign_name, re.IGNORECASE)
    account_name = bracket_match.group(1).strip() if bracket_match else ""
    return tc_label, account_name

def extract_ad_name_from_campaign(campaign_name: str) -> str:
    if not campaign_name: return ""
    
    # Priority 1: Ad name in brackets, e.g. [LT899.43]
    import re
    bracket_match = re.search(r'\[(LT\d+(?:\.\d+)?|TC\d+(?:\.\d+)?)\]', campaign_name, re.IGNORECASE)
    if bracket_match:
        return bracket_match.group(1).strip()
    
    # Priority 2: Find LT/BT pattern after ABO/CBO section
    # Matches: "... ABO - 1 - 50 - 1 - LT1207 - 24/03/26"
    lt_after_abo = re.search(r'(?:ABO|CBO)\b.*?-\s*((?:LT|BT)\d+(?:\.\d+)?)\s*(?:\s*-|$)', campaign_name, re.IGNORECASE)
    if lt_after_abo:
        return lt_after_abo.group(1).strip()
    
    # Priority 3: Fallback - find any standalone LT/BT pattern (last one in string)
    all_lt = re.findall(r'\b((?:LT|BT)\d+(?:\.\d+)?)\b', campaign_name, re.IGNORECASE)
    if all_lt:
        return all_lt[-1].strip()
    
    # Priority 4: Original ABO/CBO parsing
    match = re.search(r'(?:ABO|CBO)\s+\S+\s*-\s*(.+)$', campaign_name, re.IGNORECASE)
    if match: return match.group(1).strip()
    
    # Priority 5: rsplit fallback
    parts = campaign_name.rsplit(' - ', 1)
    if len(parts) == 2: return parts[1].strip()
    return ""

def build_col_a_label(campaign_name: str) -> str:
    result = parse_campaign_name(campaign_name)
    if not result: return ""
    return f"{result[0]} {result[1]}".strip()

def parse_excel_date(cell_value, default_date: str) -> str:
    """Safely parse Excel datetime objects or strings to YYYY-MM-DD"""
    if not cell_value:
        return default_date
    if isinstance(cell_value, datetime.datetime):
        return cell_value.strftime("%Y-%m-%d")
    if isinstance(cell_value, str):
        # Handle 'dd/mm/yyyy' typical in BR Excel
        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', cell_value)
        if match:
            return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
        # Handle 'dd/mm/yy'
        match_short = re.search(r'(\d{2})/(\d{2})/(\d{2})', cell_value)
        if match_short:
            return f"20{match_short.group(3)}-{match_short.group(2)}-{match_short.group(1)}"
    return default_date

def derive_auto_date_start(all_values, data_start, fallback):
    """Oldest 'Início' among rows still in TESTE, read from the sheet itself.

    Scans Col C (TESTES section, status in Col M) and Col P (PRÉ-ESCALA
    section, status in Col V). Returns the earliest date as YYYY-MM-DD, or
    `fallback` when no TESTE row has a parseable date. This makes the fill
    independent of the date the user picked in the UI — an old still-running
    test is never cut off by a late date_start.
    """
    dates = []
    for i in range(data_start - 1, len(all_values)):
        row = all_values[i]
        # TESTES section: Col B name + Col M status -> date in Col C
        name = row[1] if len(row) > 1 else ""
        status = row[12] if len(row) > 12 else ""
        if name and str(name).strip() and "TESTE" in str(status).strip().upper():
            d = parse_excel_date(row[2] if len(row) > 2 else "", "")
            if d:
                dates.append(d)
        # PRÉ-ESCALA section: Col O name + Col V status -> date in Col P
        name_pe = row[14] if len(row) > 14 else ""
        status_pe = row[21] if len(row) > 21 else ""
        if name_pe and str(name_pe).strip() and "TESTE" in str(status_pe).strip().upper():
            d = parse_excel_date(row[15] if len(row) > 15 else "", "")
            if d:
                dates.append(d)
    return min(dates) if dates else fallback  # YYYY-MM-DD sorts lexicographically

def _parse_ad_insight_row(row):
    """Convert one FB ad-level insight row into our metric dict."""
    imps = float(row.get("impressions", 0) or 0)
    # Hook Rate (3s video views / impressions)
    video_3s_views = 0
    for act in row.get('actions', []) or []:
        if act.get('action_type') == 'video_view':
            video_3s_views = float(act.get('value', 0) or 0)
            break
    # Body/Hold Rate (75% watched / impressions)
    p75_actions = row.get('video_p75_watched_actions', []) or []
    p75 = float(p75_actions[0].get('value', 0) or 0) if p75_actions else 0
    return {
        "ad_id": row.get("ad_id", ""),
        "ad_name": row.get("ad_name", ""),
        "campaign_id": row.get("campaign_id", ""),
        "campaign_name": row.get("campaign_name", ""),
        "spend": float(row.get("spend", 0.0) or 0.0),
        "cpm": float(row.get("cpm", 0.0) or 0.0),
        "cpc": float(row.get("cpc", 0.0) or 0.0),
        "ctr": (float(row.get("ctr", 0.0) or 0.0) / 100),
        "hook_rate": (video_3s_views / imps) if imps > 0 else 0,
        "body_rate": (p75 / imps) if imps > 0 else 0,
        "impressions": imps,
    }

class _FBTooMuchData(Exception):
    """FB error code 1: 'Please reduce the amount of data you're asking for'."""
    pass

_INSIGHTS_FIELDS = 'ad_id,ad_name,campaign_id,campaign_name,impressions,cpc,cpm,ctr,spend,actions,video_p75_watched_actions'

def _sweep_account_insights(acc_raw, since, until, fb_token, limit, progress_callback=None):
    """One paginated ad-level insights sweep for one account and range.

    Raises _FBTooMuchData when FB refuses the window size so the caller can
    degrade (smaller pages, then split the date range).
    """
    import time
    out = []
    url = f"https://graph.facebook.com/v19.0/act_{acc_raw}/insights"
    params = {
        'access_token': fb_token,
        'fields': _INSIGHTS_FIELDS,
        'level': 'ad',
        'time_range': f'{{"since":"{since}","until":"{until}"}}',
        'limit': limit,
    }
    while url:
        success = False
        last_status = None
        last_body = None
        for retry in range(6):
            r = requests.get(url, params=params, timeout=60)
            last_status = r.status_code
            last_body = r.text[:500]
            if r.status_code == 200:
                success = True
                break
            err = {}
            try:
                err = r.json().get("error", {}) or {}
            except Exception:
                pass
            if "reduce the amount of data" in str(err.get("message", "")).lower():
                raise _FBTooMuchData(f"conta {acc_raw} {since}->{until} limit={limit}")
            if r.status_code == 429 or r.status_code >= 500 or err.get("code") in (17, 4, 32, 613) or err.get("is_transient"):
                sleep_s = min(2 ** retry, 60)
                if progress_callback:
                    progress_callback(f"⏳ FB rate limit em insights (conta {acc_raw}, status {r.status_code}). Retry {retry+1}/6 em {sleep_s}s...")
                time.sleep(sleep_s)
                continue
            break

        if not success:
            msg = f"⚠️ Falha ao puxar insights da conta {acc_raw} (status {last_status}): {last_body}"
            if progress_callback: progress_callback(msg)
            raise RuntimeError(msg)

        data = r.json()
        for row in data.get("data", []):
            out.append(_parse_ad_insight_row(row))
        url = (data.get("paging", {}) or {}).get("next")
        params = {}  # 'next' URL already carries params
    return out

def merge_insight_rows(rows):
    """Merge duplicate per-ad rows (from split date ranges) into one per ad.

    Rates are rebuilt from raw components so a split sweep equals a single
    sweep: clicks = ctr*imps, videos = hook*imps, p75 = body*imps — all exact
    inversions of how _parse_ad_insight_row derived them.
    """
    acc = {}
    order = []
    for m in rows:
        k = m.get("ad_id") or m.get("ad_name")
        if k not in acc:
            acc[k] = {
                "meta": {f: m.get(f, "") for f in ("ad_id", "ad_name", "campaign_id", "campaign_name")},
                "imps": 0.0, "spend": 0.0, "clicks": 0.0, "videos": 0.0, "p75": 0.0,
            }
            order.append(k)
        a = acc[k]
        imps = float(m.get("impressions", 0) or 0)
        a["imps"] += imps
        a["spend"] += float(m.get("spend", 0) or 0)
        a["clicks"] += float(m.get("ctr", 0) or 0) * imps
        a["videos"] += float(m.get("hook_rate", 0) or 0) * imps
        a["p75"] += float(m.get("body_rate", 0) or 0) * imps
    out = []
    for k in order:
        a = acc[k]
        imps, spend, clicks = a["imps"], a["spend"], a["clicks"]
        out.append({
            **a["meta"],
            "spend": spend,
            "impressions": imps,
            "cpm": (spend / imps * 1000) if imps > 0 else 0,
            "cpc": (spend / clicks) if clicks > 0 else 0,
            "ctr": (clicks / imps) if imps > 0 else 0,
            "hook_rate": (a["videos"] / imps) if imps > 0 else 0,
            "body_rate": (a["p75"] / imps) if imps > 0 else 0,
        })
    return out

def _fetch_account_insights_adaptive(acc_raw, since, until, fb_token, progress_callback=None, limit=250):
    """Sweep one account, degrading automatically when FB says 'too much data':
    first shrink the page size, then split the date range in half and merge."""
    try:
        return _sweep_account_insights(acc_raw, since, until, fb_token, limit, progress_callback)
    except _FBTooMuchData:
        if limit > 50:
            if progress_callback:
                progress_callback(f"⚠️ FB pediu menos dados (conta {acc_raw}). Reduzindo página para 50...")
            return _fetch_account_insights_adaptive(acc_raw, since, until, fb_token, progress_callback, limit=50)
        d0 = datetime.datetime.strptime(since, "%Y-%m-%d").date()
        d1 = datetime.datetime.strptime(until, "%Y-%m-%d").date()
        if (d1 - d0).days < 1:
            raise RuntimeError(f"⚠️ FB recusou até um único dia de insights (conta {acc_raw}, {since}). Sem como reduzir mais.")
        mid = d0 + (d1 - d0) // 2
        mid_next = mid + datetime.timedelta(days=1)
        if progress_callback:
            progress_callback(f"⚠️ Período grande demais para o FB (conta {acc_raw}). Dividindo: {since}→{mid} e {mid_next}→{until}...")
        left = _fetch_account_insights_adaptive(acc_raw, since, mid.strftime("%Y-%m-%d"), fb_token, progress_callback, limit)
        right = _fetch_account_insights_adaptive(acc_raw, mid_next.strftime("%Y-%m-%d"), until, fb_token, progress_callback, limit)
        return merge_insight_rows(left + right)

def fetch_fb_ad_insights_for_accounts(account_ids, since, until, fb_token, progress_callback=None):
    """AD-level insights for whole accounts in one paginated sweep.

    Insights only return ads that DELIVERED in [since, until], so this scales
    with the active ads (hundreds) instead of the full /ads catalog (300k+ ads,
    which took forever to page through). One sweep per distinct date range
    replaces both the catalog fetch and the per-row insight calls.

    level='ad' keeps each variation separate — campaign-level insights fed
    BM108.1/.2/.3 the same aggregate (previous bug). Big windows on big
    accounts trigger FB's 'reduce the amount of data' error; the adaptive
    fetch shrinks pages and splits the range as needed.
    """
    out = []
    for account_id in account_ids:
        acc_raw = account_id.replace("act_", "")
        out.extend(_fetch_account_insights_adaptive(acc_raw, since, until, fb_token, progress_callback))
    return out

def build_ad_index(insight_rows):
    """{ad_name_lower: [{ad_id, ad_name, campaign_id, campaign_name}]} from insight rows."""
    idx = {}
    seen = set()
    for m in insight_rows:
        name = str(m.get("ad_name", "") or "").strip()
        if not name:
            continue
        key = name.lower()
        dedupe = (key, m.get("ad_id"))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        idx.setdefault(key, []).append({
            "ad_id": m.get("ad_id"),
            "ad_name": name,
            "campaign_id": m.get("campaign_id"),
            "campaign_name": m.get("campaign_name", ""),
        })
    return idx

def select_ad_metrics(ad_rows, search_term):
    """Pick the ad matching this row's exact variation name.

    Priority: exact ad_name match, then a word-boundary 'contains' match
    (so 'BM108.1' won't match 'BM108.10'). Ties break on impressions.
    Returns the metric dict, or None if nothing matches.
    """
    st = str(search_term or "").strip().lower()
    if not st:
        return None

    exact = [m for m in ad_rows if str(m.get("ad_name", "")).strip().lower() == st]
    if exact:
        return max(exact, key=lambda m: m.get("impressions", 0))

    pattern = r'(?<![a-zA-Z0-9_])' + re.escape(st) + r'(?![a-zA-Z0-9_])'
    contains = [m for m in ad_rows if re.search(pattern, str(m.get("ad_name", "")).lower())]
    if contains:
        return max(contains, key=lambda m: m.get("impressions", 0))

    return None

def match_ads(ad_index, search_term):
    """Return the candidate FB ads for a sheet ad code.

    Exact ad-name match wins; otherwise a word-boundary match on the exact
    term, then on the base term (BM108 for BM108.1). Mirrors the campaign
    matcher's scoring so variations resolve to their own ad when present.
    """
    st = str(search_term or "").strip().lower()
    if not st:
        return []
    if st in ad_index:
        return list(ad_index[st])

    base = st.split('.')[0] if '.' in st else st
    pat_exact = r'(?<![a-zA-Z0-9_\.])' + re.escape(st) + r'(?![a-zA-Z0-9_\.])'
    pat_base = r'(?<![a-zA-Z0-9_\.])' + re.escape(base) + r'(?![a-zA-Z0-9_\.])'

    best_score = 0
    hits = []
    for key, ads in ad_index.items():
        score = 0
        if re.search(pat_exact, key):
            score = 2
        elif base != st and re.search(pat_base, key):
            score = 1
        if score > 0:
            if score > best_score:
                best_score = score
                hits = list(ads)
            elif score == best_score:
                hits.extend(ads)
    return hits

# Cache of full RedTrack /report pulls keyed by (group, since, until).
# ~100 sheet rows share a handful of date ranges, so pulling each report once
# and filtering locally replaces hundreds of identical HTTP round-trips.
_rt_report_cache = {}

def fetch_rt_report(group_name, since, until, rt_token):
    """Full RedTrack /report for one grouping+range, paginated and cached."""
    key = (group_name, since, until)
    if key in _rt_report_cache:
        return _rt_report_cache[key]

    import time
    rows = []
    page = 1
    complete = True
    while page <= 5:
        data, success = None, False
        for retry in range(4):
            try:
                r = requests.get('https://api.redtrack.io/report', params={
                    'api_key': rt_token,
                    'date_from': since,
                    'date_to': until,
                    'group': group_name,
                    'limit': 1000,
                    'page': page
                }, timeout=30)
                if r.status_code == 200:
                    data, success = r.json(), True
                    break
                elif r.status_code == 429 or r.status_code >= 500:
                    time.sleep(2 ** retry)
                    continue
                else:
                    break
            except requests.RequestException:
                time.sleep(2 ** retry)
                continue
        if not success:
            complete = False
            break
        if not data:
            break
        rows.extend(data)
        if len(data) < 1000:
            break
        page += 1

    # Only cache complete pulls — a transient failure must not poison the
    # result for every row sharing this range; the next row retries.
    if complete:
        _rt_report_cache[key] = rows
    return rows

def fetch_rt_for_ad(ad_name_lower, since, until, rt_token):
    if not rt_token or not ad_name_lower:
        return {"vendas": 0, "cost": 0.0, "roas": 0.0, "ic": 0}

    def sum_group(group_name):
        v = 0.0; c = 0.0; ro = 0.0; ic = 0.0
        for r_row in fetch_rt_report(group_name, since, until, rt_token):
            rt_val = str(r_row.get(group_name, '')).strip().lower()
            if not rt_val: continue

            is_match = False
            if rt_val == ad_name_lower:
                is_match = True
            elif rt_val == ad_name_lower.split(" - ")[0].split(" ")[0]:
                is_match = True

            if is_match:
                v += float(r_row.get('convtype2', 0))
                ic += float(r_row.get('convtype1', 0))  # Initiate Checkout (IC)
                c += float(r_row.get('cost', 0))
                roas_val = float(r_row.get('roas', 0))
                if roas_val != 0: ro = roas_val
        return v, c, ro, ic

    # Try rt_ad first (default correct setup)
    vendas, cost, roas, ic = sum_group("rt_ad")

    # Fallback to sub4 if media buyer populated the wrong parameter (ex: LT1192)
    if vendas == 0 and cost == 0:
        vendas, cost, roas, ic = sum_group("sub4")

    return {"vendas": vendas, "cost": cost, "roas": roas, "ic": ic}

def fill_creative_tests(
    account_ids: list, 
    date_start: str, 
    date_end: str, 
    g_url: str,
    sheet_name: str,
    fb_token: str = None,
    redtrack_token: str = None,
    fb_api_instance=None, 
    progress_callback=None,
    gc=None
):
    token = fb_token or DEFAULT_FB_TOKEN

    # 1. Fetch Dolar Quote
    usd_to_brl = 5.0
    try:
        r_quote = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL")
        usd_to_brl = float(r_quote.json()["USDBRL"]["ask"])
        if progress_callback: progress_callback(f"Cotação do Dólar obtida: R$ {usd_to_brl:.4f}")
    except Exception as e:
        if progress_callback: progress_callback(f"⚠️ Erro ao obter dólar. Usando R$ 5.00.")

    # 2. Read Google Sheets FIRST — the rows dictate which FB date ranges we
    #    actually need, so we only fetch what the sheet asks for.
    if progress_callback:
        progress_callback("Lendo Google Sheets para mapear linhas e períodos...")

    if not gc:
        raise RuntimeError("Cliente gspread não fornecido para autenticação.")

    try:
        sh = gc.open_by_url(g_url)
        ws = sh.worksheet(sheet_name)
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir Google Sheet. Verifique o link e se a aba existe: {e}")

    all_values = ws.get_all_values()
    max_row = len(all_values)
    cells_to_update = []

    filled_a = 0
    filled_metrics = 0
    skipped_rows = 0
    not_found = []

    # Detect the header row dynamically (Col A == 'TC', Col B == 'CRIATIVO').
    # The layout varies per sheet — hardcoding DATA_START_ROW=4 skipped the
    # first data row on sheets whose header sits on row 2. Fall back to the
    # constant if the header isn't found.
    data_start = DATA_START_ROW
    for i, rv in enumerate(all_values):
        a = rv[0].strip().upper() if len(rv) > 0 else ""
        b = rv[1].strip().upper() if len(rv) > 1 else ""
        if a == "TC" and b == "CRIATIVO":
            data_start = i + 2  # data begins on the row after the header
            break

    # The overall start date comes from the SHEET, not the UI: the oldest
    # 'Início' among rows still in TESTE. Rows without a parseable date use
    # this derived date; the user-picked date_start is only the last resort
    # when no TESTE row has a date at all.
    auto_date_start = derive_auto_date_start(all_values, data_start, date_start)
    if progress_callback:
        progress_callback(f"Data inicial detectada na planilha: {auto_date_start} (teste em aberto mais antigo).")

    # 3. One FB insights sweep per DISTINCT date range used by the TESTE rows.
    #    Insights only return ads that delivered in the range, so this scales
    #    with active ads instead of the 300k+ full /ads catalog (previous
    #    bottleneck). The sweep doubles as the ad-name index for matching.
    ranges = set()
    for row_idx in range(data_start, max_row + 1):
        row_data = all_values[row_idx - 1]
        ad_name_value = row_data[1] if len(row_data) > 1 else ""  # Col B
        if not ad_name_value or str(ad_name_value).strip() == "":
            continue
        status_val = row_data[12] if len(row_data) > 12 else ""  # Col M
        if "TESTE" not in str(status_val).strip().upper():
            continue
        date_col_c = row_data[2] if len(row_data) > 2 else ""
        ranges.add(parse_excel_date(date_col_c, auto_date_start))

    fb_rows_by_range = {}
    all_insight_rows = []
    for i, since in enumerate(sorted(ranges)):
        if progress_callback:
            progress_callback(f"Puxando insights do FB ({i+1}/{len(ranges)}: {since} → {date_end})...")
        rows_r = fetch_fb_ad_insights_for_accounts(account_ids, since, date_end, token, progress_callback)
        fb_rows_by_range[since] = rows_r
        all_insight_rows.extend(rows_r)

    if progress_callback:
        progress_callback(f"Insights do FB: {len(all_insight_rows)} linhas de anúncios em {len(ranges)} período(s).")

    ad_index = build_ad_index(all_insight_rows)

    # Campaign-name index as fallback for older ads whose code only appears
    # in the campaign name.
    ad_to_campaign = {}
    seen_camp_per_key = {}
    for ads in ad_index.values():
        for ad in ads:
            c_name = ad.get("campaign_name", "")
            c_id = ad.get("campaign_id")
            if not c_name:
                continue
            extracted = extract_ad_name_from_campaign(c_name)
            if not extracted:
                continue
            key = extracted.strip().lower()
            seen = seen_camp_per_key.setdefault(key, set())
            if c_id in seen:
                continue
            seen.add(c_id)
            ad_to_campaign.setdefault(key, []).append({"id": c_id, "name": c_name})

    # Process TESTES Completos Section
    for row_idx in range(data_start, max_row + 1):
        row_data = all_values[row_idx - 1]
        
        ad_name_value = row_data[1] if len(row_data) > 1 else "" # Col B
        if not ad_name_value or str(ad_name_value).strip() == "":
            continue

        search_term = str(ad_name_value).strip().lower()

        # Primary match: by AD NAME (the test codes live in the ad name).
        ad_hits = match_ads(ad_index, search_term)
        matched_infos = []
        if ad_hits:
            seen_c = set()
            for a in ad_hits:
                cid = a.get("campaign_id")
                if cid and cid not in seen_c:
                    seen_c.add(cid)
                    matched_infos.append({"id": cid, "name": a.get("campaign_name", "")})
        else:
            # Fallback: by CAMPAIGN NAME (older ads whose code is in the campaign name).
            if search_term in ad_to_campaign:
                matched_infos = ad_to_campaign[search_term]
            else:
                base_term = search_term.split('.')[0] if '.' in search_term else search_term
                pattern_exact = r'(?<![a-zA-Z0-9_\.])' + re.escape(search_term) + r'(?![a-zA-Z0-9_\.])'
                pattern_base = r'(?<![a-zA-Z0-9_\.])' + re.escape(base_term) + r'(?![a-zA-Z0-9_\.])'

                best_score = 0
                matched_keys = []
                for key in ad_to_campaign.keys():
                    match_score = 0
                    if re.search(pattern_exact, key):
                        match_score = 2
                    elif base_term != search_term and re.search(pattern_base, key):
                        match_score = 1
                    if match_score > 0:
                        if match_score > best_score:
                            best_score = match_score
                            matched_keys = [key]  # Reset com a melhor prioridade
                        elif match_score == best_score:
                            matched_keys.append(key)
                for mk in matched_keys:
                    matched_infos.extend(ad_to_campaign[mk])

        # FB match is OPTIONAL. RedTrack columns (Gasto/Vendas/IC/CPA/verdict)
        # are filled for any ad that has RedTrack data, even without a matching
        # FB campaign. Only the FB-only columns (Hook/Body/CPM/CTR/CPC) and the
        # Col A label require a FB match.
        c_name = matched_infos[0]["name"] if matched_infos else ""

        # Col A Logic (needs a campaign name carrying a TC token)
        if c_name:
            cell_a_val = row_data[0] if len(row_data) > 0 else ""
            if not cell_a_val or str(cell_a_val).strip() == "":
                label = build_col_a_label(c_name)
                if label:
                    cells_to_update.append(gspread.Cell(row=row_idx, col=1, value=label))
                    filled_a += 1

        # Check Col M Status
        status_val = row_data[12] if len(row_data) > 12 else ""
        current_status = str(status_val).strip().upper()

        if "TESTE" in current_status:
            # Get specific start date from Col C (column 3)
            date_col_c = row_data[2] if len(row_data) > 2 else ""
            row_date_start = parse_excel_date(date_col_c, auto_date_start)

            # Current Col D value (data fim) — only write if empty so manual
            # entries and prior verdicts are preserved across re-runs.
            cell_d_val = row_data[3] if len(row_data) > 3 else ""
            col_d_empty = not cell_d_val or str(cell_d_val).strip() == ""

            # --- RedTrack (always, independent of the FB match) ---
            rt = fetch_rt_for_ad(search_term, row_date_start, date_end, redtrack_token)
            vendas = rt["vendas"]
            rt_cost_brl = rt["cost"]
            ic = rt["ic"]  # Initiate Checkout (RedTrack convtype1)
            rt_has_data = (rt_cost_brl > 0 or vendas > 0 or ic > 0)

            if matched_infos or rt_has_data:
                cells_to_update.append(gspread.Cell(row=row_idx, col=10, value=round(rt_cost_brl, 2)))  # J Gasto
                cells_to_update.append(gspread.Cell(row=row_idx, col=11, value=vendas))                  # K Vendas
                cells_to_update.append(gspread.Cell(row=row_idx, col=14, value=ic))                      # N IC

                cpa = rt_cost_brl / vendas if vendas > 0 else 0
                cells_to_update.append(gspread.Cell(row=row_idx, col=12, value=round(cpa, 2)))           # L CPA

                # --- Facebook metrics (from the pre-fetched range sweep) ---
                # Pick the ad matching THIS row's exact variation name from
                # the insights already fetched for this row's date range —
                # no extra HTTP call per row. level='ad' keeps variations
                # separate (campaign level fed BM108.1/.2/.3 the same numbers).
                range_rows = fb_rows_by_range.get(row_date_start, [])
                best_fin = select_ad_metrics(range_rows, search_term)
                if not best_fin and matched_infos:
                    # Campaign-name fallback: the code lives in the campaign
                    # name and the ad itself is named differently — take the
                    # top ad (by impressions) of the matched campaigns.
                    camp_ids = {str(info["id"]) for info in matched_infos}
                    camp_rows = [m for m in range_rows if str(m.get("campaign_id")) in camp_ids]
                    if camp_rows:
                        best_fin = max(camp_rows, key=lambda m: m.get("impressions", 0))
                if best_fin:
                    cpc_brl = best_fin["cpc"] * usd_to_brl
                    cpm_brl = best_fin["cpm"] * usd_to_brl
                    cells_to_update.append(gspread.Cell(row=row_idx, col=5, value=best_fin["hook_rate"]))  # E
                    cells_to_update.append(gspread.Cell(row=row_idx, col=6, value=best_fin["body_rate"]))  # F
                    cells_to_update.append(gspread.Cell(row=row_idx, col=7, value=round(cpm_brl, 2)))      # G
                    cells_to_update.append(gspread.Cell(row=row_idx, col=8, value=best_fin["ctr"]))        # H
                    cells_to_update.append(gspread.Cell(row=row_idx, col=9, value=round(cpc_brl, 2)))      # I

                # Col M - Status auto-fill based on vendas and gasto (RedTrack).
                # When marking VALIDADO/DESCARTADO, also stamp Col D (data fim)
                # with the analysis end date — web_app pads date_end by +1 day, so
                # subtract it back to match the date the user picked.
                verdict_status = None
                if vendas >= 3:
                    verdict_status = "VALIDADO"
                elif vendas == 2 and rt_cost_brl > 800:
                    verdict_status = "VALIDADO"
                elif vendas < 2 and rt_cost_brl >= 800:
                    verdict_status = "DESCARTADO"
                # else: gasto < 800 → don't alter column M / D

                if verdict_status:
                    cells_to_update.append(gspread.Cell(row=row_idx, col=13, value=verdict_status))
                    if col_d_empty:
                        try:
                            end_dt = datetime.datetime.strptime(date_end, "%Y-%m-%d").date() - datetime.timedelta(days=1)
                            data_fim_br = end_dt.strftime("%d/%m/%Y")
                        except Exception:
                            tz_brt = datetime.timezone(datetime.timedelta(hours=-3))
                            data_fim_br = datetime.datetime.now(tz_brt).strftime("%d/%m/%Y")
                        cells_to_update.append(gspread.Cell(row=row_idx, col=4, value=data_fim_br))

                filled_metrics += 1
            else:
                # No FB match and no RedTrack data — nothing to fill.
                not_found.append(str(ad_name_value))
        else:
            skipped_rows += 1

    # Process PRÉ-ESCALA Section
    filled_pre_escala = 0
    skipped_pre_escala = 0
    if progress_callback:
        progress_callback("Preenchendo seção PRÉ-ESCALA com datas dinâmicas...")

    for row_idx in range(data_start, max_row + 1):
        row_data = all_values[row_idx - 1]
        creative_val = row_data[14] if len(row_data) > 14 else ""  # Col O
        if not creative_val or str(creative_val).strip() == "":
            continue

        status_pe_str = row_data[21] if len(row_data) > 21 else ""  # Col V
        if "TESTE" not in str(status_pe_str).strip().upper():
            skipped_pre_escala += 1
            continue

        search_pe = str(creative_val).strip().lower()
        
        # Determine Row Date - Col P uses column 16
        date_col_p = row_data[15] if len(row_data) > 15 else ""
        row_date_pe = parse_excel_date(date_col_p, auto_date_start)
        
        # RedTrack Fetch
        rt = fetch_rt_for_ad(search_pe, row_date_pe, date_end, redtrack_token)
        
        cost_brl = rt['cost']
        vendas_pe = rt['vendas']
        roas_pe = rt['roas']
        
        cpa_pe = 0
        if vendas_pe > 0:
            cpa_pe = cost_brl / vendas_pe
        else:
            cpa_pe = 0 # forced fallback
        
        cells_to_update.append(gspread.Cell(row=row_idx, col=18, value=round(cost_brl, 2)))
        cells_to_update.append(gspread.Cell(row=row_idx, col=19, value=vendas_pe))
        cells_to_update.append(gspread.Cell(row=row_idx, col=20, value=round(roas_pe, 2)))
        cells_to_update.append(gspread.Cell(row=row_idx, col=21, value=round(cpa_pe, 2)))

        filled_pre_escala += 1

    # Batch Update All Cells
    if cells_to_update:
        if progress_callback: progress_callback("⏳ Enviando alterações ao vivo para o Google Sheets...")
        try:
            ws.update_cells(cells_to_update, value_input_option='USER_ENTERED')
        except Exception as e:
            raise RuntimeError(f"Erro ao salvar alterações no Google Sheets. Você precisa compartilhar a planilha como Editor com o robô! Erro: {e}")

    return {
        "filled_a": filled_a, 
        "filled_metrics": filled_metrics, 
        "skipped_rows": skipped_rows, 
        "not_found": not_found,
        "filled_pre_escala": filled_pre_escala,
        "skipped_pre_escala": skipped_pre_escala
    }
