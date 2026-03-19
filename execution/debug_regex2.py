import re

def extract_ad_name_from_campaign(campaign_name: str) -> str:
    if not campaign_name: return ""
    match = re.search(r'(?:ABO|CBO)\s+\S+\s*-\s*(.+)$', campaign_name, re.IGNORECASE)
    if match: return match.group(1).strip()
    parts = campaign_name.rsplit(' - ', 1)
    if len(parts) == 2: return parts[1].strip()
    return ""

test_names = [
    "ATIVAR - [LOTTOV7] CA6.DIANA ABO 1 - 100 - 1 [LT899] 14/03/26",
    "ATIVAR - [LOTTOV7]CA6.DIANA CBO 1-1-1 - LT899",
    "ATIVAR - [LOTTOV7]CA6.DIANA ABO 1-100-1 - LT899 - INTERESSES",
    "[LOTTOV7]CA6.DIANA ABO 1-150-1 - [LT899] - 18/03 P2",
    "ATIVAR - [LOTTOV7]CA9.DIANA ABO 1-50-1 - [LT899.72]"
]

for name in test_names:
    print(f"Original: {name}\nExtraced: {extract_ad_name_from_campaign(name)}\n")
