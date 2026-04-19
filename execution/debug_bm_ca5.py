import requests
import json
import sys

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
BM_ID = "657167815226375"

print(f"Buscando contas de anuncio na BM {BM_ID}...")

accounts = []
for endpoint in ['owned_ad_accounts', 'client_ad_accounts']:
    url = f"https://graph.facebook.com/v19.0/{BM_ID}/{endpoint}"
    params = {'access_token': TOKEN, 'fields': 'id,name,account_status', 'limit': 100}
    r = requests.get(url, params=params)
    if r.status_code == 200:
        data = r.json().get('data', [])
        accounts.extend(data)
    else:
        print(f"Erro ao buscar {endpoint}: {r.text}")

ca5_acc = None
for acc in accounts:
    if "CA5" in acc.get("name", "").upper():
        ca5_acc = acc
        break

if not ca5_acc:
    print("\nNenhuma conta com 'CA5' no nome encontrada nesta BM.")
    print("Contas disponiveis:")
    for a in accounts:
        print(f" - {a.get('name')} ({a.get('id')})")
    sys.exit(0)

acc_id = ca5_acc['id'].replace('act_', '')
print(f"\nConta encontrada: {ca5_acc['name']} (ID: {acc_id})")

print("\nBuscando campanhas nesta conta que contenham '899.43'...")
url_camp = f"https://graph.facebook.com/v19.0/act_{acc_id}/campaigns"
params_camp = {"access_token": TOKEN, "fields": "id,name,effective_status", "limit": 500}

matched_campaigns = []
while url_camp:
    r = requests.get(url_camp, params=params_camp)
    if r.status_code != 200:
        print(f"Erro ao buscar campanhas na conta CA5: {r.text}")
        break
    data = r.json()
    for c in data.get("data", []):
        if "899.43" in c.get("name", ""):
            matched_campaigns.append(c)
            print(f"CAMPANHA ENCONTRADA: {c['name']} (ID: {c['id']}, Status: {c.get('effective_status')})")
    url_camp = data.get("paging", {}).get("next")
    params_camp = {}

if not matched_campaigns:
    print("\nNenhuma campanha encontrada contendo '899.43' na conta CA5.")
    sys.exit(0)

print("\nBuscando insights (metricas) para essas campanhas (01/03/2026 ate 31/03/2026)...")
for camp in matched_campaigns:
    c_id = camp["id"]
    url = f"https://graph.facebook.com/v19.0/{c_id}/insights"
    params = {
        'access_token': TOKEN,
        'fields': 'campaign_id,impressions,cpc,cpm,ctr,spend,actions,video_p75_watched_actions',
        'level': 'campaign',
        'time_range': '{"since":"2026-03-01","until":"2026-03-31"}'
    }
    r = requests.get(url, params=params)
    if r.status_code == 200:
        insight_data = r.json().get('data', [])
        if insight_data:
            print(f"\nInsights para {camp['name']}:")
            print(json.dumps(insight_data[0], indent=2))
        else:
            print(f"\nSem metricas para a campanha {camp['name']} (0 impressoes/gasto no periodo).")
    else:
        print(f"\nErro ao buscar insights: {r.status_code} - {r.text}")
