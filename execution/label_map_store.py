"""Global label → metric dictionary.

Replaces per-planilha `metric_rows` (row-number based) with a single global map
keyed by the text in column A of each sheet. At fill time we read col A,
normalize each cell, look it up here, and that tells us which metric goes in
that row.

Normalization: uppercase + strip accents + collapse whitespace. That way
"Visualização Página" matches "VISUALIZACAO PAGINA" matches "  visualizacao
pagina  ". Keys are stored in normalized form (easier to diff and reason about).

Backends:
  - Google Sheets (1 row per entry) when ``configure(gc, sheet_url)`` is called.
  - Local JSON file (legacy) otherwise — used for local dev. Streamlit Cloud
    has an ephemeral filesystem so the JSON is wiped on restart.
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
from typing import Dict, List, Optional

import gspread

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_DIR = os.path.join(_PROJECT_ROOT, "config")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "metric_labels.json")

_TAB = "labels"
_HEADERS = ["label", "metric"]
_LAST_COL_LETTER = chr(ord("A") + len(_HEADERS) - 1)  # "B"

_CACHE_TTL_SEC = 30
_cache: Dict = {"data": None, "ts": 0.0}
_seed_state: Dict = {"done": False}

_gc: Optional[gspread.Client] = None
_sheet_url: Optional[str] = None

# Seed derived from the "Cópia de TRÁFEGO ABRIL/26" tab of DOSSIE LOTTO V7.
# Only labels with a clear direct mapping are seeded; the rest (lucro, CPA,
# ROAS, % conversão, etc) are user-formula cells and intentionally left out.
_DEFAULT_LABELS: Dict[str, str] = {
    # RedTrack
    "GASTO FACEBOOK": "cost",
    "CLIQUES": "clicks",
    "VISUALIZACAO PAGINA": "lp_views",
    "IC": "convtype1",
    "COMPRAS FRONT": "convtype2",
    "COMPRAS UPSELL 1": "convtype3",
    "COMPRAS UPSELL 2": "convtype4",
    "COMPRAS UPSELL 3": "convtype5",
    "COMPRAS UPSELL 4": "convtype6",
    "FATURAMENTO TRAFEGO FACEBOOK": "total_revenue",
    # VTurb (A/B test somado entre os player_ids associados à planilha)
    "VIEWS UNICOS": "vturb_viewed_device_uniq",
    "PLAYS UNICOS": "vturb_started_device_uniq",
    "PLAY RATE": "vturb_play_rate",
    "CONECT RATE VTURB": "vturb_engagement_rate",
}


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


def normalize_label(text: str) -> str:
    """Uppercase + strip accents + collapse whitespace. Empty string on None."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    collapsed = " ".join(no_accents.split())
    return collapsed.upper()


def _get_ws() -> gspread.Worksheet:
    sh = _gc.open_by_url(_sheet_url)
    try:
        ws = sh.worksheet(_TAB)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=_TAB, rows=500, cols=len(_HEADERS))
        ws.update(f"A1:{_LAST_COL_LETTER}1", [_HEADERS])
        return ws
    first_row = ws.row_values(1)
    if first_row[: len(_HEADERS)] != _HEADERS:
        ws.update(f"A1:{_LAST_COL_LETTER}1", [_HEADERS])
    return ws


def _ensure_local_file() -> None:
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    if not os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"labels": _DEFAULT_LABELS}, f, ensure_ascii=False, indent=2)


def _load_from_file() -> Dict[str, str]:
    _ensure_local_file()
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return dict(json.load(f).get("labels", {}))


def _save_to_file(labels: Dict[str, str]) -> None:
    _ensure_local_file()
    normalized = {normalize_label(k): v for k, v in labels.items() if k and v}
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"labels": normalized}, f, ensure_ascii=False, indent=2)


def _maybe_seed(ws: gspread.Worksheet, existing_rows: List[List[str]]) -> bool:
    """Seed the empty Sheets tab with local-JSON entries (or DEFAULT_LABELS).
    At-most-once per process.
    """
    if _seed_state.get("done"):
        return False
    _seed_state["done"] = True
    try:
        if len(existing_rows) > 1:
            return False
        if os.path.exists(_CONFIG_PATH):
            local = _load_from_file()
        else:
            local = dict(_DEFAULT_LABELS)
        if not local:
            return False
        rows_to_add = [[normalize_label(k), v] for k, v in local.items() if k and v]
        ws.append_rows(rows_to_add, value_input_option="RAW")
        return True
    except Exception:
        return False


def _load_from_sheets() -> Dict[str, str]:
    ws = _get_ws()
    rows = ws.get_all_values()
    if _maybe_seed(ws, rows):
        rows = ws.get_all_values()
    out: Dict[str, str] = {}
    for r in (rows[1:] if rows else []):
        if not r:
            continue
        label = (r[0] if len(r) > 0 else "").strip()
        metric = (r[1] if len(r) > 1 else "").strip()
        if label and metric:
            out[normalize_label(label)] = metric
    return out


def load() -> Dict[str, str]:
    """Return the full label → metric dict (keys already normalized)."""
    if not _is_sheets_backend():
        return _load_from_file()

    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL_SEC:
        return dict(_cache["data"])

    data = _load_from_sheets()
    _cache["data"] = data
    _cache["ts"] = now
    return dict(data)


def save(labels: Dict[str, str]) -> None:
    """Persist the full map. Bulk-write — used when caller has the whole map."""
    normalized = {normalize_label(k): v for k, v in labels.items() if k and v}
    if not _is_sheets_backend():
        _save_to_file(normalized)
        return

    ws = _get_ws()
    # Wipe and rewrite. Acceptable because save() is rarely called with the
    # full map — most edits go through upsert_one/delete_one (single-row ops).
    ws.clear()
    ws.update(f"A1:{_LAST_COL_LETTER}1", [_HEADERS])
    if normalized:
        rows = [[k, v] for k, v in normalized.items()]
        ws.append_rows(rows, value_input_option="RAW")
    _invalidate_cache()


def upsert_one(label: str, metric: str) -> None:
    key = normalize_label(label)
    if not key or not metric:
        return

    if not _is_sheets_backend():
        data = _load_from_file()
        data[key] = metric
        _save_to_file(data)
        return

    ws = _get_ws()
    labels_col = ws.col_values(1)
    row_to_update: Optional[int] = None
    for idx, val in enumerate(labels_col, start=1):
        if idx == 1:
            continue
        if val == key:
            row_to_update = idx
            break
    if row_to_update:
        ws.update(
            f"A{row_to_update}:{_LAST_COL_LETTER}{row_to_update}",
            [[key, metric]],
            value_input_option="RAW",
        )
    else:
        ws.append_row([key, metric], value_input_option="RAW")
    _invalidate_cache()


def delete_one(label: str) -> Optional[str]:
    key = normalize_label(label)
    if not key:
        return None

    if not _is_sheets_backend():
        data = _load_from_file()
        removed = data.pop(key, None)
        if removed is not None:
            _save_to_file(data)
        return removed

    ws = _get_ws()
    labels_col = ws.col_values(1)
    for idx, val in enumerate(labels_col, start=1):
        if idx == 1:
            continue
        if val == key:
            row_vals = ws.row_values(idx)
            removed = row_vals[1] if len(row_vals) > 1 else None
            ws.delete_rows(idx)
            _invalidate_cache()
            return removed
    return None


def resolve_rows(col_a_values) -> Dict[int, str]:
    """Read a column-A list (row 1 first) and return {row_number: metric_name}.

    Rows whose label isn't in the map are silently skipped — intentional, they
    are user-formula rows or unlabeled.
    """
    mapping = load()
    out: Dict[int, str] = {}
    for idx, cell in enumerate(col_a_values, start=1):
        key = normalize_label(cell)
        if key and key in mapping:
            out[idx] = mapping[key]
    return out
