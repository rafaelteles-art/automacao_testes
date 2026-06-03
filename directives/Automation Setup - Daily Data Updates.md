# Automation Setup - Daily Data Updates

> **Two distinct jobs live here.** Don't confuse them:
> 1. **Dossiê Daily Fill (cloud)** — fills the Google Sheets *planilhas* flagged
>    `auto_fill`, via `execution/fill_dossies_daily.py`, on **GitHub Actions**.
>    This is the current, recommended automation. See the section right below.
> 2. **Legacy local importer** — the older `facebook_redtrack_importer_v2.py`
>    (Excel output) run via local Task Scheduler / cron. Documented further down
>    for reference.

## Dossiê Daily Fill (GitHub Actions)

### What it does
Every day at **07:00 BRT (= 10:00 UTC)**, fills **yesterday's** date column in
every Dossiê sheet — i.e. every planilha registered in the config store with the
`auto_fill` flag turned on (the 🤖 checkbox in the Streamlit "Configurar
Planilhas" tab). Yesterday is used because at 07:00 it is the most recent
*complete* day. Re-running a later day is supported via the manual trigger.

- **Script:** `execution/fill_dossies_daily.py` (headless; no Streamlit). It auths
  via `credentials.json`, reads tokens from `token_store` (the config Sheet —
  **not** hardcoded), filters `auto_fill` planilhas, and calls
  `fill_sheet(..., filter_start=yesterday, filter_end=yesterday)` per Dossiê.
- **Workflow:** `.github/workflows/daily-fill.yml` (cron `0 10 * * *`, plus a
  manual `workflow_dispatch` with an optional `date` input for backfills).
- **It only fills date columns that already exist** in row 1 — it never creates
  a column. A 0-cell write (yesterday's header missing, or no matching column-A
  labels) is treated as a **failure** so silent no-ops surface.

### Notifications / logging
- Each run appends one summary row **per Dossiê** to a `log` tab on the config
  Sheet: `timestamp_brt | planilha | aba | data | celulas | status | erro`. The
  tab is created automatically on first run.
- The job **exits non-zero** if any Dossiê fails (continue-then-report), so
  GitHub emails the repo owner on failure. Success is silent.

### GitHub setup (one time)
Add two repository secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `GOOGLE_CREDENTIALS` | Full contents of the service-account `credentials.json` |
| `PLANILHAS_CONFIG_SHEET_URL` | URL of the config Google Sheet (tabs `planilhas`/`labels`) |

Tokens (`rt_token`, `vturb_token`) are **not** secrets — they're read from the
config Sheet via `token_store`, so updating them in the app's sidebar flows
through to the job automatically. The service-account email must be **Editor**
on both the config Sheet and every target Dossiê sheet.

### Running / testing manually
```bash
# locally: needs credentials.json in CWD + PLANILHAS_CONFIG_SHEET_URL set
python execution/fill_dossies_daily.py                 # yesterday (BRT)
python execution/fill_dossies_daily.py --date 2026-06-01  # backfill one day
python execution/fill_dossies_daily.py --dry-run          # fills sheets, skips 'log' tab
```
On GitHub: Actions → "Daily Dossiê Fill" → Run workflow (optionally set a date).

### Edge cases / learnings
- **Timezone:** BRT is a fixed UTC-3; Brazil abolished DST in 2019, so the cron
  never drifts. No DST handling needed.
- **Late conversions:** filling only yesterday means earlier days are *not*
  re-corrected for late-attributed RedTrack conversions. Backfill with `--date`
  if a past day needs refreshing.
- **API cost:** one RedTrack call per campaign per Dossiê (single-day range).

---

## Legacy: local importer (`facebook_redtrack_importer_v2.py`)

The sections below schedule the **older Excel importer**, not the Dossiê fill.

## Windows - Task Scheduler

### Step 1: Create a Batch File

Create a file named `run_import.bat`:

```batch
@echo off
cd /d "C:\path\to\your\folder"
python3 facebook_redtrack_importer_v2.py >> import_log.txt 2>&1
```

Replace `C:\path\to\your\folder` with your actual folder path.

### Step 2: Open Task Scheduler

1. Press `Win + R`
2. Type `taskschd.msc` and press Enter

### Step 3: Create New Task

1. Click "Create Basic Task" on the right
2. Name: "Facebook RedTrack Daily Import"
3. Description: "Automatically import data from Facebook Ads and RedTrack"
4. Click Next

### Step 4: Set Trigger

1. Select "Daily"
2. Set time (e.g., 2:00 AM)
3. Click Next

### Step 5: Set Action

1. Select "Start a program"
2. Program: `C:\path\to\run_import.bat`
3. Click Next
4. Click Finish

## macOS/Linux - Cron Job

### Step 1: Create a Shell Script

Create a file named `run_import.sh`:

```bash
#!/bin/bash
cd /path/to/your/folder
python3 facebook_redtrack_importer_v2.py >> import_log.txt 2>&1
```

Make it executable:
```bash
chmod +x run_import.sh
```

### Step 2: Edit Crontab

```bash
crontab -e
```

### Step 3: Add Cron Job

Add this line to run daily at 2:00 AM:

```
0 2 * * * /path/to/your/folder/run_import.sh
```

To run every 6 hours:
```
0 */6 * * * /path/to/your/folder/run_import.sh
```

### Step 4: Verify

```bash
crontab -l
```

## Monitoring

### Check Logs

After running, check the log file:

```bash
tail -f import_log.txt
```

### Email Notifications (Linux/macOS)

Add to crontab to send email on errors:

```
0 2 * * * /path/to/your/folder/run_import.sh || mail -s "Import Failed" your@email.com < import_log.txt
```

## Troubleshooting

### Script doesn't run

1. Verify Python path: `which python3`
2. Verify file permissions: `ls -la run_import.sh`
3. Check logs for errors

### Data not updating

1. Check if Excel file is open (close it)
2. Verify credentials are still valid
3. Check API rate limits
4. Review log file for error messages

## Best Practices

1. **Schedule during off-hours** (e.g., 2-3 AM)
2. **Keep logs** for debugging
3. **Test manually first** before automating
4. **Monitor for 1-2 weeks** to ensure reliability
5. **Set up alerts** for failures
6. **Rotate credentials** regularly

## Advanced: Error Handling

Modify the script to send email on failure:

```python
import smtplib
from email.mime.text import MIMEText

def send_error_email(error_message):
    sender = "your@email.com"
    recipient = "admin@email.com"
    
    msg = MIMEText(f"Import failed:\n\n{error_message}")
    msg['Subject'] = "Facebook RedTrack Import Failed"
    msg['From'] = sender
    msg['To'] = recipient
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender, "your_app_password")
        server.send_message(msg)
```

## Support

For issues with scheduling:
- **Windows:** Search "Task Scheduler" in Help
- **macOS:** `man crontab`
- **Linux:** `man cron`
