import requests

RT_TOKEN = "wB7qY69R0KVU9tl4TBaQ"
SINCE = "2026-03-01"
UNTIL = "2026-03-28"
SEARCH = "581"

print(f"Buscando LT581.52 no RedTrack ({SINCE} a {UNTIL})...\n")

page = 1
found = []
while page <= 10:
    r = requests.get('https://api.redtrack.io/report', params={
        'api_key': RT_TOKEN,
        'date_from': SINCE,
        'date_to': UNTIL,
        'group': 'rt_ad',
        'limit': 1000,
        'page': page
    }, timeout=30)
    if r.status_code != 200:
        print(f"Page {page}: HTTP {r.status_code}")
        break
    data = r.json()
    if not data:
        break
    print(f"Page {page}: {len(data)} rows")
    for row in data:
        rt_ad = str(row.get('rt_ad', '')).strip()
        if SEARCH in rt_ad:
            found.append(row)
    if len(data) < 1000:
        break
    page += 1

print(f"\nResultados contendo '{SEARCH}':")
for m in found:
    rt_ad = m.get('rt_ad', '')
    cost = m.get('cost', 0)
    vendas = m.get('convtype2', 0)
    roas = m.get('roas', 0)
    print(f"  rt_ad='{rt_ad}' | cost={cost} | vendas={vendas} | roas={roas}")
