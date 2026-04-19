import requests
import json

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
BASE_URL = "https://graph.facebook.com/v19.0"

accounts = [
    "987248712293933", "1583963688753767", "6481076258591934",
    "1230367020974448", "542987171356461", "1300700817490669",
    "854290605799299", "982787082695569", "875839750407156", "550719079377709"
]

results = []
for acc in accounts:
    r = requests.get(
        f"{BASE_URL}/act_{acc}/insights",
        params={
            "access_token": TOKEN,
            "fields": "ad_name,spend",
            "level": "ad",
            "time_range": '{"since":"2026-03-01","until":"2026-03-06"}',
            "limit": 5000
        },
        timeout=30
    )
    data = r.json()
    if 'data' in data:
        for a in data['data']:
            a_name = a.get('ad_name', '')
            spend = float(a.get('spend', 0))
            if spend > 0:
                lower_name = a_name.lower()
                if "1010" in lower_name or "1011" in lower_name or "1017" in lower_name:
                    results.append(f"ACC {acc} | ${spend:.2f} | AD: {a_name}")

with open(r'c:\Preencher planilha\execution\dumped_ads.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(results))
print(f"Dumped {len(results)} matches!")

