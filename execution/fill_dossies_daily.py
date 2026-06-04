#!/usr/bin/env python3
"""Daily fill job — fills every Dossiê sheet for *yesterday* (BRT).

A "Dossiê sheet" is a registered planilha with the ``auto_fill`` flag turned on
(see CONTEXT.md). This script is the headless counterpart of the manual fill in
the Streamlit UI; it is meant to run unattended on a schedule (GitHub Actions,
cron `0 10 * * *` UTC = 07:00 BRT).

Flow:
  1. Auth gspread from ``credentials.json`` (written from a CI secret) with the
     spreadsheets scope — mirrors web_app.py's headless auth path.
  2. Resolve the config sheet URL from ``PLANILHAS_CONFIG_SHEET_URL`` and call
     ``configure(gc, url)`` on all three stores.
  3. Load tokens from token_store (the config Sheet). ``rt_token`` is required;
     ``vturb_token`` is optional. NO hardcoded token fallbacks.
  4. Keep only planilhas with ``auto_fill`` on.
  5. For each, fill ONLY yesterday's (already-existing) date column via
     ``fill_sheet(..., filter_start=yesterday, filter_end=yesterday)``.
  6. Per-Dossiê: catch errors, continue, append a summary row to the ``log`` tab
     of the config Sheet. A 0-cell write (missing yesterday column / no data) is
     treated as a FAILURE so silent no-ops surface.
  7. Exit non-zero if anything failed → GitHub emails the repo owner.

Usage:
    python execution/fill_dossies_daily.py            # fills yesterday (BRT)
    python execution/fill_dossies_daily.py --date 2026-06-01   # backfill one day
    python execution/fill_dossies_daily.py --dry-run  # compute, do not write/log
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

import gspread
from google.oauth2.service_account import Credentials

# Allow importing sibling execution modules regardless of CWD.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import planilha_config_store as cfg_store
import label_map_store
import token_store
from fill_planilha_by_dates import fill_sheet

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
BRT = timezone(timedelta(hours=-3))  # Brazil has no DST since 2019 — stable.
_LOG_TAB = "log"
_LOG_HEADERS = ["timestamp_brt", "planilha", "aba", "data", "celulas", "status", "erro"]


def _log(msg: str) -> None:
    print(msg, flush=True)


def _build_client() -> gspread.Client:
    """Authorize gspread from credentials.json (headless). Falls back to the
    GOOGLE_APPLICATION_CREDENTIALS path if set."""
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    if not os.path.exists(cred_path):
        raise RuntimeError(
            f"Service-account credentials not found at '{cred_path}'. "
            "In CI, write the secret to credentials.json before running."
        )
    # Read with utf-8-sig so a leading UTF-8 BOM (e.g. introduced when the CI
    # secret was piped through PowerShell) is stripped before JSON parsing.
    with open(cred_path, "r", encoding="utf-8-sig") as f:
        info = json.load(f)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _yesterday_brt() -> date:
    return datetime.now(BRT).date() - timedelta(days=1)


def _append_log_rows(gc: gspread.Client, sheet_url: str, rows: List[List[str]]) -> None:
    """Append run-summary rows to the `log` tab of the config Sheet, creating it
    with headers if needed. Best-effort: a logging failure must not mask the run."""
    if not rows:
        return
    try:
        sh = gc.open_by_url(sheet_url)
        try:
            ws = sh.worksheet(_LOG_TAB)
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=_LOG_TAB, rows=2000, cols=len(_LOG_HEADERS))
            ws.update(f"A1:{chr(ord('A') + len(_LOG_HEADERS) - 1)}1", [_LOG_HEADERS])
        ws.append_rows(rows, value_input_option="RAW")
    except Exception as e:
        _log(f"[WARN] Não consegui gravar no tab '{_LOG_TAB}': {e}")


def run(target_day: date, dry_run: bool = False) -> int:
    """Fill every Dossiê for `target_day`. Returns process exit code."""
    gc = _build_client()

    # lstrip the BOM too — a PowerShell-piped secret may carry a leading ﻿.
    sheet_url = (os.environ.get("PLANILHAS_CONFIG_SHEET_URL") or "").lstrip("﻿").strip()
    if not sheet_url:
        _log("[ERRO] PLANILHAS_CONFIG_SHEET_URL não definido. Abortando.")
        return 2

    cfg_store.configure(gc, sheet_url)
    label_map_store.configure(gc, sheet_url)
    token_store.configure(gc, sheet_url)

    tokens = token_store.load()
    rt_token = (tokens.get("rt_token") or "").strip()
    vturb_token = (tokens.get("vturb_token") or "").strip() or None
    if not rt_token:
        _log("[ERRO] rt_token ausente no token_store (config Sheet). Abortando.")
        return 2

    dossies = [p for p in cfg_store.load_all(force_reload=True) if p.get("auto_fill")]
    _log(f"Dossiês com auto_fill: {len(dossies)} | preenchendo dia {target_day.isoformat()} (BRT)")
    if not dossies:
        _log("[ERRO] Nenhuma planilha com auto_fill marcado. Nada a fazer.")
        return 1

    ts = datetime.now(BRT).strftime("%Y-%m-%d %H:%M:%S")
    log_rows: List[List[str]] = []
    failures = 0

    for p in dossies:
        nome = p.get("nome", "?")
        aba = p.get("aba", "?")
        try:
            result = fill_sheet(
                p,
                rt_token,
                gc,
                filter_start=target_day,
                filter_end=target_day,
                vturb_token=vturb_token,
            )
            updates = int(result.get("updates", 0))
            if updates > 0:
                status, erro = "OK", ""
                _log(f"  ✅ {nome} [{aba}] — {updates} células")
            else:
                status = "FALHA"
                erro = result.get("note") or "0 células — coluna de ontem ausente ou sem dados"
                failures += 1
                _log(f"  ⚠️ {nome} [{aba}] — {erro}")
            log_rows.append([ts, nome, aba, target_day.isoformat(), str(updates), status, erro])
        except Exception as e:
            failures += 1
            erro = f"{type(e).__name__}: {e}"
            _log(f"  ❌ {nome} [{aba}] — {erro}")
            _log(traceback.format_exc())
            log_rows.append([ts, nome, aba, target_day.isoformat(), "0", "ERRO", erro])

    if dry_run:
        _log("[DRY-RUN] Não gravando no tab 'log'.")
    else:
        _append_log_rows(gc, sheet_url, log_rows)

    total = len(dossies)
    _log(f"Concluído: {total - failures}/{total} Dossiês preenchidos com sucesso.")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Preenche os Dossiês do dia anterior.")
    parser.add_argument("--date", help="Sobrescreve o dia alvo (YYYY-MM-DD). Padrão: ontem (BRT).")
    parser.add_argument("--dry-run", action="store_true", help="Calcula e grava na planilha, mas não escreve no tab 'log'.")
    args = parser.parse_args()

    if args.date:
        try:
            target_day = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            _log(f"[ERRO] --date inválido: {args.date!r}. Use YYYY-MM-DD.")
            return 2
    else:
        target_day = _yesterday_brt()

    try:
        return run(target_day, dry_run=args.dry_run)
    except Exception as e:
        _log(f"[ERRO FATAL] {type(e).__name__}: {e}")
        _log(traceback.format_exc())
        return 2


if __name__ == "__main__":
    sys.exit(main())
