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


def test_merge_insight_rows_rebuilds_rates():
    # Same ad split across two half-ranges; merged must equal a single sweep.
    half1 = {"ad_id": "1", "ad_name": "BM188", "campaign_id": "c1", "campaign_name": "X",
             "impressions": 1000.0, "spend": 10.0, "cpm": 10.0, "cpc": 0.2,
             "ctr": 0.05, "hook_rate": 0.5, "body_rate": 0.1}
    half2 = {"ad_id": "1", "ad_name": "BM188", "campaign_id": "c1", "campaign_name": "X",
             "impressions": 3000.0, "spend": 90.0, "cpm": 30.0, "cpc": 0.6,
             "ctr": 0.05, "hook_rate": 0.9, "body_rate": 0.3}
    merged = fct.merge_insight_rows([half1, half2])
    assert len(merged) == 1
    m = merged[0]
    assert m["impressions"] == 4000.0 and m["spend"] == 100.0
    assert abs(m["cpm"] - 25.0) < 1e-9            # 100/4000*1000
    assert abs(m["ctr"] - 0.05) < 1e-9            # (50+150)/4000
    assert abs(m["cpc"] - 0.5) < 1e-9             # 100/200 clicks
    assert abs(m["hook_rate"] - 0.8) < 1e-9       # (500+2700)/4000
    assert abs(m["body_rate"] - 0.25) < 1e-9      # (100+900)/4000
    print("PASS: merge_insight_rows rebuilds rates exactly from split ranges")


def test_adaptive_split_on_too_much_data():
    import json as _json

    def span_days(params):
        tr = _json.loads(params["time_range"])
        d0 = fct.datetime.datetime.strptime(tr["since"], "%Y-%m-%d").date()
        d1 = fct.datetime.datetime.strptime(tr["until"], "%Y-%m-%d").date()
        return (d1 - d0).days

    class TooBig:
        status_code = 500
        text = '{"error":{"code":1,"message":"Please reduce the amount of data"}}'
        def json(self): return {"error": {"code": 1, "message": "Please reduce the amount of data you're asking for, then retry your request"}}

    class Ok:
        status_code = 200
        text = ""
        def json(self):
            return {"data": [{"ad_id": "1", "ad_name": "BM188", "campaign_id": "c1",
                              "campaign_name": "X", "impressions": "1000", "spend": "10",
                              "cpm": "10.0", "ctr": "5.0", "cpc": "0.20"}], "paging": {}}

    def fake_get(url, params=None, timeout=None):
        # Refuse windows longer than 3 days regardless of page size.
        if params and "time_range" in params and span_days(params) > 3:
            return TooBig()
        return Ok()

    orig = fct.requests.get
    fct.requests.get = fake_get
    try:
        # 7-day window -> refused -> limit shrink (still refused) -> split into
        # sub-windows of <=3 days -> leaves merged into ONE row per ad.
        rows = fct.fetch_fb_ad_insights_for_accounts(["act_1"], "2026-07-01", "2026-07-08", "tok")
        assert len(rows) == 1, [r.get("ad_name") for r in rows]
        assert rows[0]["ad_name"] == "BM188"
        assert rows[0]["spend"] == 20.0, rows[0]["spend"]  # 2 leaf windows x 10
        assert rows[0]["impressions"] == 2000.0
        assert abs(rows[0]["cpm"] - 10.0) < 1e-9  # rate preserved across merge
        print("PASS: adaptive fetch splits refused windows and merges per ad")
    finally:
        fct.requests.get = orig


if __name__ == "__main__":
    test_exact_ad_name_match()
    test_boundary_not_greedy()
    test_variation_exact_then_base()
    test_build_ad_index_from_insight_rows()
    test_rt_report_cache_reuses_pull()
    test_derive_auto_date_start()
    test_merge_insight_rows_rebuilds_rates()
    test_adaptive_split_on_too_much_data()
    print("\nAll tests passed.")
