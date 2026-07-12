#!/usr/bin/env python3
"""
Regression test for the "variations fill identically" bug.

Bug: FB metrics (Hook/Body/CPM/CTR/CPC) were fetched at level='campaign', so ad
variations sharing a campaign (BM108.1/.2/.3) all received the same aggregate.
Fix: fetch at level='ad' and select the ad matching the row's exact variation.

Run: python execution/test_variation_metrics.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import fill_creative_tests as fct


# Simulated ad-level insight rows for ONE campaign holding three variations.
_FAKE_AD_API = {
    "data": [
        {"ad_id": "1", "ad_name": "BM108.1", "campaign_id": "c1", "campaign_name": "CAMP",
         "impressions": "1000", "spend": "10",
         "cpm": "10.0", "ctr": "5.0", "cpc": "0.20",
         "actions": [{"action_type": "video_view", "value": "500"}],
         "video_p75_watched_actions": [{"value": "100"}]},
        {"ad_id": "2", "ad_name": "BM108.2", "campaign_id": "c1", "campaign_name": "CAMP",
         "impressions": "2000", "spend": "40",
         "cpm": "20.0", "ctr": "6.0", "cpc": "0.30",
         "actions": [{"action_type": "video_view", "value": "1400"}],
         "video_p75_watched_actions": [{"value": "300"}]},
        {"ad_id": "3", "ad_name": "BM108.3", "campaign_id": "c1", "campaign_name": "CAMP",
         "impressions": "3000", "spend": "90",
         "cpm": "30.0", "ctr": "7.0", "cpc": "0.40",
         "actions": [{"action_type": "video_view", "value": "2700"}],
         "video_p75_watched_actions": [{"value": "900"}]},
    ],
    "paging": {},
}


class _FakeResp:
    status_code = 200
    text = ""

    def json(self):
        return _FAKE_AD_API


def _fake_get(url, params=None, timeout=None):
    return _FakeResp()


def test_ad_level_variations_are_distinct():
    orig = fct.requests.get
    fct.requests.get = _fake_get
    try:
        rows = fct.fetch_fb_ad_insights_for_accounts(["act_1"], "2026-07-01", "2026-07-12", "tok")

        m1 = fct.select_ad_metrics(rows, "bm108.1")
        m2 = fct.select_ad_metrics(rows, "bm108.2")
        m3 = fct.select_ad_metrics(rows, "bm108.3")

        assert m1 and m2 and m3, "all three variations must resolve to an ad"

        # The whole point: the three variations must NOT be identical.
        assert m1["cpm"] != m2["cpm"] != m3["cpm"], "CPM must differ per variation"
        assert m1["hook_rate"] != m2["hook_rate"], "hook_rate must differ per variation"

        # Spot-check exact values (proves per-ad parsing, not aggregate).
        assert abs(m1["cpm"] - 10.0) < 1e-9
        assert abs(m2["cpm"] - 20.0) < 1e-9
        assert abs(m3["cpm"] - 30.0) < 1e-9
        assert abs(m1["hook_rate"] - 0.5) < 1e-9   # 500/1000
        assert abs(m2["hook_rate"] - 0.7) < 1e-9   # 1400/2000
        assert abs(m1["ctr"] - 0.05) < 1e-9        # 5.0 / 100
        assert abs(m1["body_rate"] - 0.1) < 1e-9   # 100/1000
        print("PASS: ad-level variations resolve to distinct metrics")
    finally:
        fct.requests.get = orig


def test_select_prefers_exact_then_boundary():
    rows = [
        {"ad_name": "BM108.1", "cpm": 10.0, "impressions": 1000},
        {"ad_name": "BM108.10", "cpm": 99.0, "impressions": 5000},
    ]
    m = fct.select_ad_metrics(rows, "bm108.1")
    assert m["cpm"] == 10.0, "must not match BM108.10 when looking for BM108.1"

    # Boundary-contains fallback: name embeds the variation with a suffix.
    rows2 = [{"ad_name": "BM108.1 - copy A", "cpm": 42.0, "impressions": 10}]
    m2 = fct.select_ad_metrics(rows2, "bm108.1")
    assert m2 and m2["cpm"] == 42.0
    print("PASS: selection prefers exact and respects word boundaries")


def test_no_match_returns_none():
    rows = [{"ad_name": "BM999.1", "cpm": 1.0, "impressions": 1}]
    assert fct.select_ad_metrics(rows, "bm108.1") is None
    print("PASS: no match returns None")


if __name__ == "__main__":
    test_ad_level_variations_are_distinct()
    test_select_prefers_exact_then_boundary()
    test_no_match_returns_none()
    print("\nAll tests passed.")
