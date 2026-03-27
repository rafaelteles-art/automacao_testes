import requests

RT_TOKEN = "wB7qY69R0KVU9tl4TBaQ"
groups_to_test = ['rt_ad', 'rt_cmp', 'sub1', 'sub2', 'sub3', 'sub4', 'sub5']

for group in groups_to_test:
    url = 'https://api.redtrack.io/report'
    params = {
        'api_key': RT_TOKEN,
        'date_from': '2026-03-01',
        'date_to': '2026-03-27',
        'group': group,
        'limit': 2000,
        'page': 1
    }
    
    r = requests.get(url, params=params)
    if r.status_code == 200:
        data = r.json()
        matches = 0
        names = []
        for row in data:
            val = str(row.get(group, '')).lower()
            if '1192' in val:
                matches += 1
                if len(names) < 3: names.append(val)
                
        if matches > 0:
            print(f"FOUND: GROUP {group} tem {matches} matches para '1192' (Ex: {names})")
        else:
            print(f"NOT FOUND: GROUP {group} sem matches.")
    else:
        print(f"Erro no grupo {group}: {r.status_code}")
