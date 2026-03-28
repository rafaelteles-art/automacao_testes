"""
Debug: search for the 16 missing ads across all FB accounts.
Tests both the bracket extraction and the raw campaign name search.
"""
import requests
import re
import json

TOKEN = "EAAWDHozjODgBQ0b4ZAZBOZBzGhqi9ZCX0bj8DbmAPnsBfYbEMMZCqMeBMCmLjB2dpzxHvzZC6UQGApi9frZAWyQHPmHZB1hFJa2q3nTNaaDtwHSxqJB5Veeo1CpE9gTYAD3vpJf9vRNNj62z2ebVJ6tD0mKbIzh9DXZCbrnjOHhiAkrcffsEwKcZAuHchAMZBRgi1BjmUIjP2IhfH7O"

MISSING_ADS = [
    "LT581.52", "LT1136.4", "LT1207", "LT1192", "LT1193",
    "LT1185", "LT1228", "LT1229", "LT1224", "LT1225",
    "LT1236", "LT1209", "LT1210", "LT1208", "LT1084.1", "LT1084.2"
]

# The accounts the app uses (from previous context)
ACCOUNTS = [
    "987248712293933", "1583963688753767", "6481076258591934",
    "1230367020974448", "542987171356461", "1300700817490669",
    "854290605799299", "982787082695569", "875839750407156", "550719079377709"
]

def extract_ad_name_from_campaign(campaign_name):
    if not campaign_name: return ""
    bracket_match = re.search(r'\[(LT\d+(?:\.\d+)?|TC\d+(?:\.\d+)?)\]', campaign_name, re.IGNORECASE)
    if bracket_match:
        return bracket_match.group(1).strip()
    match = re.search(r'(?:ABO|CBO)\s+\S+\s*-\s*(.+)$', campaign_name, re.IGNORECASE)
    if match: return match.group(1).strip()
    parts = campaign_name.rsplit(' - ', 1)
    if len(parts) == 2: return parts[1].strip()
    return ""

# Fetch all campaigns
print("Fetching all campaigns from all accounts...")
all_campaigns = []
for acc in ACCOUNTS:
    url = f"https://graph.facebook.com/v19.0/act_{acc}/campaigns"
    params = {"access_token": TOKEN, "fields": "id,name", "limit": 500}
    while url:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200: break
        data = r.json()
        page_data = data.get("data", [])
        if not page_data: break
        all_campaigns.extend(page_data)
        url = data.get("paging", {}).get("next")
        params = {}

print(f"Total campaigns fetched: {len(all_campaigns)}")

# Build the ad_to_campaign map (same as production code)
ad_to_campaign = {}
for camp in all_campaigns:
    c_name = camp.get("name", "")
    extracted = extract_ad_name_from_campaign(c_name)
    if extracted:
        key = extracted.strip().lower()
        if key not in ad_to_campaign:
            ad_to_campaign[key] = []
        ad_to_campaign[key].append({"id": camp["id"], "name": c_name})

print(f"Unique extracted ad names: {len(ad_to_campaign)}")

# Now test each missing ad
print(f"\n{'='*70}")
print("TESTING EACH MISSING AD")
print(f"{'='*70}\n")

for ad in MISSING_ADS:
    search_term = ad.strip().lower()
    print(f"--- {ad} (search_term='{search_term}') ---")
    
    # Direct key match
    if search_term in ad_to_campaign:
        infos = ad_to_campaign[search_term]
        print(f"  DIRECT MATCH: {len(infos)} campaign(s)")
        for i in infos[:3]:
            print(f"    Campaign: {i['name']}")
        continue
    
    # Regex match (same as production)
    base_term = search_term.split('.')[0] if '.' in search_term else search_term
    pattern_exact = r'(?<![a-zA-Z0-9_\.])' + re.escape(search_term) + r'(?![a-zA-Z0-9_\.])'
    pattern_base = r'(?<![a-zA-Z0-9_\.])' + re.escape(base_term) + r'(?![a-zA-Z0-9_\.])'
    
    exact_keys = [k for k in ad_to_campaign.keys() if re.search(pattern_exact, k)]
    base_keys = [k for k in ad_to_campaign.keys() if re.search(pattern_base, k)]
    
    if exact_keys:
        print(f"  REGEX EXACT MATCH keys: {exact_keys[:5]}")
    elif base_keys:
        print(f"  REGEX BASE MATCH keys: {base_keys[:5]}")
    else:
        print(f"  NOT FOUND in ad_to_campaign!")
        # Search raw campaign names for any with this ad number
        raw_matches = [c['name'] for c in all_campaigns if ad.lower() in c['name'].lower()]
        if raw_matches:
            print(f"  BUT FOUND in raw campaign names ({len(raw_matches)}):")
            for rm in raw_matches[:3]:
                extracted = extract_ad_name_from_campaign(rm)
                print(f"    Campaign: '{rm}'")
                print(f"    Extracted: '{extracted}'")
        else:
            ad_num = ad.replace("LT", "")
            raw_num = [c['name'] for c in all_campaigns if ad_num in c['name']]
            if raw_num:
                print(f"  FOUND by number '{ad_num}' in raw names ({len(raw_num)}):")
                for rm in raw_num[:3]:
                    extracted = extract_ad_name_from_campaign(rm)
                    print(f"    Campaign: '{rm}'")
                    print(f"    Extracted: '{extracted}'")
            else:
                print(f"  TRULY NOT FOUND in any campaign name (not in these accounts)")
    print()
