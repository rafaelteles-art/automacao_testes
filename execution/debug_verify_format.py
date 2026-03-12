"""Quick verify: time_range JSON returns the correct $166.53 for LT1010.2"""
import requests

TOKEN = "EAAWDHozjODgBQ0b4ZAZBOZBzGhqi9ZCX0bj8DbmAPnsBfYbEMMZCqMeBMCmLjB2dpzxHvzZC6UQGApi9frZAWyQHPmHZB1hFJa2q3nTNaaDtwHSxqJB5Veeo1CpE9gTYAD3vpJf9vRNNj62z2ebVJ6tD0mKbIzh9DXZCbrnjOHhiAkrcffsEwKcZAuHchAMZBRgi1BjmUIjP2IhfH7O"
ACC = "1277255524217242"

# Method 1: time_range JSON (CORRECT - what we just fixed to)
r1 = requests.get(f"https://graph.facebook.com/v19.0/act_{ACC}/insights", params={
    "access_token": TOKEN,
    "fields": "campaign_name,spend",
    "level": "campaign",
    "time_range": '{"since":"2026-02-01","until":"2026-03-06"}',
    "limit": 500
}, timeout=30)
for c in r1.json().get('data', []):
    if 'lt1010.2' in c['campaign_name'].lower():
        print(f"[time_range JSON] LT1010.2 spend: ${float(c['spend']):.2f}")

# Method 2: date_start/date_end params (OLD - what was broken)
r2 = requests.get(f"https://graph.facebook.com/v19.0/act_{ACC}/insights", params={
    "access_token": TOKEN,
    "fields": "campaign_name,spend",
    "level": "campaign",
    "date_start": "2026-02-01",
    "date_end": "2026-03-06",
    "limit": 500
}, timeout=30)
for c in r2.json().get('data', []):
    if 'lt1010.2' in c['campaign_name'].lower():
        print(f"[date_start/end ] LT1010.2 spend: ${float(c['spend']):.2f}")
