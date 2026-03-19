import requests
import json
import sys

TOKEN = "EAAWDHozjODgBQ0b4ZAZBOZBzGhqi9ZCX0bj8DbmAPnsBfYbEMMZCqMeBMCmLjB2dpzxHvzZC6UQGApi9frZAWyQHPmHZB1hFJa2q3nTNaaDtwHSxqJB5Veeo1CpE9gTYAD3vpJf9vRNNj62z2ebVJ6tD0mKbIzh9DXZCbrnjOHhiAkrcffsEwKcZAuHchAMZBRgi1BjmUIjP2IhfH7O"
ACC_ID = "657167815226375"

print(f"Fetching campaigns for act_{ACC_ID}...")

url_camp = f"https://graph.facebook.com/v19.0/act_{ACC_ID}/campaigns"
params_camp = {"access_token": TOKEN, "fields": "id,name", "limit": 500}

matched_campaigns = []

while url_camp:
    r = requests.get(url_camp, params=params_camp)
    if r.status_code != 200:
        print(f"Error fetching campaigns: {r.status_code} - {r.text}")
        break
    data = r.json()
    for c in data.get("data", []):
        if "899.43" in c.get("name", ""):
            matched_campaigns.append(c)
            print(f"✅ FOUND CAMPAIGN: {c['name']} (ID: {c['id']})")
    url_camp = data.get("paging", {}).get("next")
    params_camp = {}

if not matched_campaigns:
    print("❌ No campaigns found containing '899.43'. Here are the first 10 campaigns in this account to verify connection:")
    url_test = f"https://graph.facebook.com/v19.0/act_{ACC_ID}/campaigns"
    r = requests.get(url_test, params={"access_token": TOKEN, "fields": "id,name", "limit": 10})
    if r.status_code == 200:
        for c in r.json().get("data", []):
            print(f" - {c['name']}")
    else:
        print(f"Error checking fallback: {r.text}")
    sys.exit(0)

print("\nFetching insights for matched campaigns...")
for camp in matched_campaigns:
    c_id = camp["id"]
    url = f"https://graph.facebook.com/v19.0/{c_id}/insights"
    params = {
        'access_token': TOKEN,
        'fields': 'campaign_id,impressions,cpc,cpm,ctr,spend,actions,video_p75_watched_actions',
        'level': 'campaign',
        'time_range': '{"since":"2026-03-01","until":"2026-03-31"}'
    }
    r = requests.get(url, params=params)
    if r.status_code == 200:
        insight_data = r.json().get('data', [])
        if insight_data:
            print(f"\n📊 Insights for {camp['name']}:")
            print(json.dumps(insight_data[0], indent=2))
        else:
            print(f"\n⚠️ No insights for {camp['name']} in this period (0 impressions/spend).")
    else:
        print(f"\n❌ Error fetching insights: {r.status_code} - {r.text}")
