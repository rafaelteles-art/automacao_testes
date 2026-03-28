"""
Search ALL accounts from ALL BMs for the 16 missing ads.
Uses bracket pattern [LTxxxx] to find them.
"""
import requests
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facebook_redtrack_importer_v2 import FacebookAdsAPI

TOKEN = "EAAWDHozjODgBQ0b4ZAZBOZBzGhqi9ZCX0bj8DbmAPnsBfYbEMMZCqMeBMCmLjB2dpzxHvzZC6UQGApi9frZAWyQHPmHZB1hFJa2q3nTNaaDtwHSxqJB5Veeo1CpE9gTYAD3vpJf9vRNNj62z2ebVJ6tD0mKbIzh9DXZCbrnjOHhiAkrcffsEwKcZAuHchAMZBRgi1BjmUIjP2IhfH7O"

MISSING_ADS = [
    "LT581.52", "LT1136.4", "LT1207", "LT1192", "LT1193",
    "LT1185", "LT1228", "LT1229", "LT1224", "LT1225",
    "LT1236", "LT1209", "LT1210", "LT1208", "LT1084.1", "LT1084.2"
]

# Build search patterns: [LT1207], [LT581.52], etc.
SEARCH_TERMS = [ad.lower() for ad in MISSING_ADS]

print("Fetching all BMs...")
fb_api = FacebookAdsAPI(TOKEN)
bms = fb_api.get_business_managers()
print(f"Found {len(bms)} BMs")

print("Fetching all accounts (owned + shared) from all BMs...")
all_accounts = []
seen_ids = set()
for bm in bms:
    accounts = fb_api.get_ad_accounts(bm['id'])
    for acc in accounts:
        if acc['id'] not in seen_ids:
            seen_ids.add(acc['id'])
            all_accounts.append(acc)

print(f"Total unique accounts: {len(all_accounts)}")

# Search function per account
def search_account(acc):
    acc_id = acc['id'].replace('act_', '')
    results = []
    url = f"https://graph.facebook.com/v19.0/act_{acc_id}/campaigns"
    params = {"access_token": TOKEN, "fields": "id,name", "limit": 500}
    try:
        while url:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code != 200: break
            data = r.json()
            for c in data.get("data", []):
                c_name_lower = c.get("name", "").lower()
                for term in SEARCH_TERMS:
                    # Check bracket pattern [LTxxx] or plain match
                    if f"[{term}]" in c_name_lower or f" {term} " in c_name_lower or c_name_lower.endswith(f" {term}"):
                        results.append({
                            "ad": term,
                            "campaign": c['name'],
                            "campaign_id": c['id'],
                            "account_id": acc_id,
                            "account_name": acc.get('name', '?')
                        })
            url = data.get("paging", {}).get("next")
            params = {}
    except:
        pass
    return results

print(f"\nSearching {len(all_accounts)} accounts with 15 threads...")
all_found = {}

with ThreadPoolExecutor(max_workers=15) as executor:
    futures = [executor.submit(search_account, a) for a in all_accounts]
    for i, f in enumerate(as_completed(futures)):
        results = f.result()
        for r in results:
            ad = r['ad']
            if ad not in all_found:
                all_found[ad] = []
            all_found[ad].append(r)
        if (i+1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(all_accounts)} accounts scanned...")

print(f"\n{'='*70}")
print("RESULTS")
print(f"{'='*70}\n")

for ad in MISSING_ADS:
    term = ad.lower()
    if term in all_found:
        matches = all_found[term]
        print(f"FOUND {ad}: {len(matches)} campaign(s)")
        for m in matches[:5]:
            print(f"  Account: {m['account_name']} ({m['account_id']})")
            print(f"  Campaign: {m['campaign']}")
            print()
    else:
        print(f"NOT FOUND: {ad} - not in any accessible account\n")
