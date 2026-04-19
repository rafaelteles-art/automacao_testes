#!/usr/bin/env python3
"""Test all Diana Vargas accounts for campaign data"""
import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
BASE = "https://graph.facebook.com/v19.0"

# All Diana Vargas accounts from debug_find_account.py output
accounts = {
    "Diana CA10": "act_987248712293933",
    "Diana CA09": "act_1583963688753767",
    "Diana CA08": "act_6481076258591934",
    "Diana CA07": "act_1230367020974448",
    "Diana CA06": "act_542987171356461",
    "Diana CA05": "act_1300700817490669",
    "Diana CA04": "act_854290605799299",
    "Diana CA03": "act_982787082695569",
    "1": "act_875839750407156",
    "2": "act_550719079377709",
}

for name, acc_id in accounts.items():
    raw = acc_id.replace("act_", "")
    r = requests.get(
        f"{BASE}/act_{raw}/insights",
        params={
            "access_token": TOKEN,
            "fields": "campaign_name",
            "level": "campaign",
            "date_start": "2026-02-01",
            "date_end": "2026-03-03",
            "limit": 3,
        },
        timeout=20
    )
    data = r.json()
    campaigns = data.get("data", [])
    if campaigns:
        print(f"\n✅ {name} ({acc_id}) has {len(campaigns)} campaigns:")
        for c in campaigns:
            print(f"   {c.get('campaign_name', 'N/A')}")
    else:
        err = data.get("error", {}).get("message", "empty")
        print(f"   {name}: 0 campaigns ({err[:60]})")
