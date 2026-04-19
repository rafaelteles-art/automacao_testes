#!/usr/bin/env python3
"""Scan ALL BMs and all their accounts for any campaign containing 'LOTTO' or 'TC'"""
import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
BASE = "https://graph.facebook.com/v19.0"

# Get all BMs
r = requests.get(f"{BASE}/me/businesses", params={"access_token": TOKEN, "fields": "id,name"}, timeout=15)
bms = r.json().get("data", [])
print(f"Found {len(bms)} BMs. Scanning for LOTTO/TC campaigns...\n")

found_any = False
for bm in bms:
    bm_id, bm_name = bm["id"], bm["name"]
    for endpoint in ["owned_ad_accounts", "client_ad_accounts"]:
        r2 = requests.get(f"{BASE}/{bm_id}/{endpoint}", params={"access_token": TOKEN, "fields": "id,name", "limit": 50}, timeout=15)
        accounts = r2.json().get("data", [])
        for acc in accounts:
            acc_id = acc["id"].replace("act_", "")
            # Test with wider date range
            for date_range in [("2026-01-01", "2026-03-03"), ("2025-10-01", "2025-12-31")]:
                r3 = requests.get(
                    f"{BASE}/act_{acc_id}/insights",
                    params={
                        "access_token": TOKEN,
                        "fields": "campaign_name",
                        "level": "campaign",
                        "date_start": date_range[0],
                        "date_end": date_range[1],
                        "limit": 3,
                    },
                    timeout=20
                )
                campaigns = r3.json().get("data", [])
                lotto_camps = [c for c in campaigns if "LOTTO" in (c.get("campaign_name") or "").upper() or "LT" in (c.get("campaign_name") or "")]
                if lotto_camps:
                    print(f"✅ FOUND! BM: {bm_name} / Account: {acc['name']} ({acc['id']}) [{date_range[0]}]")
                    for c in lotto_camps:
                        print(f"   {c.get('campaign_name')}")
                    found_any = True
                    break

if not found_any:
    print("No LOTTO/LT campaigns found in any account for 2025-2026.")
