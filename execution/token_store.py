"""Persistent store for API tokens (fb_token, rt_token, vturb_token).

Follows the same dual-backend pattern as planilha_config_store and label_map_store:
  - Google Sheets (tab "tokens") when configure(gc, sheet_url) is called.
  - Local JSON fallback otherwise (ephemeral on Streamlit Cloud).

Tab schema: key | value
"""
from __future__ import annotations

import json
import os
from typing import Dict, Optional

import gspread

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_DIR = os.path.join(_PROJECT_ROOT, "config")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "tokens.json")

_TAB = "tokens"
_HEADERS = ["key", "value"]
_KEYS = ["fb_token", "rt_token", "vturb_token"]

_gc: Optional[gspread.Client] = None
_sheet_url: Optional[str] = None


def configure(gc: gspread.Client, sheet_url: str) -> None:
    global _gc, _sheet_url
    _gc = gc
    _sheet_url = sheet_url


def _is_sheets_backend() -> bool:
    return _gc is not None and bool(_sheet_url)


def _get_ws() -> gspread.Worksheet:
    sh = _gc.open_by_url(_sheet_url)
    try:
        ws = sh.worksheet(_TAB)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=_TAB, rows=20, cols=2)
        ws.update("A1:B1", [_HEADERS])
        return ws
    first_row = ws.row_values(1)
    if first_row[:2] != _HEADERS:
        ws.update("A1:B1", [_HEADERS])
    return ws


def load() -> Dict[str, str]:
    """Return dict with saved token values. Missing keys have empty string."""
    if _is_sheets_backend():
        try:
            ws = _get_ws()
            rows = ws.get_all_records()
            return {r["key"]: str(r.get("value", "")) for r in rows if r.get("key") in _KEYS}
        except Exception:
            pass
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save(tokens: Dict[str, str]) -> None:
    """Persist token values. Only saves non-empty values."""
    if _is_sheets_backend():
        try:
            ws = _get_ws()
            rows = ws.get_all_records()
            existing_row = {r["key"]: i + 2 for i, r in enumerate(rows) if r.get("key")}
            for key, value in tokens.items():
                if key not in _KEYS or not value:
                    continue
                if key in existing_row:
                    ws.update(f"B{existing_row[key]}", [[value]])
                else:
                    ws.append_row([key, value])
            return
        except Exception:
            pass
    # Local JSON fallback
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    existing: Dict[str, str] = {}
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing.update({k: v for k, v in tokens.items() if v})
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
