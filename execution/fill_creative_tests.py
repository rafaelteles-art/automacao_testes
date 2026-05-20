#!/usr/bin/env python3
"""
fill_creative_tests.py
Fills Column A (TC group label) and performance metrics (Hook, Body75, CPM, CTR, CPC, Gasto)
of the '032026' sheet conditionally based on User Column M (Status).

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

def fetch_fb_insights_for_campaign(c_id, since, until, fb_token):
    url = f"https://graph.facebook.com/v19.0/{c_id}/insights"
    params = {
        'access_token': fb_token,
        'fields': 'campaign_id,impressions,cpc,cpm,ctr,spend,actions,video_p75_watched_actions',
        'level': 'campaign',
        'time_range': f'{{"since":"{since}","until":"{until}"}}'
    }
    import time
    for _ in range(3):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if data.get('data'):
                row = data['data'][0]
                imps = float(row.get("impressions", 0))
                # Hook Rate
                actions = row.get('actions', [])
                video_3s_views = 0
                for act in actions:
                    if act.get('action_type') == 'video_view':
                        video_3s_views = float(act.get('value', 0))
                        break
                # Hold Rate
                video_p75_actions = row.get('video_p75_watched_actions', [])
                p75 = float(video_p75_actions[0].get('value', 0)) if video_p75_actions else 0
                
                return {
                    "spend": float(row.get("spend", 0.0)),
                    "cpm": float(row.get("cpm", 0.0)),
                    "cpc": float(row.get("cpc", 0.0)),
                    "ctr": (float(row.get("ctr", 0.0)) / 100),
                    "hook_rate": (video_3s_views / imps) if imps > 0 else 0,
                    "body_rate": (p75 / imps) if imps > 0 else 0,
                    "impressions": imps
                }
            break
        elif r.status_code == 429 or r.status_code >= 500:
            time.sleep(2)
            continue
        else:
            break

    return {
        "spend": 0.0, "cpm": 0.0, "cpc": 0.0,
        "ctr": 0.0, "hook_rate": 0.0, "body_rate": 0.0,
        "impressions": 0.0
    }

def fetch_rt_for_ad(ad_name_lower, since, until, rt_token):
    if not rt_token or not ad_name_lower:
        return {"vendas": 0, "cost": 0.0, "roas": 0.0}
    
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
        v = 0.0; c = 0.0; ro = 0.0
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
                    c += float(r_row.get('cost', 0))
                    roas_val = float(r_row.get('roas', 0))
                    if roas_val != 0: ro = roas_val
            
            if len(rt_data) < 1000: break
            page += 1
        return v, c, ro

    # Try rt_ad first (default correct setup)
    vendas, cost, roas = fetch_and_sum("rt_ad")
    
    # Fallback to sub4 if media buyer populated the wrong parameter (ex: LT1192)
    if vendas == 0 and cost == 0:
        vendas, cost, roas = fetch_and_sum("sub4")
        
    # Double check API glitch
    if vendas == 0 and cost == 0:
        time.sleep(3)
        vendas, cost, roas = fetch_and_sum("rt_ad")

    return {"vendas": vendas, "cost": cost, "roas": roas}

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

    # 2. Fetch all campaigns to build catalog
    if progress_callback: progress_callback("Construindo catálogo raiz de Campanhas...")

    all_campaigns = []
    for account_id in account_ids:
        acc_raw = account_id.replace("act_", "")
        url = f"https://graph.facebook.com/v19.0/act_{acc_raw}/campaigns"
        params = {"access_token": token, "fields": "id,name", "limit": 500}
        import time
        while url:
            success = False
            last_status = None
            last_body = None
            for retry in range(6):
                r = requests.get(url, params=params, timeout=30)
                last_status = r.status_code
                last_body = r.text[:500]
                if r.status_code == 200:
                    success = True
                    break
                # Detect FB rate limit codes in body (error.code 17, 4, 32, 613)
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
                        progress_callback(f"⏳ FB rate limit (conta {acc_raw}, status {r.status_code}). Retry {retry+1}/6 em {sleep_s}s...")
                    time.sleep(sleep_s)
                    continue
                else:
                    break

            if not success:
                msg = f"⚠️ Falha ao puxar campanhas da conta {acc_raw} (status {last_status}): {last_body}"
                if progress_callback: progress_callback(msg)
                raise RuntimeError(msg)
                
            data = r.json()
            page_data = data.get("data", [])
            if not page_data: break
            all_campaigns.extend(page_data)
            paging = data.get("paging", {})
            url = paging.get("next")
            params = {}

    ad_to_campaign = {}
    for camp in all_campaigns:
        c_name = camp.get("name", "")
        c_id = camp.get("id")
        if c_name:
            extracted = extract_ad_name_from_campaign(c_name)
            if extracted:
                key = extracted.strip().lower()
                if key not in ad_to_campaign: ad_to_campaign[key] = []
                ad_to_campaign[key].append({"id": c_id, "name": c_name})

    if not ad_to_campaign:
        raise RuntimeError("Nenhuma campanha válida encontrada para as contas selecionadas.")

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

    # Process TESTES Completos Section
    for row_idx in range(DATA_START_ROW, max_row + 1):
        row_data = all_values[row_idx - 1]
        
        ad_name_value = row_data[1] if len(row_data) > 1 else "" # Col B
        if not ad_name_value or str(ad_name_value).strip() == "":
            continue

        search_term = str(ad_name_value).strip().lower()
        matched_infos = []
        
        if search_term in ad_to_campaign:
            matched_infos = ad_to_campaign[search_term]
        else:
            import re
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
                        
            matched_infos = []
            for mk in matched_keys:
                matched_infos.extend(ad_to_campaign[mk])

        if not matched_infos:
            not_found.append(str(ad_name_value))
            continue
            
        c_name = matched_infos[0]["name"]

        # Col A Logic
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
            
            best_fin = None
            max_imps = -1
            max_spend = -1
            
            # Check all matched campaigns and pick the one with most impressions (or spend)
            for info in matched_infos:
                fin = fetch_fb_insights_for_campaign(info["id"], row_date_start, date_end, token)
                imps = fin.get("impressions", 0)
                spend_fb = fin.get("spend", 0)
                
                if imps > max_imps or (imps == max_imps and spend_fb > max_spend):
                    max_imps = imps
                    max_spend = spend_fb
                    best_fin = fin
                    
            if not best_fin:
                best_fin = {"spend": 0.0, "cpm": 0.0, "cpc": 0.0, "ctr": 0.0, "hook_rate": 0.0, "body_rate": 0.0, "impressions": 0.0}
            
            fin = best_fin
            
            cpc_brl = fin["cpc"] * usd_to_brl
            cpm_brl = fin["cpm"] * usd_to_brl
            
            # Fetch RedTrack dynamically for this row
            rt = fetch_rt_for_ad(search_term, row_date_start, date_end, redtrack_token)
            vendas = rt["vendas"]
            rt_cost_brl = rt["cost"]
            
            # Queue metric updates
            cells_to_update.append(gspread.Cell(row=row_idx, col=5, value=fin["hook_rate"]))
            cells_to_update.append(gspread.Cell(row=row_idx, col=6, value=fin["body_rate"]))
            cells_to_update.append(gspread.Cell(row=row_idx, col=7, value=round(cpm_brl, 2)))
            cells_to_update.append(gspread.Cell(row=row_idx, col=8, value=fin["ctr"]))
            cells_to_update.append(gspread.Cell(row=row_idx, col=9, value=round(cpc_brl, 2)))
            cells_to_update.append(gspread.Cell(row=row_idx, col=10, value=round(rt_cost_brl, 2))) # Pull Gasto from RedTrack
            
            cells_to_update.append(gspread.Cell(row=row_idx, col=11, value=vendas))
            
            cpa = 0
            if vendas > 0:
                cpa = rt_cost_brl / vendas
            else:
                cpa = 0 # Forced fallback to 0
                
            cells_to_update.append(gspread.Cell(row=row_idx, col=12, value=round(cpa, 2)))

            # Col M - Status auto-fill based on vendas and gasto.
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
            skipped_rows += 1

    # Process PRÉ-ESCALA Section
    filled_pre_escala = 0
    skipped_pre_escala = 0
    if progress_callback:
        progress_callback("Preenchendo seção PRÉ-ESCALA com datas dinâmicas...")

    for row_idx in range(DATA_START_ROW, max_row + 1):
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
