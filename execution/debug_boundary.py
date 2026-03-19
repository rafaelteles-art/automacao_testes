import re

ad_names = ["lt899", "lt899.43"]
keys = [
    "[lt899.72]",
    "[lt899] - p2",
    "100 - 1 [lt899] 14/03/26",
    "[lt899.43] - interesses",
    "lt8990",
    "lt899.4"
]

for search_term in ad_names:
    print(f"--- MATCHING for {search_term} ---")
    for key in keys:
        if search_term == key:
            print(f"EXACT: {key}")
        elif search_term in key:
            pattern = r'(?<![a-zA-Z0-9_])' + re.escape(search_term) + r'(?![a-zA-Z0-9_])'
            if re.search(pattern, key):
                print(f"BOUNDARY MATCH: {key}")
            else:
                print(f"FAIL BOUNDARY: {key}")
