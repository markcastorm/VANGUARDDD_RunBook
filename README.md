# VANGUARDDD RunBook

**Vanguard ETF Average Duration Data Collection System**

Automated data collection system for tracking Average Duration metrics from 3 Vanguard Corporate Bond ETFs with intelligent forward-filling and backfilling logic.

---

## 📊 Overview

This runbook scrapes daily Average Duration data from Vanguard ETF pages and maintains a cumulative master data file with sophisticated data management:

- **Forward-filling**: When data hasn't changed, uses previous day's values
- **Backfilling**: When "as of" date or values change, historically corrects master data from the "as of" date onwards

### Tracked Products

| Ticker | Fund Name | Metric |
|--------|-----------|--------|
| **VCIT** | Vanguard Intermediate-Term Corporate Bond ETF | Average Duration |
| **VCSH** | Vanguard Short-Term Corporate Bond ETF | Average Duration |
| **VCLT** | Vanguard Long-Term Corporate Bond ETF | Average Duration |

---

## 🏗️ Architecture

```
VANGUARDDD_RunBook/
├── config.py              # Configuration (URLs, selectors, column mappings)
├── logger_setup.py        # Logging configuration
├── scraper.py             # Web scraping (Selenium)
├── parser.py              # Forward/backfill logic
├── file_generator.py      # Excel file generation
├── orchestrator.py        # Main execution coordinator
├── Master/
│   ├── Master_DATA.xlsx   # Cumulative master data file
│   └── tracking_state.json # Tracks last known "as of" date and values
├── output/
│   ├── <timestamp>/       # Timestamped output folders
│   └── latest/            # Always contains most recent files
└── logs/                  # Execution logs
```

---

## 🔄 Data Update Logic

### The Theory

Vanguard updates their "as of" dates irregularly. The system tracks TWO variables:
1. **"as of" date** - When the data is valid from
2. **Duration values** - The actual duration numbers

### Decision Tree

```python
IF scraped_as_of_date == last_as_of_date AND scraped_values == last_values:
    → SCENARIO 1: FORWARD-FILL
    Action: Add today's row with same values

ELIF scraped_as_of_date != last_as_of_date:
    → SCENARIO 2: DATE CHANGED (BACKFILL)
    Action: Update from as_of_date to today with new values

ELIF scraped_values != last_values:
    → SCENARIO 3: VALUES CHANGED (BACKFILL)
    Action: Update from as_of_date to today with corrected values
```

### Example Scenarios

#### Scenario 1: No Change
```
Run on 2026-01-27
Scraped: "as of 12/31/2025", values = [6.0, 2.6, 12.1]
Last:    "as of 12/31/2025", values = [6.0, 2.6, 12.1]

→ Forward-fill: Add row 2026-01-27 with [6.0, 2.6, 12.1]
```

#### Scenario 2: Date Changed
```
Run on 2026-01-27
Scraped: "as of 01/15/2026", values = [6.2, 2.7, 12.3]
Last:    "as of 12/31/2025", values = [6.0, 2.6, 12.1]

→ Backfill from 01/15/2026:
   2026-01-15 | 6.2 | 2.7 | 12.3  ← Updated
   2026-01-16 | 6.2 | 2.7 | 12.3  ← Updated
   ...
   2026-01-26 | 6.2 | 2.7 | 12.3  ← Updated
   2026-01-27 | 6.2 | 2.7 | 12.3  ← New row
```

#### Scenario 3: Values Changed
```
Run on 2026-01-27
Scraped: "as of 12/31/2025", values = [6.2, 2.7, 12.3]
Last:    "as of 12/31/2025", values = [6.0, 2.6, 12.1]

→ Backfill from 12/31/2025:
   Apply corrected values from 12/31/2025 onwards to today
```

---

## 🚀 Installation

### Prerequisites

```bash
pip install selenium pandas openpyxl
```

Download ChromeDriver: https://chromedriver.chromium.org/

### Setup

1. **Verify Master Data File exists:**
   ```
   D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\Master\Master_DATA.xlsx
   ```

2. **Configure headless mode (optional):**
   Edit [config.py:161](D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\config.py#L161):
   ```python
   HEADLESS_MODE = True  # Set False to see browser
   ```

---

## ▶️ Usage

### Run the Full Pipeline

```bash
python orchestrator.py
```

### Test Individual Components

```bash
# Test scraper only
python scraper.py

# Test parser only
python parser.py

# Test file generator only
python file_generator.py
```

---

## 📤 Output Files

### Generated Files (timestamped)

```
output/<YYYYMMDD_HHMMSS>/
├── VANGUARDDD_DATA_<timestamp>.xlsx   # Data file
├── VANGUARDDD_META_<timestamp>.xlsx   # Metadata file
└── VANGUARDDD_<timestamp>.zip         # ZIP archive

output/latest/
└── (copies of above files)            # Always most recent
```

### Master Data File Structure

```
Row 0: [blank] | CODE1 | CODE2 | CODE3
Row 1: [blank] | Description1 | Description2 | Description3
Row 2+: DATE | VCIT_Duration | VCSH_Duration | VCLT_Duration
```

### Tracking State File

```json
{
  "as_of_date": "2025-12-31",
  "durations": {
    "VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION.B": 6.0,
    "VANGUARDDD.SHORTTERMCORPORATEBONDETF.AVGDURATION.B": 2.6,
    "VANGUARDDD.LONGTERMCORPORATEBONDETF.AVGDURATION.B": 12.1
  },
  "last_run_date": "2026-01-27",
  "last_updated": "2026-01-27 10:30:45"
}
```

---

## 🔍 Debugging

### Enable Debug Mode

Edit [config.py:162](D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\config.py#L162):
```python
DEBUG_MODE = True
```

### Check Logs

```
logs/<YYYYMMDD_HHMMSS>/vanguarddd_<timestamp>.log
```

### Common Issues

| Issue | Solution |
|-------|----------|
| **Scraper fails** | Check CSS selectors in `config.py` (Vanguard may change HTML) |
| **Date not found** | Verify `date_text` selector in config |
| **Duration not found** | Check `symbol_avg_duration` selector |
| **Master file locked** | Close Excel if it's open |
| **ChromeDriver error** | Update ChromeDriver to match Chrome version |

---

## 🎯 Key Features

✅ **Intelligent Data Management**
- Automatic forward-filling when data unchanged
- Historical backfilling when data corrected
- Change detection for both date and values

✅ **Robust Web Scraping**
- Multiple fallback methods for data extraction
- Fund name verification
- Automatic retry logic

✅ **Data Integrity**
- Validation of duration ranges (0.1 - 30 years)
- Date format parsing from multiple formats
- Tracking state persistence

✅ **Professional Outputs**
- Timestamped files prevent overwrites
- "latest" folder for easy access
- ZIP archives for distribution
- Comprehensive metadata

---

## 📝 Configuration Options

### Key Settings in [config.py](D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\config.py)

```python
# Browser
HEADLESS_MODE = True          # Run without visible browser
WAIT_TIMEOUT = 20             # Page load timeout (seconds)

# Data Management
ENABLE_FORWARD_FILL = True    # Forward-fill unchanged data
ENABLE_BACKFILL = True        # Backfill when data changes
MAX_BACKFILL_DAYS = 365       # Safety limit for backfilling

# Validation
MIN_DURATION_VALUE = 0.1      # Minimum valid duration (years)
MAX_DURATION_VALUE = 30.0     # Maximum valid duration (years)
REQUIRE_ALL_PRODUCTS = True   # Fail if any product fails
```

---

## 🔄 Workflow

```
┌─────────────────┐
│  orchestrator   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    scraper      │──→ Navigate to 3 Vanguard ETF URLs
└────────┬────────┘    Extract "as of" date + Average Duration
         │
         ▼
┌─────────────────┐
│    parser       │──→ Load tracking state + master data
└────────┬────────┘    Compare scraped vs last known
         │              Apply forward-fill or backfill
         │              Save updated master + tracking state
         ▼
┌─────────────────┐
│ file_generator  │──→ Create DATA.xlsx
└────────┬────────┘    Create META.xlsx
         │              Create ZIP archive
         │              Copy to "latest" folder
         ▼
     [Complete]
```

---

## 👥 Credits

**Architecture based on:**
- CHEF_NOVARTIS (PDF scraping pipeline)
- SSGADD (Cumulative data management)

**Developer:** AfricaAI
**Date:** January 2026
**Dataset:** VANGUARDDD

---

## 📚 Related Files

- [information.txt](D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\project_information\information.txt) - Original requirements
- [VANGUARDDD_RunBook.docx](D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\project_information\VANGUARDDD_RunBook.docx) - Manual runbook
- [Sample HTML outputs](D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\project_information\sample1.txt) - For selector verification

---

## 🛠️ Maintenance

### Updating CSS Selectors

If Vanguard changes their HTML structure, update selectors in [config.py:44-65](D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\config.py#L44-L65):

```python
SELECTORS = {
    'portfolio_section': 'section#portfolio-composition',
    'date_text': 'p.date.rps-paragraph-two',
    'symbol_avg_duration': 'td[data-rpa-tag-id="symbolAvgDuration"]',
    # ... etc
}
```

### Adding New ETFs

1. Add URL to `URLS` dict in config.py
2. Add column definition to `OUTPUT_COLUMNS` list
3. Update master data file structure

---

**Status:** ✅ Production Ready
**Last Updated:** 2026-01-27
