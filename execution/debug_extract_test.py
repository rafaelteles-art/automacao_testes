"""
Test the new extraction logic against all known campaign name formats.
"""
import re

def extract_ad_name_from_campaign_NEW(campaign_name):
    if not campaign_name: return ""
    
    # Priority 1: Ad name in brackets, e.g. [LT899.43]
    bracket_match = re.search(r'\[(LT\d+(?:\.\d+)?|TC\d+(?:\.\d+)?)\]', campaign_name, re.IGNORECASE)
    if bracket_match:
        return bracket_match.group(1).strip()
    
    # Priority 2: Find LT/BT pattern after ABO/CBO section
    # Matches: "... ABO - 1 - 50 - 1 - LT1207 - 24/03/26"
    lt_after_abo = re.search(r'(?:ABO|CBO)\b.*?-\s*((?:LT|BT)\d+(?:\.\d+)?)\s*(?:\s*-|$)', campaign_name, re.IGNORECASE)
    if lt_after_abo:
        return lt_after_abo.group(1).strip()
    
    # Priority 3: Fallback - find any standalone LT/BT pattern (last one in string)
    all_lt = re.findall(r'\b((?:LT|BT)\d+(?:\.\d+)?)\b', campaign_name, re.IGNORECASE)
    if all_lt:
        return all_lt[-1].strip()
    
    # Priority 4: Original ABO/CBO parsing
    match = re.search(r'(?:ABO|CBO)\s+\S+\s*-\s*(.+)$', campaign_name, re.IGNORECASE)
    if match: return match.group(1).strip()
    
    # Priority 5: rsplit fallback
    parts = campaign_name.rsplit(' - ', 1)
    if len(parts) == 2: return parts[1].strip()
    return ""

# Test cases
test_cases = [
    # New format (no brackets around LT)
    ("[LOTTOV7]CA5.SOMEYUM - TC260 - ABO - 1 - 50 - 1 - LT1207 - 24/03/26", "LT1207"),
    ("[LOTTOV7]CA5.SOMEYUM - TC260 - ABO - 1 - 50 - 1 - LT581.52 - 24/03/26", "LT581.52"),
    ("[LOTTOV7]CA5.SOMEYUM - TC262 - ABO - 1 - 50 - 1 - LT1084.1 - 27/03/26", "LT1084.1"),
    ("[LOTTOV7]CA5.DIGITAL - TC261 - ABO - 1 - 50 - 1 - LT1228 - 25/03/26", "LT1228"),
    
    # Old format with brackets
    ("ATIVAR - [LOTTOV7] CA5.SOMEYUM TC252 ABO 1 - 50 - 1 [LT899.43] 15/03/26", "LT899.43"),
    ("ATIVAR - [LOTTOV7]CA6.DIANA ABO 1-100-1 - LT899 - INTERESSES", "LT899"),
    ("ATIVAR - [LOTTOV7]CA6.DIANA CBO 1-1-1 - LT899", "LT899"),
    ("[LOTTOV7]CA6.DIANA ABO 1-150-1 - [LT899] - 18/03 P2", "LT899"),
    ("[LOTTOV7]CA9.DIANA TC248 ABO 1-50-1 - [LT899.72]", "LT899.72"),
    
    # Edge cases
    ("ATIVAR - [LOTTOV7]CA6.DIANA ABO 1-50-1 - LT899.9", "LT899.9"),
    ("[LOTTOV7]CA9.DIANA PE ABO 1-150-1 [LT899.17]", "LT899.17"),
]

print("Testing new extraction logic:")
print(f"{'Campaign Name':<75} | {'Expected':<12} | {'Got':<12} | {'OK?'}")
print("-" * 115)

all_ok = True
for campaign, expected in test_cases:
    result = extract_ad_name_from_campaign_NEW(campaign)
    ok = result.lower() == expected.lower()
    if not ok: all_ok = False
    status = "PASS" if ok else "FAIL"
    print(f"{campaign[:74]:<75} | {expected:<12} | {result:<12} | {status}")

print(f"\n{'ALL TESTS PASSED!' if all_ok else 'SOME TESTS FAILED!'}")
