import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facebook_redtrack_importer_v2 import FacebookAdsAPI

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
fb_api = FacebookAdsAPI(TOKEN)

print("Fetching all Business Managers...")
bms = fb_api.get_business_managers()
if not bms:
    print("No BMs found or token error.")
    sys.exit(0)

all_accounts = []
print(f"Found {len(bms)} BMs. Fetching all accounts (owned & shared)...")
for bm in bms:
    accounts = fb_api.get_ad_accounts(bm['id'])
    for acc in accounts:
        if acc not in all_accounts:
            all_accounts.append(acc)

print(f"Total unique accounts accessible: {len(all_accounts)}")

from concurrent.futures import ThreadPoolExecutor, as_completed

def check_account(acc):
    acc_id = acc['id'].replace('act_', '')
    acc_matches_camp = []
    acc_matches_ad = []
    
    # Check campaigns
    url_camp = f"https://graph.facebook.com/v19.0/act_{acc_id}/campaigns"
    params_camp = {"access_token": TOKEN, "fields": "id,name", "limit": 500}
    try:
        while url_camp:
            r = requests.get(url_camp, params=params_camp, timeout=20)
            if r.status_code != 200: break
            data = r.json()
            for c in data.get("data", []):
                if search in c.get("name", ""):
                    acc_matches_camp.append(c)
                    print(f"FOUND CAMPAIGN: {c['name']} (ID: {c['id']}) in acc {acc_id}")
            url_camp = data.get("paging", {}).get("next")
            params_camp = {}
    except: pass
        
    # Check ads
    url_ad = f"https://graph.facebook.com/v19.0/act_{acc_id}/ads"
    params_ad = {"access_token": TOKEN, "fields": "id,name,campaign{name,id}", "limit": 500}
    try:
        while url_ad:
            r = requests.get(url_ad, params=params_ad, timeout=20)
            if r.status_code != 200: break
            data = r.json()
            for a in data.get("data", []):
                if search in a.get("name", ""):
                    acc_matches_ad.append(a)
                    c_name = a.get('campaign', {}).get('name', 'UNKNOWN')
                    print(f"FOUND AD: {a['name']} (ID: {a['id']}) inside Campaign: {c_name} in acc {acc_id}")
            url_ad = data.get("paging", {}).get("next")
            params_ad = {}
    except: pass
        
    return acc_matches_camp, acc_matches_ad

matched_campaigns = []
matched_ads = []

print("Starting 15 threads...")
with ThreadPoolExecutor(max_workers=15) as executor:
    futures = [executor.submit(check_account, a) for a in all_accounts]
    for i, f in enumerate(as_completed(futures)):
        camp_res, ad_res = f.result()
        matched_campaigns.extend(camp_res)
        matched_ads.extend(ad_res)
        if i % 10 == 0:
            print(f"Progress: {i}/{len(all_accounts)} accounts scanned...")

print(f"\nDONE! Found {len(matched_campaigns)} campaigns and {len(matched_ads)} ads.")
