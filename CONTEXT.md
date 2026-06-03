# Preencher Planilha

Automation that fills Google Sheets / Excel spreadsheets with advertising metrics
pulled from Facebook Ads, RedTrack, and VTurb. This glossary defines the project's
domain language; it is not a spec.

## Language

**Planilha**:
A target spreadsheet registered in the config store, associating a Google Sheets
workbook + tab with one or more RedTrack campaigns and VTurb players. Filling a
planilha writes summed metrics into every column whose first row holds a date.
_Avoid_: sheet, spreadsheet (ambiguous — could mean the config store or the target)

**Dossiê sheet**:
A Planilha that is flagged for automatic daily fill. "Dossiê" is not a separate
kind of spreadsheet — it is an opt-in subset of registered planilhas. The flag
lives on the `planilhas` config sheet and is toggled per-planilha in the UI.
_Avoid_: dossier (English), report

**Config store**:
The canonical Google Sheets workbook (tabs `planilhas` and `labels`) that holds
all registered planilhas and the global label→metric dictionary. The source of
truth in production, since the Streamlit Cloud filesystem is ephemeral.
_Avoid_: database, config file

**Daily fill job**:
The scheduled, headless run that loads every Dossiê sheet from the config store
and fills it for the day. Distinct from the manual fill triggered in the UI.
_Avoid_: cron, import (import refers to the separate FB/RedTrack Excel importer)
