import re

def find_best_match(search_term, keys):
    best_key = ""
    best_score = 0
    base_term = search_term.split('.')[0] if '.' in search_term else search_term
    
    pattern_exact = r'(?<![a-zA-Z0-9_\.])' + re.escape(search_term) + r'(?![a-zA-Z0-9_\.])'
    pattern_base = r'(?<![a-zA-Z0-9_\.])' + re.escape(base_term) + r'(?![a-zA-Z0-9_\.])'
    
    for key in keys:
        match_valid = False
        match_score = 0

        if re.search(pattern_exact, key):
            match_valid = True
            match_score = 3
        elif key in search_term:
            match_valid = True
            match_score = 2
        elif base_term != search_term and re.search(pattern_base, key):
            match_valid = True
            match_score = 1
            
        if match_valid:
            if match_score > best_score or (match_score == best_score and len(key) > len(best_key)):
                best_key = key
                best_score = match_score
                
    return best_key, best_score

keys = [
    "[lt899.17]",
    "[lt899.72]",
    "[lt899] - 18/03 p2",
    "lt899",
    "lt8990 - test",
    "lt899.43 - specific"
]

print("Match for lt899.43:", find_best_match("lt899.43", ["[lt899] - 18/03 p2", "lt899", "[lt899.17]"]))
print("Match for lt899.43 with exact:", find_best_match("lt899.43", keys))
print("Match for lt899:", find_best_match("lt899", keys))
