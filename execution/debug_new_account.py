import requests

TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
BASE_URL = "https://graph.facebook.com/v19.0"

# The NEW account from the user's screenshot
acc = "1277255524217242"

print(f"=== Scanning account {acc} ===\n")

# 1. Check all campaigns in this account
r = requests.get(
    f"{BASE_URL}/act_{acc}/insights",
    params={
        "access_token": TOKEN,
        "fields": "campaign_name,spend,cpm,account_currency",
        "level": "campaign",
        "time_range": '{"since":"2026-02-01","until":"2026-03-06"}',
        "limit": 500
    },
    timeout=30
)
data = r.json()

test_ads = ['lt1017.7', 'lt1010.2', 'lt899.22', 'lt1033.2', 'lt1011.4', 'lt899.32', 'lt899.33', 'lt1034.4', 'lt1069', 'lt1070']

if 'data' in data:
    print(f"Found {len(data['data'])} campaigns with spend:\n")
    for c in data['data']:
        c_name = c['campaign_name']
        spend = float(c.get('spend', 0))
        currency = c.get('account_currency', '?')
        if spend > 0:
            # Check if any test ad matches
            is_match = ""
            for t in test_ads:
                if t in c_name.lower():
                    is_match = f" <<< MATCH: {t}"
            print(f"  ${spend:>10.2f} {currency} | {c_name}{is_match}")
else:
    print(f"Error or no data: {data}")
