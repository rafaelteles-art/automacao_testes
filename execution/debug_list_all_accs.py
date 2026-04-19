import sys
import json
import requests
sys.path.append(r"C:\Preencher planilha\execution")
from facebook_redtrack_importer_v2 import FacebookAdsAPI

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
BASE_URL = "https://graph.facebook.com/v19.0"

fb = FacebookAdsAPI(TOKEN)
bms = fb.get_bms()
print(f"BMS found: {len(bms)}")
if bms:
    accounts = fb.get_ad_accounts(bms[0]['id'])
    print(f"Accounts in first BM: {len(accounts)}")
    for a in accounts:
        print(f" -> {a['name']} ({a['id']})")
