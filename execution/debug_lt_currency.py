import requests

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
BASE_URL = "https://graph.facebook.com/v19.0"

accounts = [
    "987248712293933", "1583963688753767", "6481076258591934",
    "1230367020974448", "542987171356461", "1300700817490669",
    "854290605799299", "982787082695569"
]

print("Scanning for LT1010.2 from 2024 to 2026...")

for acc in accounts:
    r = requests.get(
        f"{BASE_URL}/act_{acc}/insights",
        params={
            "access_token": TOKEN,
            "fields": "campaign_name,spend,account_currency",
            "level": "campaign",
            "time_range": '{"since":"2024-01-01","until":"2026-03-06"}',
            "limit": 5000
        },
        timeout=30
    )
    data = r.json()
    if 'data' in data:
        for c in data['data']:
            c_name = c['campaign_name']
            spend = float(c.get('spend', 0))
            if "lt1010.2" in c_name.lower():
                print(f"[{acc}] Found LT1010.2!")
                print(f"   Name:     {c_name}")
                print(f"   Spend:    {spend}")
                print(f"   Currency: {c.get('account_currency', 'UNKNOWN')}")
                
