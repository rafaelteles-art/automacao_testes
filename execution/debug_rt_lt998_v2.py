"""
Debug: confirm rt_ad format and pagination issue for LT998.9
"""
import requests

RT_TOKEN = "wB7qY69R0KVU9tl4TBaQ"
SINCE = "2026-03-01"
UNTIL = "2026-03-28"

# Fetch ALL pages properly to find 998.9
print("=== Fetching ALL rt_ad pages ===")
page = 1
all_rt_ads = []
found = []

while page <= 20:
    r = requests.get('https://api.redtrack.io/report', params={
        'api_key': RT_TOKEN,
        'date_from': SINCE,
        'date_to': UNTIL,
        'group': 'rt_ad',
        'limit': 1000,
        'page': page
    }, timeout=30)
    if r.status_code != 200:
        print(f"  Page {page}: HTTP {r.status_code}")
        break
    data = r.json()
    if not data:
        print(f"  Page {page}: empty - DONE")
        break
    print(f"  Page {page}: {len(data)} rows")
    
    for row in data:
        rt_ad = str(row.get('rt_ad', '')).strip()
        all_rt_ads.append(rt_ad)
        # Search for '998' without LT prefix
        if '998' in rt_ad:
            found.append(row)
    
    if len(data) < 1000:
        print(f"  Last page (< 1000 rows)")
        break
    page += 1

print(f"\nTotal rt_ad values across ALL pages: {len(all_rt_ads)}")
print(f"Unique: {len(set(all_rt_ads))}")
print(f"\nMatches containing '998': {len(found)}")
for m in found:
    rt_ad = m.get('rt_ad', '')
    cost = m.get('cost', 0)
    vendas = m.get('convtype2', 0)
    roas = m.get('roas', 0)
    print(f"  rt_ad='{rt_ad}' | cost={cost} | vendas={vendas} | roas={roas}")

# Also test: what does '998.9' without LT look like?
stripped_matches = [r for r in all_rt_ads if r == '998.9']
print(f"\nExact match for '998.9' (no LT): {len(stripped_matches)}")

# Show some samples around the 990-999 range
range_matches = [a for a in sorted(set(all_rt_ads)) if a.startswith('99')]
print(f"\nAll rt_ad values starting with '99': {range_matches[:20]}")
