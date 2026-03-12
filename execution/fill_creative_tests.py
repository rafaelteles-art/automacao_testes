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

DEFAULT_FB_TOKEN = "EAAWDHozjODgBQ0b4ZAZBOZBzGhqi9ZCX0bj8DbmAPnsBfYbEMMZCqMeBMCmLjB2dpzxHvzZC6UQGApi9frZAWyQHPmHZB1hFJa2q3nTNaaDtwHSxqJB5Veeo1CpE9gTYAD3vpJf9vRNNj62z2ebVJ6tD0mKbIzh9DXZCbrnjOHhiAkrcffsEwKcZAuHchAMZBRgi1BjmUIjP2IhfH7O"

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
    match = re.search(r'(?:ABO|CBO)\s+\S+\s*-\s*(.+)$', campaign_name, re.IGNORECASE)
    if match: return match.group(1).strip()
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
                    "body_rate": (p75 / imps) if imps > 0 else 0
                }
            break
        elif r.status_code == 429 or r.status_code >= 500:
            time.sleep(2)
            continue
        else:
            break

    return {
        "spend": 0.0, "cpm": 0.0, "cpc": 0.0,
        "ctr": 0.0, "hook_rate": 0.0, "body_rate": 0.0
    }

def fetch_rt_for_ad(ad_name_lower, since, until, rt_token):
    vendas = 0.0
    cost = 0.0
    roas = 0.0
    if not rt_token or not ad_name_lower:
        return {"vendas": 0, "cost": 0.0, "roas": 0.0}
    
    import time
    page = 1
    
    def internal_fetch(p_num):
        for retry in range(4):
            try:
                r = requests.get('https://api.redtrack.io/report', params={
                    'api_key': rt_token,
                    'date_from': since,
                    'date_to': until,
                    'group': 'rt_ad',
                    'limit': 2000,
                    'page': p_num
                }, timeout=30)
                
                if r.status_code == 200:
                    return r.json(), True
                elif r.status_code == 429 or r.status_code >= 500:
                    time.sleep(2 ** retry) # Exponential backoff: 1s, 2s, 4s, 8s
                    continue
                else:
                    return [], False
            except requests.RequestException:
                time.sleep(2 ** retry)
                continue
        return [], False

    # First Pass
    while page <= 5:
        rt_data, success = internal_fetch(page)
        if not success or not rt_data: break
        
        for r_row in rt_data:
            rt_ad = str(r_row.get('rt_ad', '')).strip().lower()
            if not rt_ad: continue
            
            is_match = False
            if rt_ad == ad_name_lower:
                is_match = True
            elif rt_ad == ad_name_lower.split(" - ")[0].split(" ")[0]:
                is_match = True
                
            if is_match:
                vendas += float(r_row.get('convtype2', 0))
                cost += float(r_row.get('cost', 0))
                roas_val = float(r_row.get('roas', 0))
                if roas_val != 0: roas = roas_val
        
        if len(rt_data) < 2000: break
        page += 1

    # DOUBLE CHECK logic: if intermittent API drop caused 0 data, force a second pass after sleeping
    if vendas == 0 and cost == 0:
        time.sleep(3)
        rt_data_dc, success_dc = internal_fetch(1)
        if success_dc and rt_data_dc:
            for r_row in rt_data_dc:
                rt_ad = str(r_row.get('rt_ad', '')).strip().lower()
                if not rt_ad: continue
                
                is_match = False
                if rt_ad == ad_name_lower:
                    is_match = True
                elif rt_ad == ad_name_lower.split(" - ")[0].split(" ")[0]:
                    is_match = True
                    
                if is_match:
                    vendas += float(r_row.get('convtype2', 0))
                    cost += float(r_row.get('cost', 0))
                    roas_val = float(r_row.get('roas', 0))
                    if roas_val != 0: roas = roas_val

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
        while url:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code != 200: break
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
                if key not in ad_to_campaign: ad_to_campaign[key] = {"id": c_id, "name": c_name}

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
        matched_info = None
        
        if search_term in ad_to_campaign:
            matched_info = ad_to_campaign[search_term]
        else:
            for key, info in ad_to_campaign.items():
                if search_term in key or key in search_term:
                    matched_info = info
                    break

        if not matched_info:
            not_found.append(str(ad_name_value))
            continue
            
        c_name = matched_info["name"]
        c_id = matched_info["id"]

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
            
            # Fetch FB data dynamically for this row
            fin = fetch_fb_insights_for_campaign(c_id, row_date_start, date_end, token)
            
            cpc_brl = fin["cpc"] * usd_to_brl
            cpm_brl = fin["cpm"] * usd_to_brl
            spend_brl = fin["spend"] * usd_to_brl
            
            # Queue metric updates
            cells_to_update.append(gspread.Cell(row=row_idx, col=5, value=fin["hook_rate"]))
            cells_to_update.append(gspread.Cell(row=row_idx, col=6, value=fin["body_rate"]))
            cells_to_update.append(gspread.Cell(row=row_idx, col=7, value=round(cpm_brl, 2)))
            cells_to_update.append(gspread.Cell(row=row_idx, col=8, value=fin["ctr"]))
            cells_to_update.append(gspread.Cell(row=row_idx, col=9, value=round(cpc_brl, 2)))
            cells_to_update.append(gspread.Cell(row=row_idx, col=10, value=round(spend_brl, 2)))
            
            # Fetch RedTrack dynamically for this row
            rt = fetch_rt_for_ad(search_term, row_date_start, date_end, redtrack_token)
            vendas = rt["vendas"]
            
            cells_to_update.append(gspread.Cell(row=row_idx, col=11, value=vendas))
            
            cpa = 0
            if vendas > 0:
                cpa = spend_brl / vendas
            else:
                cpa = 0 # Forced fallback to 0
                
            cells_to_update.append(gspread.Cell(row=row_idx, col=12, value=round(cpa, 2)))

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
