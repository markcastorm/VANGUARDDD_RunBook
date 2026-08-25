# VANGUARDDD RunBook

**Vanguard ETF Average Duration Data Collection System**

Automated daily pipeline that scrapes bond duration data from Vanguard's website for three corporate bond ETFs, maintains a cumulative historical master file, and applies intelligent forward-fill / backfill logic to handle irregular data updates.

---

## Tracked Products

| Ticker | Fund Name | Metric |
|--------|-----------|--------|
| **VCIT** | Vanguard Intermediate-Term Corporate Bond ETF | Average Duration |
| **VCSH** | Vanguard Short-Term Corporate Bond ETF | Average Duration |
| **VCLT** | Vanguard Long-Term Corporate Bond ETF | Average Duration |

---

## Architecture

```
VANGUARDDD_RunBook/
├── orchestrator.py        # Entry point — chains all steps
├── scraper.py             # Playwright browser automation
├── parser.py              # Forward/backfill decision logic
├── file_generator.py      # Excel + ZIP output generation
├── config.py              # All configuration (URLs, selectors, paths)
├── logger_setup.py        # Logging bootstrap
├── Master/
│   ├── Master_DATA.xlsx   # Cumulative historical data (never delete)
│   └── tracking_state.json # Last known as-of date + values
├── output/
│   ├── VANGUARDDD_DATA_<timestamp>.xlsx
│   ├── VANGUARDDD_META_<timestamp>.xlsx
│   ├── VANGUARDDD_<timestamp>.zip
│   └── latest/            # Always contains most recent run
└── logs/
    └── vanguarddd_<timestamp>.log
```

---

## Installation

```bash
pip install playwright playwright-stealth pandas openpyxl
playwright install chromium
```

> **Note:** Playwright uses its own bundled Chromium — your system Chrome version is irrelevant. Chrome auto-updates cannot break this scraper.

---

## Usage

### Run the full pipeline

```bash
python orchestrator.py
```

### Run individual components (for debugging)

```bash
python scraper.py        # Test extraction only (no file writes)
python parser.py         # Test forward/backfill with mock data
python file_generator.py # Regenerate output files from existing master
```

---

## How It Works

### Browser Automation

Playwright with `playwright-stealth` loads each ETF's portfolio page in two steps:
1. Load the base URL → wait 10s for Angular SPA to bootstrap
2. Navigate to `#portfolio-composition` hash → wait 6s for lazy-loaded section to render

Stealth patches browser fingerprinting properties, bypassing Vanguard's bot detection.

### Data Extraction

For each ticker, two selectors are tried in order:

| Priority | Selector | What it finds |
|----------|----------|---------------|
| Primary | `td[data-rpa-tag-id="symbolAvgDuration"]` | Average duration value |
| Fallback | `tr.fixed-income` row scan → `td.row-header` matching "Average duration" | Same value via table |

Date: `p.date.rps-paragraph-two` (fallback: `p.date`)

### Forward/Backfill Logic

Vanguard updates their "as of" date irregularly. The pipeline tracks the last known state in `tracking_state.json` and decides:

```
IF scraped as_of_date == last AND values == last:
    FORWARD-FILL — append today's row with same values

IF as_of_date changed OR values changed:
    BACKFILL — update all rows from as_of_date onward, then append through today
```

#### Example — Forward-fill (most common)
```
Scraped: as of 07/31/2026, VCIT=6.0, VCSH=2.7, VCLT=11.8
Last:    as of 07/31/2026, VCIT=6.0, VCSH=2.7, VCLT=11.8
→ Append row for 2026-08-25: [6.0, 2.7, 11.8]
```

#### Example — Backfill (when Vanguard updates)
```
Scraped: as of 08/31/2026, VCIT=6.2, VCSH=2.8, VCLT=12.0
Last:    as of 07/31/2026, VCIT=6.0, VCSH=2.7, VCLT=11.8
→ Update all rows from 2026-08-31 onward with new values
→ Append rows from last master date through today
```

---

## Master Data File Structure

`Master/Master_DATA.xlsx` — never delete this file.

```
Row 0:  [blank]     | CODE (VCIT)    | CODE (VCSH)    | CODE (VCLT)
Row 1:  [blank]     | Description... | Description... | Description...
Row 2+: YYYY-MM-DD  | 6.0            | 2.7            | 11.8
```

Date range: `2024-02-29` to present (653+ rows as of 2026-08-25, business days only).

---

## Output Files

Each run generates three files timestamped at run time:

| File | Contents |
|------|----------|
| `VANGUARDDD_DATA_<ts>.xlsx` | Full master data (copy) |
| `VANGUARDDD_META_<ts>.xlsx` | Metadata (codes, descriptions, units, provider info) |
| `VANGUARDDD_<ts>.zip` | ZIP archive of both files |

All files are also copied to `output/latest/` for easy access.

---

## Configuration

Key settings in [config.py](config.py):

```python
HEADLESS_MODE = False      # True for unattended/scheduled runs
DEBUG_MODE    = True       # Enables verbose DEBUG logging

REQUIRE_ALL_PRODUCTS = True  # Abort if any ticker fails (recommended)

MIN_DURATION_VALUE = 0.1   # Validation: reject durations outside this range
MAX_DURATION_VALUE = 30.0
```

---

## Debugging

### Common issues

| Issue | Solution |
|-------|----------|
| Scraper extracts nothing | Check selectors in `config.py` — Vanguard may have changed HTML |
| Master file permission error | Close Master_DATA.xlsx in Excel before running |
| Page loads but section missing | Increase `time.sleep()` values in `scraper.navigate_to_page()` |
| Wrong values being written | Check `tracking_state.json` — manually correct if needed |

### Logs

Every run writes a timestamped log to `logs/`. Set `DEBUG_MODE = True` in config for full detail.

---

## Scheduling (Windows Task Scheduler)

For unattended daily runs:
1. Set `HEADLESS_MODE = True` in `config.py`
2. Create a Task Scheduler job:
   - **Program:** `python`
   - **Arguments:** `D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\orchestrator.py`
   - **Start in:** `D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook`
   - **Trigger:** Daily, weekdays, e.g. 08:00 AM

---

## Maintenance

### If Vanguard changes their HTML

Update selectors in `config.py` `SELECTORS` dict:
```python
SELECTORS = {
    'portfolio_section':   'section#portfolio-composition',
    'date_text':           'p.date.rps-paragraph-two',
    'symbol_avg_duration': 'td[data-rpa-tag-id="symbolAvgDuration"]',
    # fallback table scan
    'table_rows':          'tr.fixed-income',
    'row_header':          'td.row-header',
    'average_duration_label': 'Average duration',
}
```

### Adding a new ETF

1. Add to `URLS` dict in `config.py`
2. Append entry to `OUTPUT_COLUMNS` list in `config.py`
3. Add corresponding column to `Master_DATA.xlsx` (row 0: code, row 1: description, historical values)
4. Add the new code key to `tracking_state.json` `durations` dict

---

## Credits

**Architecture:** Based on CHEF_NOVARTIS (PDF scraping) and SSGADD (cumulative data management) patterns.
**Developer:** AfricaAI
**Dataset:** VANGUARDDD
**Status:** Production ready
**Last updated:** 2026-08-25
