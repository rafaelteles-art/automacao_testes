import requests
import json

RT_TOKEN = "wB7qY69R0KVU9tl4TBaQ"

def test_rt_fetch(since, until):
    print(f"Buscando relatorio do RedTrack de {since} a {until}...")
    
    url = 'https://api.redtrack.io/report'
    params = {
        'api_key': RT_TOKEN,
        'date_from': since,
        'date_to': until,
        'group': 'rt_ad',
        'limit': 1000,
        'page': 1
    }
    
    page = 1
    matches = []
    
    while True:
        params['page'] = page
        r = requests.get(url, params=params)
        if r.status_code == 200:
            data = r.json()
            if not data: break
            print(f"Page {page}: Fetched {len(data)} rows.")
            for row in data:
                rt_ad = str(row.get('rt_ad', '')).lower()
                if '1192' in rt_ad:
                    matches.append(row)
            if len(data) < 1000: break
            page += 1
        else:
            print(f"Error {r.status_code}: {r.text}")
            break
                
        print(f"Encontrados {len(matches)} resultados contendo '1192':")
        for m in matches[:15]:
            print(json.dumps(m, indent=2))
    else:
        print(f"Error {r.status_code}: {r.text}")

test_rt_fetch('2026-03-01', '2026-03-27')
