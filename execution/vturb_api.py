"""VTurb Analytics API client.

Thin wrapper around https://analytics.vturb.net focused on the two calls the
planilha-filler needs:

  - `list_players()` to populate the UI dropdown.
  - `daily_stats_for_player(player_id, start, end)` to aggregate metrics
    per day. The API requires full datetime (`YYYY-MM-DD HH:MM:SS`).

A "VTurb A/B test" has no dedicated endpoint; it's just a set of variant
player_ids. The caller passes all variants, we fetch each, and the summing
happens in `fill_planilha_by_dates.aggregate_metrics_by_date`.
"""

from __future__ import annotations

from typing import Dict, List

import requests

BASE_URL = "https://analytics.vturb.net"
API_VERSION = "v1"

# VTurb daily stats fields we expose to the planilha. Keys are what we write
# into SUPPORTED_METRICS (prefixed `vturb_`); values are the raw keys returned
# by /sessions/stats_by_day.
VTURB_METRIC_FIELDS: Dict[str, str] = {
    "vturb_viewed": "total_viewed",
    "vturb_viewed_session_uniq": "total_viewed_session_uniq",
    "vturb_viewed_device_uniq": "total_viewed_device_uniq",
    "vturb_started": "total_started",
    "vturb_started_session_uniq": "total_started_session_uniq",
    "vturb_started_device_uniq": "total_started_device_uniq",
    "vturb_finished": "total_finished",
    "vturb_clicked": "total_clicked",
    "vturb_over_pitch": "total_over_pitch",
    "vturb_under_pitch": "total_under_pitch",
    # Ratios — keep raw for reference; aggregator recomputes across players
    # from summed numerators/denominators so multi-player averaging is correct.
    "vturb_play_rate": "play_rate",
    "vturb_over_pitch_rate": "over_pitch_rate",
    "vturb_engagement_rate": "engagement_rate",
}


class VTurbAPI:
    def __init__(self, token: str):
        if not token:
            raise ValueError("VTurb token is required")
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "X-Api-Token": token,
            "X-Api-Version": API_VERSION,
            "Content-Type": "application/json",
        })

    def _post(self, path: str, body: Dict) -> Dict:
        r = self.session.post(f"{BASE_URL}{path}", json=body, timeout=60)
        r.raise_for_status()
        return r.json()

    def _get(self, path: str) -> Dict:
        r = self.session.get(f"{BASE_URL}{path}", timeout=60)
        r.raise_for_status()
        return r.json()

    def list_players(self) -> List[Dict]:
        """Return [{'id', 'name', 'pitch_time', 'duration', 'created_at'}, ...]."""
        data = self._get("/players/list")
        return data if isinstance(data, list) else []

    def daily_stats_for_player(
        self,
        player_id: str,
        date_start: str,
        date_end: str,
    ) -> List[Dict]:
        """Return daily stats rows from /sessions/stats_by_day.

        date_start / date_end can be "YYYY-MM-DD" (we pad to day start/end) or
        full "YYYY-MM-DD HH:MM:SS". Response items have `date_key` plus the
        fields listed in VTURB_METRIC_FIELDS.
        """
        body = {
            "player_id": player_id,
            "start_date": _pad_start(date_start),
            "end_date": _pad_end(date_end),
        }
        data = self._post("/sessions/stats_by_day", body)
        return data if isinstance(data, list) else []


def _pad_start(s: str) -> str:
    return s if len(s) > 10 else f"{s} 00:00:00"


def _pad_end(s: str) -> str:
    return s if len(s) > 10 else f"{s} 23:59:59"
