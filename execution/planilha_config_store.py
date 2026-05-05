#!/usr/bin/env python3
"""Persistent configuration store for the "Preencher por Campanhas" feature.

Each entry associates a Google Sheet (URL + tab) with one or more RedTrack
campaign IDs, and optionally a row->metric mapping describing which metric the
user wants written into each row under a date column.

Backends:
  - Google Sheets (1 row per planilha) when ``configure(gc, sheet_url)`` is
    called. Each save touches a single row, so concurrent inserts/edits from
    multiple users do not collide unless they target the same planilha at the
    same instant.
  - Local JSON file (legacy) otherwise. Used for local dev / first-time setup.

Streamlit Cloud has an ephemeral filesystem — the local JSON does NOT survive
restarts, which is why production must use the Sheets backend.

Sheets tab schema (column order matters):
    id | nome | g_url | aba | campaign_ids | metric_rows | vturb_player_ids
  - campaign_ids / vturb_player_ids: comma-separated strings.
  - metric_rows: JSON-encoded object (kept for backward compat with old data).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Dict, List, Optional

import gspread

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_DIR = os.path.join(_PROJECT_ROOT, "config")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "planilhas.json")

_TAB = "planilhas"
_HEADERS = ["id", "nome", "g_url", "aba", "campaign_ids", "metric_rows", "vturb_player_ids"]
_LAST_COL_LETTER = chr(ord("A") + len(_HEADERS) - 1)  # "G"

_CACHE_TTL_SEC = 30
_cache: Dict = {"data": None, "ts": 0.0}
_seed_state: Dict = {"done": False}

_gc: Optional[gspread.Client] = None
_sheet_url: Optional[str] = None


def configure(gc: gspread.Client, sheet_url: str) -> None:
    """Switch to the Google Sheets backend. Call once at app startup."""
    global _gc, _sheet_url
    _gc = gc
    _sheet_url = sheet_url
    _invalidate_cache()


def _is_sheets_backend() -> bool:
    return _gc is not None and bool(_sheet_url)


def _invalidate_cache() -> None:
    _cache["data"] = None
    _cache["ts"] = 0.0


def _get_ws() -> gspread.Worksheet:
    sh = _gc.open_by_url(_sheet_url)
    try:
        ws = sh.worksheet(_TAB)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=_TAB, rows=1000, cols=len(_HEADERS))
        ws.update(f"A1:{_LAST_COL_LETTER}1", [_HEADERS])
        return ws
    first_row = ws.row_values(1)
    if first_row[: len(_HEADERS)] != _HEADERS:
        ws.update(f"A1:{_LAST_COL_LETTER}1", [_HEADERS])
    return ws


def _row_to_dict(row: List[str]) -> Dict:
    pad = list(row) + [""] * (len(_HEADERS) - len(row))
    rec = dict(zip(_HEADERS, pad))
    rec["campaign_ids"] = [c.strip() for c in (rec.get("campaign_ids") or "").split(",") if c.strip()]
    rec["vturb_player_ids"] = [c.strip() for c in (rec.get("vturb_player_ids") or "").split(",") if c.strip()]
    raw = rec.get("metric_rows") or ""
    try:
        rec["metric_rows"] = json.loads(raw) if raw else {}
    except Exception:
        rec["metric_rows"] = {}
    return rec


def _dict_to_row(rec: Dict) -> List[str]:
    return [
        rec.get("id", ""),
        rec.get("nome", ""),
        rec.get("g_url", ""),
        rec.get("aba", ""),
        ",".join(rec.get("campaign_ids", []) or []),
        json.dumps(rec.get("metric_rows", {}) or {}, ensure_ascii=False),
        ",".join(rec.get("vturb_player_ids", []) or []),
    ]


def _ensure_local_file() -> None:
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    if not os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"planilhas": []}, f, ensure_ascii=False, indent=2)


def _load_from_file() -> List[Dict]:
    _ensure_local_file()
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("planilhas", [])


def _save_to_file(items: List[Dict]) -> None:
    _ensure_local_file()
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"planilhas": items}, f, ensure_ascii=False, indent=2)


def _maybe_seed_from_local_json(ws: gspread.Worksheet, existing_rows: List[List[str]]) -> bool:
    """If the Sheets tab is empty (just headers) but a local JSON has entries,
    push them up. Runs at most once per process. Returns True if seeded.
    """
    if _seed_state.get("done"):
        return False
    _seed_state["done"] = True
    try:
        if len(existing_rows) > 1:  # already has data beyond headers
            return False
        if not os.path.exists(_CONFIG_PATH):
            return False
        local_items = _load_from_file()
        if not local_items:
            return False
        rows_to_add = [_dict_to_row(it) for it in local_items]
        ws.append_rows(rows_to_add, value_input_option="RAW")
        return True
    except Exception:
        return False  # seeding is best-effort


def load_all(force_reload: bool = False) -> List[Dict]:
    if not _is_sheets_backend():
        return _load_from_file()

    now = time.time()
    if (
        not force_reload
        and _cache["data"] is not None
        and (now - _cache["ts"]) < _CACHE_TTL_SEC
    ):
        return _cache["data"]

    ws = _get_ws()
    rows = ws.get_all_values()
    if _maybe_seed_from_local_json(ws, rows):
        rows = ws.get_all_values()
    data = [_row_to_dict(r) for r in rows[1:] if any((c or "").strip() for c in r)] if rows else []
    _cache["data"] = data
    _cache["ts"] = now
    return data


def get(planilha_id: str) -> Optional[Dict]:
    for p in load_all():
        if p.get("id") == planilha_id:
            return p
    return None


def upsert(
    nome: str,
    g_url: str,
    aba: str,
    campaign_ids: List[str],
    metric_rows: Optional[Dict[str, str]] = None,
    planilha_id: Optional[str] = None,
    vturb_player_ids: Optional[List[str]] = None,
) -> Dict:
    """Create or update a planilha entry. Returns the stored dict."""
    record = {
        "id": planilha_id or str(uuid.uuid4()),
        "nome": (nome or "").strip(),
        "g_url": (g_url or "").strip(),
        "aba": (aba or "").strip(),
        "campaign_ids": [c for c in (campaign_ids or []) if c],
        "metric_rows": metric_rows or {},
        "vturb_player_ids": [p for p in (vturb_player_ids or []) if p],
    }

    if not _is_sheets_backend():
        items = _load_from_file()
        for idx, existing in enumerate(items):
            if existing.get("id") == record["id"]:
                items[idx] = record
                _save_to_file(items)
                return record
        items.append(record)
        _save_to_file(items)
        return record

    ws = _get_ws()
    ids_col = ws.col_values(1)
    row_to_update: Optional[int] = None
    for idx, val in enumerate(ids_col, start=1):
        if idx == 1:
            continue  # header
        if val == record["id"]:
            row_to_update = idx
            break

    new_row = _dict_to_row(record)
    if row_to_update:
        ws.update(
            f"A{row_to_update}:{_LAST_COL_LETTER}{row_to_update}",
            [new_row],
            value_input_option="RAW",
        )
    else:
        ws.append_row(new_row, value_input_option="RAW")

    _invalidate_cache()
    return record


def delete(planilha_id: str) -> bool:
    if not _is_sheets_backend():
        items = _load_from_file()
        new_items = [p for p in items if p.get("id") != planilha_id]
        if len(new_items) == len(items):
            return False
        _save_to_file(new_items)
        return True

    ws = _get_ws()
    ids_col = ws.col_values(1)
    for idx, val in enumerate(ids_col, start=1):
        if idx == 1:
            continue
        if val == planilha_id:
            ws.delete_rows(idx)
            _invalidate_cache()
            return True
    return False
