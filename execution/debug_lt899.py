import requests
import re

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"

accounts = [
    "987248712293933", "1583963688753767", "6481076258591934",
    "1230367020974448", "542987171356461", "1300700817490669",
    "854290605799299", "982787082695569", "875839750407156", "550719079377709"
]
search_ad = "899.43"

print(f"Searching for {search_ad} in campaigns anywhere in their names...")

matched = []
results = []
for acc in accounts:
    url = f"https://graph.facebook.com/v19.0/act_{acc}/campaigns"
    params = {"access_token": TOKEN, "fields": "id,name", "limit": 500}
    while url:
        r = requests.get(url, params=params)
        if r.status_code != 200: break
        data = r.json()
        for camp in data.get("data", []):
            if search_ad.lower() in camp['name'].lower() or "lt899" in camp['name'].lower():
                matched.append(camp)
                res = f"FOUND: {camp['name']} (ID: {camp['id']}) in acc {acc}"
                print(res)
                results.append(res)
        
        url = data.get("paging", {}).get("next")
        params = {}

print(f"Total matched campaigns: {len(matched)}")

with open(r'c:\Preencher planilha\execution\lt899_dump.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(results))
