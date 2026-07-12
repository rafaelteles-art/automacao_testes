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


def test_build_ad_index_from_insight_rows():
    rows = [
        {"ad_id": "1", "ad_name": "BM188", "campaign_id": "c1", "campaign_name": "[LOTTOV7] ABO - BM"},
        {"ad_id": "2", "ad_name": "BM189", "campaign_id": "c1", "campaign_name": "[LOTTOV7] ABO - BM"},
        {"ad_id": "1", "ad_name": "BM188", "campaign_id": "c1", "campaign_name": "[LOTTOV7] ABO - BM"},  # dup (2nd range)
        {"ad_id": "3", "ad_name": "", "campaign_id": "c2", "campaign_name": "x"},  # skipped (no name)
    ]
    idx = fct.build_ad_index(rows)
    assert set(idx.keys()) == {"bm188", "bm189"}, idx.keys()
    assert len(idx["bm188"]) == 1, "same ad_id across ranges must be deduped"
    assert idx["bm188"][0]["campaign_id"] == "c1"
    assert idx["bm188"][0]["campaign_name"] == "[LOTTOV7] ABO - BM"
    print("PASS: build_ad_index indexes and dedupes insight rows")


def test_rt_report_cache_reuses_pull():
    calls = {"n": 0}
    payload = [{"rt_ad": "BM188", "convtype2": 1, "convtype1": 2, "cost": 10.0, "roas": 1.5},
               {"rt_ad": "BM189", "convtype2": 0, "convtype1": 0, "cost": 5.0, "roas": 0}]

    class R:
        status_code = 200
        text = ""
        def json(self): return payload

    orig = fct.requests.get
    fct.requests.get = lambda url, params=None, timeout=None: (calls.__setitem__("n", calls["n"] + 1), R())[1]
    fct._rt_report_cache.clear()
    try:
        a = fct.fetch_rt_for_ad("bm188", "2026-07-01", "2026-07-12", "tok")
        b = fct.fetch_rt_for_ad("bm189", "2026-07-01", "2026-07-12", "tok")
        assert a["cost"] == 10.0 and a["vendas"] == 1 and a["ic"] == 2
        assert b["cost"] == 5.0
        # Both rows have data on rt_ad (no sub4 fallback) and share the same
        # date range, so a single HTTP pull serves them all — and a third row
        # on the same range adds NO new calls.
        n_after_two = calls["n"]
        fct.fetch_rt_for_ad("bm188", "2026-07-01", "2026-07-12", "tok")
        assert calls["n"] == n_after_two, f"cache miss: {calls['n']} != {n_after_two}"
        assert n_after_two == 1, f"expected 1 cached HTTP pull, got {n_after_two}"
        print("PASS: RedTrack report cached per range; repeat rows add no HTTP calls")
    finally:
        fct.requests.get = orig
        fct._rt_report_cache.clear()


def test_derive_auto_date_start():
    def row(n=26, **cols):
        r = [""] * n
        for idx, v in cols.items():
            r[int(idx)] = v
        return r

    values = [
        row(),  # R1 section header
        row(),  # R2 column header
        # TESTES: name in B(1), date in C(2), status in M(12)
        row(**{"1": "BDM05", "2": "18/04/2026", "12": "TESTE"}),
        row(**{"1": "BM188", "2": "10/07/2026", "12": "TESTE"}),
        row(**{"1": "BM50", "2": "01/03/2026", "12": "VALIDADO"}),   # not TESTE -> ignored
        # PRÉ-ESCALA: name in O(14), date in P(15), status in V(21)
        row(**{"14": "BM82", "15": "02/06/2026", "21": "TESTE"}),
    ]
    got = fct.derive_auto_date_start(values, 3, "2026-07-01")
    assert got == "2026-04-18", got  # oldest TESTE date wins (VALIDADO ignored)

    # No TESTE row with a date -> fallback
    values2 = [row(), row(), row(**{"1": "BM1", "12": "TESTE"})]
    assert fct.derive_auto_date_start(values2, 3, "2026-07-01") == "2026-07-01"
    print("PASS: auto start date = oldest TESTE date; fallback when none")


if __name__ == "__main__":
    test_exact_ad_name_match()
    test_boundary_not_greedy()
    test_variation_exact_then_base()
    test_build_ad_index_from_insight_rows()
    test_rt_report_cache_reuses_pull()
    test_derive_auto_date_start()
    print("\nAll tests passed.")
