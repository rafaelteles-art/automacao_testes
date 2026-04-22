"""Global label → metric dictionary.

Replaces per-planilha `metric_rows` (row-number based) with a single global map
keyed by the text in column A of each sheet. At fill time we read col A,
normalize each cell, look it up here, and that tells us which metric goes in
that row.

Normalization: uppercase + strip accents + collapse whitespace. That way
"Visualização Página" matches "VISUALIZACAO PAGINA" matches "  visualizacao
pagina  ". Keys inside the JSON file are already stored in normalized form
(easier to diff and reason about).
"""

from __future__ import annotations

import json
import os
import unicodedata
from typing import Dict, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_DIR = os.path.join(_PROJECT_ROOT, "config")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "metric_labels.json")

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


def normalize_label(text: str) -> str:
    """Uppercase + strip accents + collapse whitespace. Empty string on None."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    collapsed = " ".join(no_accents.split())
    return collapsed.upper()


def _ensure_file() -> None:
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    if not os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"labels": _DEFAULT_LABELS}, f, ensure_ascii=False, indent=2)


def load() -> Dict[str, str]:
    """Return the full label → metric dict (keys already normalized)."""
    _ensure_file()
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return dict(json.load(f).get("labels", {}))


def save(labels: Dict[str, str]) -> None:
    """Persist the full map. Caller normalizes keys via `normalize_label` if needed."""
    _ensure_file()
    normalized = {normalize_label(k): v for k, v in labels.items() if k and v}
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"labels": normalized}, f, ensure_ascii=False, indent=2)


def upsert_one(label: str, metric: str) -> None:
    data = load()
    data[normalize_label(label)] = metric
    save(data)


def delete_one(label: str) -> Optional[str]:
    data = load()
    removed = data.pop(normalize_label(label), None)
    if removed is not None:
        save(data)
    return removed


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
