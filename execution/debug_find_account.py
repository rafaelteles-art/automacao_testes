#!/usr/bin/env python3
"""Find which BM has a ca6.diana or lotto-type account"""
import requests, json

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
BASE = "https://graph.facebook.com/v19.0"

# Get all BMs
r = requests.get(f"{BASE}/me/businesses", params={"access_token": TOKEN, "fields": "id,name"}, timeout=15)
bms = r.json().get("data", [])

print(f"Found {len(bms)} BMs. Checking each for accounts...\n")

for bm in bms:
    bm_id = bm["id"]
    bm_name = bm["name"]

    # Try both owned and client accounts
    for endpoint in ["owned_ad_accounts", "client_ad_accounts"]:
        r2 = requests.get(
            f"{BASE}/{bm_id}/{endpoint}",
            params={"access_token": TOKEN, "fields": "id,name", "limit": 50},
            timeout=15
        )
        accs = r2.json().get("data", [])
        if accs:
            print(f"BM: {bm_name} ({bm_id}) - {endpoint}:")
            for acc in accs:
                print(f"   {acc['name']} -> {acc['id']}")
            print()
