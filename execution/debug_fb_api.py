import requests
import json

def test():
    FB_ACCESS_TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
    account_id = "542987171356461" # Diana Vargas CA06 (selected previously)
    
    url = f"https://graph.facebook.com/v19.0/act_{account_id}/insights"
    params = {
        'access_token': FB_ACCESS_TOKEN,
        'fields': 'campaign_id,campaign_name,ad_id,ad_name,impressions,clicks,spend,cpc,cpm,ctr',
        'level': 'ad',
        'date_start': '2026-02-01',
        'date_end': '2026-03-03',
        'limit': 5
    }
    response = requests.get(url, params=params)
    data = response.json()
    print("KEYS:", data.keys())
    if 'paging' in data:
      print("PAGING:", data['paging'])
    print(json.dumps(data.get('data', [])[:2], indent=2))

if __name__ == "__main__":
    test()
