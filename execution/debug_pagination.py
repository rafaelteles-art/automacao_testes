#!/usr/bin/env python3
"""Test API pagination to see if it breaks after 200 records"""
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facebook_redtrack_importer_v2 import FacebookAdsAPI

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
ACCOUNT_ID = "act_1471816737648462"  # CA05 - THE DIGITAL DAY

print(f"Testing pagination for {ACCOUNT_ID}...")
fb_api = FacebookAdsAPI(TOKEN)

def pg(msg):
    print(f"Progress: {msg}")

try:
    data = fb_api.get_ad_insights(
        ACCOUNT_ID,
        "2026-02-01",
        "2026-03-03",
        level="ad",
        progress_callback=pg
    )
    print(f"\nFinal count: {len(data)} records")
except Exception as e:
    print(f"\nEXCEPTION RAISED: {e}")
