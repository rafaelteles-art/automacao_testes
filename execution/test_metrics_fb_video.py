#!/usr/bin/env python3
import requests
import json

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
ACCOUNT_ID = "act_542987171356461"

url = f"https://graph.facebook.com/v19.0/{ACCOUNT_ID}/insights"
params = {
    'access_token': TOKEN,
    'fields': 'campaign_name,impressions,cpc,ctr,video_play_actions,video_p75_watched_actions',
    'level': 'campaign',
    'date_start': '2026-03-01',
    'date_end': '2026-03-03',
    'limit': 50
}

r = requests.get(url, params=params)
data = r.json().get('data', [])
# filter only those with video_play_actions
video_data = [d for d in data if 'video_play_actions' in d]

print(json.dumps(video_data[:2], indent=2))
