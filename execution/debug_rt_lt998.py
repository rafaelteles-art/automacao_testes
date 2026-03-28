"""
Debug: test RedTrack fetch for LT998.9
Replicates the exact logic from fill_creative_tests.fetch_rt_for_ad
but with verbose logging so we can see what's happening.
"""
import requests
import json

RT_TOKEN = "wB7qY69R0KVU9tl4TBaQ"
SEARCH_AD = "lt998.9"
SINCE = "2026-03-01"
UNTIL = "2026-03-28"

print(f"=== Testing RedTrack fetch for '{SEARCH_AD}' ===")
print(f"Period: {SINCE} to {UNTIL}\n")

# Step 1: Fetch ALL rt_ad rows and search
print("--- Step 1: group=rt_ad (all pages) ---")
page = 1
all_rt_ads = []
found_rt_ad = []

while page <= 10:
    r = requests.get('https://api.redtrack.io/report', params={
        'api_key': RT_TOKEN,
        'date_from': SINCE,
        'date_to': UNTIL,
        'group': 'rt_ad',
        'limit': 2000,
        'page': page
    }, timeout=30)
    if r.status_code != 200:
        print(f"  Page {page}: HTTP {r.status_code}")
        break
    data = r.json()
    if not data:
        print(f"  Page {page}: empty")
        break
    print(f"  Page {page}: {len(data)} rows")
    
    for row in data:
        rt_ad = str(row.get('rt_ad', '')).strip().lower()
        all_rt_ads.append(rt_ad)
        if '998' in rt_ad:
            found_rt_ad.append(row)
    
    if len(data) < 2000:
        break
    page += 1

print(f"\n  Total rt_ad values fetched: {len(all_rt_ads)}")
print(f"  Matches containing '998': {len(found_rt_ad)}")
for m in found_rt_ad:
    rt_ad = m.get('rt_ad', '')
    cost = m.get('cost', 0)
    vendas = m.get('convtype2', 0)
    roas = m.get('roas', 0)
    print(f"    rt_ad='{rt_ad}' | cost={cost} | vendas={vendas} | roas={roas}")

# Step 2: Check matching logic
print(f"\n--- Step 2: Testing match logic ---")
print(f"  ad_name_lower = '{SEARCH_AD}'")
print(f"  split result  = '{SEARCH_AD.split(' - ')[0].split(' ')[0]}'")

exact_match = [a for a in all_rt_ads if a == SEARCH_AD]
partial_match = [a for a in all_rt_ads if a == SEARCH_AD.split(" - ")[0].split(" ")[0]]
contains_match = [a for a in all_rt_ads if SEARCH_AD in a or '998.9' in a]

print(f"  Exact matches (rt_ad == '{SEARCH_AD}'): {len(exact_match)}")
print(f"  Partial matches (rt_ad == '{SEARCH_AD.split(' - ')[0].split(' ')[0]}'): {len(partial_match)}")
print(f"  Contains '998.9': {len(contains_match)}")
if contains_match:
    print(f"    Values: {contains_match[:10]}")

# Step 3: Also try sub4 fallback
print(f"\n--- Step 3: group=sub4 check ---")
r = requests.get('https://api.redtrack.io/report', params={
    'api_key': RT_TOKEN,
    'date_from': SINCE,
    'date_to': UNTIL,
    'group': 'sub4',
    'limit': 2000,
    'page': 1
}, timeout=30)
if r.status_code == 200:
    data = r.json()
    print(f"  Total rows: {len(data)}")
    sub4_matches = [row for row in data if '998' in str(row.get('sub4', '')).lower()]
    print(f"  sub4 matches containing '998': {len(sub4_matches)}")
    for m in sub4_matches:
        print(f"    sub4='{m.get('sub4','')}' | cost={m.get('cost',0)} | vendas={m.get('convtype2',0)}")
else:
    print(f"  HTTP {r.status_code}")

# Step 4: Dump a sample of actual rt_ad values to see the format
print(f"\n--- Step 4: Sample of all rt_ad values (first 30) ---")
for i, a in enumerate(sorted(set(all_rt_ads))[:30]):
    print(f"  [{i}] '{a}'")

print(f"\n  ... total unique rt_ad values: {len(set(all_rt_ads))}")
