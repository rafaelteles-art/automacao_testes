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

def fetch_fb_ad_insights_for_campaign(c_id, since, until, fb_token):
    """Return a list of AD-level insight dicts for a campaign.

    Campaign-level insights return one aggregate row, so every ad variation
    that shares a campaign (BM108.1/.2/.3) would get identical Hook/Body/CPM/
    CTR/CPC. Pulling at level='ad' keeps each variation separate; the caller
    then selects the ad matching the row's exact name via select_ad_metrics().
    """
    url = f"https://graph.facebook.com/v19.0/{c_id}/insights"
    params = {
        'access_token': fb_token,
        'fields': 'ad_id,ad_name,impressions,cpc,cpm,ctr,spend,actions,video_p75_watched_actions',
        'level': 'ad',
        'time_range': f'{{"since":"{since}","until":"{until}"}}',
        'limit': 200,
    }
    out = []
    import time
    while url:
        got_page = False
        for _ in range(3):
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                data = r.json()
                for row in data.get('data', []):
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
                    out.append({
                        "ad_id": row.get("ad_id", ""),
                        "ad_name": row.get("ad_name", ""),
                        "spend": float(row.get("spend", 0.0) or 0.0),
                        "cpm": float(row.get("cpm", 0.0) or 0.0),
                        "cpc": float(row.get("cpc", 0.0) or 0.0),
                        "ctr": (float(row.get("ctr", 0.0) or 0.0) / 100),
                        "hook_rate": (video_3s_views / imps) if imps > 0 else 0,
                        "body_rate": (p75 / imps) if imps > 0 else 0,
                        "impressions": imps,
                    })
                url = (data.get('paging', {}) or {}).get('next')
                params = {}  # 'next' URL already carries params
                got_page = True
                break
            elif r.status_code == 429 or r.status_code >= 500:
                time.sleep(2)
                continue
            else:
                url = None
                break
        if not got_page:
            break
    return out

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

def fetch_all_ads(account_ids, token, progress_callback=None):
    """Build an index of Facebook ADS keyed by ad name.

    The test codes (BM188, BM108.1, ...) live in the ad NAME, not the campaign
    name, so indexing campaigns alone misses them. Returns:
        ad_index: {ad_name_lower: [{ad_id, ad_name, campaign_id, campaign_name}]}
    """
    import time
    ad_index = {}
    total = 0
    for account_id in account_ids:
        acc_raw = account_id.replace("act_", "")
        url = f"https://graph.facebook.com/v19.0/act_{acc_raw}/ads"
        params = {"access_token": token, "fields": "id,name,campaign{id,name}", "limit": 500}
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
                is_rate_limit = False
                try:
                    err = r.json().get("error", {}) or {}
                    if err.get("code") in (17, 4, 32, 613) or err.get("is_transient"):
                        is_rate_limit = True
                except Exception:
                    pass
                if r.status_code == 429 or r.status_code >= 500 or is_rate_limit:
                    sleep_s = min(2 ** retry, 60)
                    if progress_callback:
                        progress_callback(f"⏳ FB rate limit ao puxar anúncios (conta {acc_raw}, status {r.status_code}). Retry {retry+1}/6 em {sleep_s}s...")
                    time.sleep(sleep_s)
                    continue
                else:
                    break

            if not success:
                msg = f"⚠️ Falha ao puxar anúncios da conta {acc_raw} (status {last_status}): {last_body}"
                if progress_callback: progress_callback(msg)
                raise RuntimeError(msg)

            data = r.json()
            page_data = data.get("data", [])
            for ad in page_data:
                name = str(ad.get("name", "") or "").strip()
                if not name:
                    continue
                camp = ad.get("campaign", {}) or {}
                ad_index.setdefault(name.lower(), []).append({
                    "ad_id": ad.get("id"),
                    "ad_name": name,
                    "campaign_id": camp.get("id"),
                    "campaign_name": camp.get("name", ""),
                })
                total += 1
            if progress_callback and total:
                progress_callback(f"Catálogo de anúncios: {total} anúncios indexados...")
            paging = data.get("paging", {})
            url = paging.get("next")
            params = {}
    return ad_index

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

def fetch_rt_for_ad(ad_name_lower, since, until, rt_token):
    if not rt_token or not ad_name_lower:
        return {"vendas": 0, "cost": 0.0, "roas": 0.0, "ic": 0}
    
    import time
    
    def internal_fetch(p_num, group_name):
        for retry in range(4):
            try:
                r = requests.get('https://api.redtrack.io/report', params={
                    'api_key': rt_token,
                    'date_from': since,
                    'date_to': until,
                    'group': group_name,
                    'limit': 1000,
                    'page': p_num
                }, timeout=30)
                if r.status_code == 200:
                    return r.json(), True
                elif r.status_code == 429 or r.status_code >= 500:
                    time.sleep(2 ** retry)
                    continue
                else:
                    return [], False
            except requests.RequestException:
                time.sleep(2 ** retry)
                continue
        return [], False

    def fetch_and_sum(group_name):
        v = 0.0; c = 0.0; ro = 0.0; ic = 0.0
        page = 1
        while page <= 5:
            rt_data, success = internal_fetch(page, group_name)
            if not success or not rt_data: break

            for r_row in rt_data:
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

            if len(rt_data) < 1000: break
            page += 1
        return v, c, ro, ic

    # Try rt_ad first (default correct setup)
    vendas, cost, roas, ic = fetch_and_sum("rt_ad")

    # Fallback to sub4 if media buyer populated the wrong parameter (ex: LT1192)
    if vendas == 0 and cost == 0:
        vendas, cost, roas, ic = fetch_and_sum("sub4")

    # Double check API glitch
    if vendas == 0 and cost == 0:
        time.sleep(3)
        vendas, cost, roas, ic = fetch_and_sum("rt_ad")

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

    # 2. Fetch all ADS to build the catalog. Test codes live in the ad name
    #    (BM188, BM108.1, ...), so we index ads by name. The campaign-name index
    #    is derived from the same sweep as a fallback for older ads whose code
    #    only appears in the campaign name.
    if progress_callback: progress_callback("Construindo catálogo de Anúncios...")

    ad_index = fetch_all_ads(account_ids, token, progress_callback)

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

    if not ad_index and not ad_to_campaign:
        raise RuntimeError("Nenhum anúncio encontrado para as contas selecionadas.")

    # 3. Read Google Sheets and Process Row-by-Row
    if progress_callback:
        progress_callback("Varrendo Google Sheets e extraindo dados específicos por linha (Dynamic Dates)...")

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
            row_date_start = parse_excel_date(date_col_c, date_start)

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

                # --- Facebook metrics (only when an ad matched) ---
                # Gather AD-LEVEL insights across matched campaigns, then pick
                # the ad matching THIS row's exact variation name. Fetching at
                # campaign level returned the same aggregate for every variation
                # sharing a campaign (BM108.1/.2/.3 all filled identically).
                if matched_infos:
                    ad_rows = []
                    for info in matched_infos:
                        ad_rows.extend(fetch_fb_ad_insights_for_campaign(info["id"], row_date_start, date_end, token))
                    best_fin = select_ad_metrics(ad_rows, search_term)
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
        row_date_pe = parse_excel_date(date_col_p, date_start)
        
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
