import requests
import json
import sys
import argparse

# RedTrack report puller by ad (rt_ad).
#
# Usage:
#   python execution/check_redtrack_ads.py --ads HG01,HG01.1,HG02 --date-from 2026-06-23
#   python execution/check_redtrack_ads.py --ads-file ads.txt --date-from 2026-06-23 --date-to 2026-07-10
#
# Defaults keep the original behavior (hardcoded ad list) if no --ads/--ads-file given.

DEFAULT_ADS = ["LT1017.7", "LT1010.2", "LT899.22", "LT1033.2", "LT1011.4",
               "LT899.32", "LT899.33", "LT1034.4", "LT1069", "LT1070"]

# App-wide default RedTrack token (same as facebook_redtrack_importer_v2.py fallback)
DEFAULT_API_KEY = "wB7qY69R0KVU9tl4TBaQ"


def parse_args():
    p = argparse.ArgumentParser(description="Pull RedTrack /report data grouped by rt_ad.")
    p.add_argument("--ads", help="Comma-separated ad codes (rt_ad), e.g. HG01,HG01.1,HG02")
    p.add_argument("--ads-file", help="File with one ad code per line")
    p.add_argument("--date-from", default="2024-01-01", help="YYYY-MM-DD (default 2024-01-01)")
    p.add_argument("--date-to", default="2026-12-31", help="YYYY-MM-DD (default 2026-12-31)")
    p.add_argument("--api-key", default=DEFAULT_API_KEY)
    p.add_argument("--json", action="store_true", help="Dump raw JSON instead of the table")
    return p.parse_args()


def resolve_ads(args):
    if args.ads_file:
        with open(args.ads_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    if args.ads:
        return [a.strip() for a in args.ads.split(",") if a.strip()]
    return DEFAULT_ADS


def main():
    args = parse_args()
    ads = resolve_ads(args)
    ads_str = ",".join(ads)

    url = "https://api.redtrack.io/report"
    params = {
        'api_key': args.api_key,
        'date_from': args.date_from,
        'date_to': args.date_to,
        'group': 'rt_ad',
        'rt_ad': ads_str,
        'limit': 5000,
    }

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Erro na requisicao: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not data:
        print(f"Nenhum dado retornado para esses ads no periodo {args.date_from} -> {args.date_to}.")
        print(f"Ads consultados: {ads_str}")
        sys.exit(0)

    returned_ids = {row.get("rt_ad") for row in data}
    print(f"Periodo: {args.date_from} -> {args.date_to}")
    print(f"Encontrados dados para {len(data)} anuncios:")
    print("-" * 95)
    print(f"{'Anuncio':<12} | {'Gasto (cost)':>14} | {'Vendas (ct2)':>12} | {'IC (ct1)':>9} | {'Receita':>14}")
    print("-" * 95)

    tot_cost = tot_rev = 0.0
    tot_sales = tot_ic = 0
    for row in sorted(data, key=lambda r: str(r.get("rt_ad", ""))):
        ad_id = row.get("rt_ad", "Desconhecido")
        sales = row.get("convtype2", 0) or 0
        ic = row.get("convtype1", 0) or 0
        revenue = row.get("total_revenue", 0.0) or 0.0
        spend = row.get("cost", 0.0) or 0.0
        tot_cost += spend
        tot_rev += revenue
        tot_sales += sales
        tot_ic += ic
        print(f"{ad_id:<12} | {spend:>14.2f} | {sales:>12} | {ic:>9} | {revenue:>14.2f}")

    print("-" * 95)
    print(f"{'TOTAL':<12} | {tot_cost:>14.2f} | {tot_sales:>12} | {tot_ic:>9} | {tot_rev:>14.2f}")

    missing = [a for a in ads if a not in returned_ids]
    if missing:
        print()
        print(f"Sem dados no periodo ({len(missing)}): {', '.join(missing)}")


if __name__ == "__main__":
    main()
