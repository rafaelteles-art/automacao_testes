#!/usr/bin/env python3
import requests
import json

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
ACCOUNT_ID = "act_542987171356461"

url = f"https://graph.facebook.com/v19.0/{ACCOUNT_ID}/insights"
params = {
    'access_token': TOKEN,
    'fields': 'campaign_name,impressions,video_play_actions,video_p25_watched_actions,video_p50_watched_actions,video_p75_watched_actions,video_p100_watched_actions,video_15_sec_watched_actions,video_30_sec_watched_actions,video_avg_time_watched_actions,actions',
    'level': 'campaign',
    'filtering': '[{"field":"campaign.name","operator":"CONTAIN","value":"LT581.3 - P21"}]',
    'date_preset': 'maximum'
}

r = requests.get(url, params=params)
print(json.dumps(r.json(), indent=2))
