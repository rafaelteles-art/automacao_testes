"""
Simulate EXACTLY what fill_creative_tests does for accounts 4248841835333178 and 1471816737648462.
Check why some ads from these accounts are found and others aren't.
"""
import requests
import re
import time

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"

# The two accounts where the missing ads live
TARGET_ACCOUNTS = ["4248841835333178", "1471816737648462"]

MISSING_ADS = [
    "LT1136.4", "LT1207", "LT1192", "LT1193", "LT1185",
    "LT1228", "LT1229", "LT1224", "LT1225", "LT1236",
    "LT1209", "LT1210", "LT1208"
]

def extract_ad_name_NEW(campaign_name):
    if not campaign_name: return ""
    bracket_match = re.search(r'\[(LT\d+(?:\.\d+)?|TC\d+(?:\.\d+)?)\]', campaign_name, re.IGNORECASE)
    if bracket_match: return bracket_match.group(1).strip()
    lt_after_abo = re.search(r'(?:ABO|CBO)\b.*?-\s*((?:LT|BT)\d+(?:\.\d+)?)\s*(?:\s*-|$)', campaign_name, re.IGNORECASE)
    if lt_after_abo: return lt_after_abo.group(1).strip()
    all_lt = re.findall(r'\b((?:LT|BT)\d+(?:\.\d+)?)\b', campaign_name, re.IGNORECASE)
    if all_lt: return all_lt[-1].strip()
    match = re.search(r'(?:ABO|CBO)\s+\S+\s*-\s*(.+)$', campaign_name, re.IGNORECASE)
    if match: return match.group(1).strip()
    parts = campaign_name.rsplit(' - ', 1)
    if len(parts) == 2: return parts[1].strip()
    return ""

for acc_id in TARGET_ACCOUNTS:
    print(f"\n{'='*70}")
    print(f"Account: {acc_id}")
    print(f"{'='*70}")
    
    url = f"https://graph.facebook.com/v19.0/act_{acc_id}/campaigns"
    params = {"access_token": TOKEN, "fields": "id,name", "limit": 500}
    
    all_campaigns = []
    page_num = 0
    while url:
        page_num += 1
        success = False
        for retry in range(4):
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                success = True
                break
            elif r.status_code == 429 or r.status_code >= 500:
                print(f"  Page {page_num} retry {retry}: HTTP {r.status_code}")
                time.sleep(2 ** retry)
            else:
                print(f"  Page {page_num}: HTTP {r.status_code} - {r.text[:200]}")
                break
        
        if not success:
            print(f"  FAILED to fetch page {page_num}!")
            break
        
        data = r.json()
        page_data = data.get("data", [])
        if not page_data:
            break
        all_campaigns.extend(page_data)
        print(f"  Page {page_num}: {len(page_data)} campaigns (total: {len(all_campaigns)})")
        url = data.get("paging", {}).get("next")
        params = {}
    
    print(f"\n  Total campaigns fetched: {len(all_campaigns)}")
    
    # Build ad_to_campaign with NEW logic
    ad_map = {}
    for camp in all_campaigns:
        c_name = camp.get("name", "")
        extracted = extract_ad_name_NEW(c_name)
        if extracted:
            key = extracted.strip().lower()
            ad_map[key] = c_name
    
    print(f"  Unique extracted ad names: {len(ad_map)}")
    
    # Check each missing ad
    for ad in MISSING_ADS:
        search = ad.strip().lower()
        if search in ad_map:
            print(f"  FOUND {ad} -> '{ad_map[search]}'")
        else:
            # Check with regex patterns
            base_term = search.split('.')[0] if '.' in search else search
            pattern = r'(?<![a-zA-Z0-9_\.])' + re.escape(search) + r'(?![a-zA-Z0-9_\.])'
            regex_matches = [k for k in ad_map.keys() if re.search(pattern, k)]
            if regex_matches:
                print(f"  REGEX MATCH {ad} -> keys: {regex_matches}")
            else:
                # Raw search in campaign names
                raw = [c['name'] for c in all_campaigns if ad.lower() in c['name'].lower()]
                if raw:
                    for r_name in raw[:2]:
                        ext = extract_ad_name_NEW(r_name)
                        print(f"  RAW FOUND {ad} in '{r_name}' -> extracted: '{ext}'")
                else:
                    print(f"  NOT FOUND: {ad}")
