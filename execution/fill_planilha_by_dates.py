#!/usr/bin/env python3
"""Fill a Google Sheet by date-columns from associated RedTrack campaigns.

Flow:
  1. Read row 1 of the configured tab.
  2. Identify columns whose row-1 value is a date (DD/MM/YYYY, YYYY-MM-DD,
     a real datetime, or an Excel serial number).
  3. For each associated RedTrack campaign, fetch /report?group=date for the
     full date range covered by the detected columns.
  4. Sum each metric (cost, convtype1, convtype2, revenue, roas, clicks, ...)
     per date across all associated campaigns.
  5. For each (row, metric) entry in the planilha's `metric_rows` mapping,
     write the summed value into the corresponding (row, date-column) cell.

If `metric_rows` is empty, no writes happen — the function only returns the
preview payload so the UI can show what would be filled.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, date, timedelta
from typing import Callable, Dict, List, Optional, Tuple

import gspread

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from facebook_redtrack_importer_v2 import RedTrackAPI
from vturb_api import VTURB_METRIC_FIELDS, VTurbAPI
import label_map_store


# Metrics we expose in the UI. Keep the keys aligned with RedTrack /report
# field names so summing is a straight dict[k] += value.
#
# Summable (counts/money) — somar entre campanhas faz sentido.
# Ratios (roas, cpa, cpc, cr, ctr, aov, *_rate) são médias ponderadas e NÃO
# somáveis diretamente; expomos mesmo assim para o usuário escolher, mas
# `fill_sheet` está escrevendo a soma crua (para ratios, use só quando houver
# uma campanha única associada à planilha).
_CONV_TYPES = [f"convtype{i}" for i in range(1, 41)]
_REVENUE_TYPES = [f"revenuetype{i}" for i in range(1, 41)]

SUPPORTED_METRICS: List[str] = [
    # Volume / dinheiro (somáveis)
    "cost",
    "revenue",
    "total_revenue",
    "profit",
    "clicks",
    "unique_clicks",
    "impressions",
    "impressions_visible",
    "lp_clicks",
    "lp_views",
    "unique_lp_clicks",
    "prelp_clicks",
    "prelp_views",
    "unique_prelp_clicks",
    "ok",
    "other",
    "approved",
    "declined",
    "pending",
    "total_conversions",
    "conversions",
    "transactions",
    # Fraud buckets
    "attribution",
    "baddevice",
    "blacklist",
    "datacenter",
    # Ratios / médias (não somáveis — cuidado)
    "roas",
    "roi",
    "cpa",
    "cpc",
    "cpt",
    "aov",
    "cr",
    "ctr",
    "epc",
    "epc_lp",
    "epc_roi",
    "epuc",
    "epv",
    *_CONV_TYPES,
    *_REVENUE_TYPES,
    # VTurb (vide vturb_api.VTURB_METRIC_FIELDS). Somáveis entre variantes de
    # A/B test, exceto as _rate (recomputadas via numerador/denominador).
    *VTURB_METRIC_FIELDS.keys(),
    # Audiência absoluta que chegou ao pitch (a "Audiência do Pitch" do
    # dashboard). NÃO vem de stats_by_day — é derivada da curva de retenção
    # em vturb_api.pitch_audience_for_day(). Somável entre variantes de A/B test.
    "vturb_pitch_audience",
]


def _try_parse_date(value) -> Optional[date]:
    """Best-effort coercion of a header cell into a date.

    Handles datetime objects, ISO strings, BR strings (DD/MM/YYYY), and Excel
    serial numbers. Returns None when the cell isn't a date.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        # Excel serial date (days since 1899-12-30)
        try:
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
        except Exception:
            return None
    s = str(value).strip()
    if not s:
        return None
    fmts = ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y/%m/%d")
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def detect_date_columns(header_row: List) -> List[Tuple[int, date]]:
    """Return [(col_index_1based, date), ...] for every date cell in row 1."""
    columns: List[Tuple[int, date]] = []
    for idx, cell in enumerate(header_row, start=1):
        d = _try_parse_date(cell)
        if d is not None:
            columns.append((idx, d))
    return columns


def aggregate_metrics_by_date(
    rt_api: RedTrackAPI,
    campaign_ids: List[str],
    date_start: str,
    date_end: str,
    progress: Optional[Callable[[str], None]] = None,
    vturb_api: Optional[VTurbAPI] = None,
    vturb_player_ids: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """Sum each supported metric per date across campaigns and VTurb players.

    Returns: {"2026-04-15": {"cost": 123.4, "convtype2": 5, "vturb_viewed": 80, ...}, ...}
    """
    totals: Dict[str, Dict[str, float]] = {}
    for cid in campaign_ids:
        if progress:
            progress(f"Buscando RedTrack /report da campanha {cid}...")
        rows = rt_api.daily_report_for_campaign(cid, date_start, date_end)
        for row in rows:
            day_raw = row.get("date")
            if not day_raw:
                continue
            day = str(day_raw)[:10]  # accepts "2026-04-15" or "2026-04-15T00:00:00Z"
            bucket = totals.setdefault(day, {m: 0.0 for m in SUPPORTED_METRICS})
            for m in SUPPORTED_METRICS:
                try:
                    bucket[m] += float(row.get(m, 0) or 0)
                except (TypeError, ValueError):
                    continue

    if vturb_api and vturb_player_ids:
        # Accumulators for engagement_rate weighted average (by total_viewed).
        engagement_num: Dict[str, float] = {}
        engagement_den: Dict[str, float] = {}
        # Per-player pitch_time/duration, needed to derive the pitch audience
        # from the retention curve. One /players/list call, reused for all.
        player_meta: Dict[str, Dict] = {}
        try:
            for p in vturb_api.list_players():
                player_meta[p.get("id")] = p
        except Exception:
            player_meta = {}
        for pid in vturb_player_ids:
            if progress:
                progress(f"Buscando VTurb /sessions/stats_by_day do player {pid}...")
            rows = vturb_api.daily_stats_for_player(pid, date_start, date_end)
            meta = player_meta.get(pid, {})
            pitch_time = int(meta.get("pitch_time") or 0)
            video_duration = int(meta.get("duration") or 0)
            for row in rows:
                day_raw = row.get("date_key") or row.get("day")
                if not day_raw:
                    continue
                day = str(day_raw)[:10]
                bucket = totals.setdefault(day, {m: 0.0 for m in SUPPORTED_METRICS})
                # Sum raw counts; ratios get re-derived after.
                for metric_key, raw_field in VTURB_METRIC_FIELDS.items():
                    if metric_key.endswith("_rate"):
                        continue
                    try:
                        bucket[metric_key] += float(row.get(raw_field, 0) or 0)
                    except (TypeError, ValueError):
                        continue
                # Weighted engagement_rate accumulators.
                try:
                    viewed = float(row.get("total_viewed", 0) or 0)
                    er = float(row.get("engagement_rate", 0) or 0)
                    engagement_num[day] = engagement_num.get(day, 0.0) + er * viewed
                    engagement_den[day] = engagement_den.get(day, 0.0) + viewed
                except (TypeError, ValueError):
                    pass
                # Pitch audience: only worth a call on days that had plays.
                # Summed across A/B-test variants into the same day bucket.
                started = float(row.get("total_started", 0) or 0)
                if started > 0 and pitch_time > 0 and video_duration > 0:
                    try:
                        bucket["vturb_pitch_audience"] += vturb_api.pitch_audience_for_day(
                            pid, pitch_time, video_duration, day
                        )
                    except Exception:
                        pass

        # Derive ratios from summed counts (more correct than averaging rates).
        #   play_rate = total_started / total_viewed * 100
        #   over_pitch_rate = total_over_pitch / total_started * 100
        #   engagement_rate = weighted avg by total_viewed
        for day, bucket in totals.items():
            viewed = bucket.get("vturb_viewed", 0) or 0
            started = bucket.get("vturb_started", 0) or 0
            over_pitch = bucket.get("vturb_over_pitch", 0) or 0
            bucket["vturb_play_rate"] = (started / viewed * 100) if viewed else 0.0
            bucket["vturb_over_pitch_rate"] = (over_pitch / started * 100) if started else 0.0
            den = engagement_den.get(day, 0.0)
            bucket["vturb_engagement_rate"] = (engagement_num.get(day, 0.0) / den) if den else 0.0

    return totals


def build_preview(
    config: Dict,
    rt_token: str,
    gc: gspread.Client,
    progress: Optional[Callable[[str], None]] = None,
    filter_start: Optional[date] = None,
    filter_end: Optional[date] = None,
    vturb_token: Optional[str] = None,
) -> Dict:
    """Read the sheet, detect date columns, fetch+aggregate metrics.

    If `filter_start`/`filter_end` are provided, only date-columns whose header
    date falls inside [start, end] are processed. Returns a dict with:
    date_columns, totals_by_date, campaign_ids, vturb_player_ids, range.
    Does NOT write.
    """
    if progress:
        progress("Abrindo planilha...")
    sh = gc.open_by_url(config["g_url"])
    ws = sh.worksheet(config["aba"])
    header_row = ws.row_values(1)
    col_a = ws.col_values(1)
    resolved_rows = label_map_store.resolve_rows(col_a)
    date_cols = detect_date_columns(header_row)
    if filter_start:
        date_cols = [(c, d) for c, d in date_cols if d >= filter_start]
    if filter_end:
        date_cols = [(c, d) for c, d in date_cols if d <= filter_end]
    if not date_cols:
        return {
            "date_columns": [],
            "totals_by_date": {},
            "campaign_ids": config.get("campaign_ids", []),
            "vturb_player_ids": config.get("vturb_player_ids", []),
            "resolved_rows": resolved_rows,
            "range": None,
        }

    dates_only = [d for _, d in date_cols]
    date_start = min(dates_only).strftime("%Y-%m-%d")
    date_end = max(dates_only).strftime("%Y-%m-%d")

    rt_api = RedTrackAPI(rt_token)
    vturb_player_ids = config.get("vturb_player_ids", []) or []
    vturb_api = VTurbAPI(vturb_token) if (vturb_token and vturb_player_ids) else None

    totals = aggregate_metrics_by_date(
        rt_api,
        config.get("campaign_ids", []),
        date_start,
        date_end,
        progress=progress,
        vturb_api=vturb_api,
        vturb_player_ids=vturb_player_ids,
    )
    return {
        "date_columns": [(c, d.strftime("%Y-%m-%d")) for c, d in date_cols],
        "totals_by_date": totals,
        "campaign_ids": config.get("campaign_ids", []),
        "vturb_player_ids": vturb_player_ids,
        "resolved_rows": resolved_rows,
        "range": (date_start, date_end),
    }


def fill_sheet(
    config: Dict,
    rt_token: str,
    gc: gspread.Client,
    progress: Optional[Callable[[str], None]] = None,
    filter_start: Optional[date] = None,
    filter_end: Optional[date] = None,
    vturb_token: Optional[str] = None,
) -> Dict:
    """Apply the metric_rows mapping to each detected date column.

    Returns: {"updates": int, "preview": {...}, "skipped_dates": [...]}.
    """
    preview = build_preview(
        config, rt_token, gc, progress=progress,
        filter_start=filter_start, filter_end=filter_end,
        vturb_token=vturb_token,
    )
    resolved_rows: Dict[int, str] = preview.get("resolved_rows") or {}
    if not resolved_rows:
        return {"updates": 0, "preview": preview, "skipped_dates": [],
                "note": "Nenhuma linha da coluna A bateu com o dicionário global de labels — nada foi escrito."}

    sh = gc.open_by_url(config["g_url"])
    ws = sh.worksheet(config["aba"])

    cells: List[gspread.Cell] = []
    skipped: List[str] = []
    for col_idx, day in preview["date_columns"]:
        bucket = preview["totals_by_date"].get(day)
        if not bucket:
            skipped.append(day)
            continue
        for row_idx, metric in resolved_rows.items():
            value = bucket.get(metric, 0.0)
            cells.append(gspread.Cell(row=row_idx, col=col_idx, value=round(float(value), 4)))

    if cells:
        if progress:
            progress(f"Gravando {len(cells)} células na planilha...")
        ws.update_cells(cells, value_input_option="USER_ENTERED")

    return {"updates": len(cells), "preview": preview, "skipped_dates": skipped}
