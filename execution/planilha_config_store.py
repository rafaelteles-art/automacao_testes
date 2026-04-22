#!/usr/bin/env python3
"""Persistent configuration store for the "Preencher por Campanhas" feature.

Each entry associates a Google Sheet (URL + tab) with one or more RedTrack
campaign IDs, and optionally a row->metric mapping describing which metric the
user wants written into each row under a date column.

Stored as JSON at the project root under `config/planilhas.json` so it survives
Streamlit reloads. The file is safe to commit if the user wants to share their
setup across machines (no credentials live here).
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_DIR = os.path.join(_PROJECT_ROOT, "config")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "planilhas.json")


def _ensure_file() -> None:
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    if not os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"planilhas": []}, f, ensure_ascii=False, indent=2)


def load_all() -> List[Dict]:
    _ensure_file()
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("planilhas", [])


def _save_all(planilhas: List[Dict]) -> None:
    _ensure_file()
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"planilhas": planilhas}, f, ensure_ascii=False, indent=2)


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
    items = load_all()
    record = {
        "id": planilha_id or str(uuid.uuid4()),
        "nome": nome.strip(),
        "g_url": g_url.strip(),
        "aba": aba.strip(),
        "campaign_ids": [c for c in campaign_ids if c],
        "metric_rows": metric_rows or {},
        "vturb_player_ids": [p for p in (vturb_player_ids or []) if p],
    }
    for idx, existing in enumerate(items):
        if existing.get("id") == record["id"]:
            items[idx] = record
            _save_all(items)
            return record
    items.append(record)
    _save_all(items)
    return record


def delete(planilha_id: str) -> bool:
    items = load_all()
    new_items = [p for p in items if p.get("id") != planilha_id]
    if len(new_items) == len(items):
        return False
    _save_all(new_items)
    return True
