import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facebook_redtrack_importer_v2 import FacebookAdsAPI

FB_TOKEN = "EAAWDHozjODgBRYSLNrJKwCXTvowH12ayUGzsp7bZBqbHZBGFrQcaZAXpFwgiq3byQ2cg6ZBHFZCLn8hCXZAN8ZB1BzjQZBbtEP8jgdGzcpdNiFfgXZCKtTzNVQZAAYclfzwEyLOfsL3eazEIe22X5PQnJ6qUSZCn266p1Oi0eEQ84yFMh7tvg6SblkNFlMgZAxlwXDji"
ACCOUNT_ID = "542987171356461"
DATE_START = "2026-02-01"
DATE_END = "2026-03-03"

def test_api():
    print("Initializing API...")
    api = FacebookAdsAPI(FB_TOKEN)
    print("Starting fetch...")
    
    start_time = time.time()
    data = api.get_ad_insights(ACCOUNT_ID, DATE_START, DATE_END)
    end_time = time.time()
    
    print(f"Fetch completed in {end_time - start_time:.2f} seconds.")
    print(f"Total records fetched: {len(data)}")

if __name__ == "__main__":
    test_api()
