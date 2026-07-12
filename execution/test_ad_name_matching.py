#!/usr/bin/env python3
"""
Tests for ad-name indexing/matching, which fixes "not all ads being filled".

The test codes (BM188, BM108.1) live in the Facebook AD name, not the campaign
name, so the fill must index ads by name. Run:
    python execution/test_ad_name_matching.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import fill_creative_tests as fct


def _index(*names):
    idx = {}
    for i, n in enumerate(names):
        idx.setdefault(n.lower(), []).append({
            "ad_id": str(i), "ad_name": n,
            "campaign_id": f"c{i}", "campaign_name": f"[LOTTOV7]CA1.X TC{i} ABO 1 - {n}",
        })
    return idx


def test_exact_ad_name_match():
    idx = _index("BM188", "BM200", "BM261")
    hits = fct.match_ads(idx, "bm188")
    assert len(hits) == 1 and hits[0]["ad_name"] == "BM188"
    assert hits[0]["campaign_id"] == "c0"
    print("PASS: exact ad-name match resolves the right campaign")


def test_boundary_not_greedy():
    idx = _index("BM18", "BM188", "BM1880")
    hits = fct.match_ads(idx, "bm188")
    assert len(hits) == 1 and hits[0]["ad_name"] == "BM188", [h["ad_name"] for h in hits]
    print("PASS: BM188 does not match BM18 or BM1880")


def test_variation_exact_then_base():
    # Exact variation present -> resolves to itself only.
    idx = _index("BM108.1", "BM108.2", "BM108.3")
    hits = fct.match_ads(idx, "bm108.2")
    assert len(hits) == 1 and hits[0]["ad_name"] == "BM108.2"

    # Missing variation with only dotted siblings -> NO false cross-match
    # (the base pattern excludes dot-adjacent keys, so it won't grab .1/.2/.3).
    hits2 = fct.match_ads(_index("BM108.1", "BM108.2", "BM108.3"), "bm108.9")
    assert hits2 == [], [h["ad_name"] for h in hits2]

    # Missing variation but a non-dotted base ad exists -> falls back to base.
    hits3 = fct.match_ads(_index("BM108", "BM200"), "bm108.9")
    assert len(hits3) == 1 and hits3[0]["ad_name"] == "BM108", [h["ad_name"] for h in hits3]
    print("PASS: variation matches itself; base fallback only to non-dotted base ad")


def test_fetch_all_ads_parses_campaign():
    payload = {"data": [
        {"id": "1", "name": "BM188", "campaign": {"id": "c1", "name": "[LOTTOV7] ABO - BM"}},
        {"id": "2", "name": "BM189", "campaign": {"id": "c1", "name": "[LOTTOV7] ABO - BM"}},
        {"id": "3", "name": "", "campaign": {"id": "c2", "name": "x"}},  # skipped (no name)
    ], "paging": {}}

    class R:
        status_code = 200
        text = ""
        def json(self): return payload

    orig = fct.requests.get
    fct.requests.get = lambda url, params=None, timeout=None: R()
    try:
        idx = fct.fetch_all_ads(["act_123"], "tok")
        assert set(idx.keys()) == {"bm188", "bm189"}, idx.keys()
        assert idx["bm188"][0]["campaign_id"] == "c1"
        assert idx["bm188"][0]["campaign_name"] == "[LOTTOV7] ABO - BM"
        print("PASS: fetch_all_ads indexes ad names with campaign info")
    finally:
        fct.requests.get = orig


if __name__ == "__main__":
    test_exact_ad_name_match()
    test_boundary_not_greedy()
    test_variation_exact_then_base()
    test_fetch_all_ads_parses_campaign()
    print("\nAll tests passed.")
