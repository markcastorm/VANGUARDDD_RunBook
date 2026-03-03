# config.py
# Vanguard ETF Average Duration Data Collection Configuration

import os
from datetime import datetime

# =============================================================================
# DATA SOURCE CONFIGURATION
# =============================================================================

# URLs for the three Vanguard ETF products
URLS = {
    'VCIT': 'https://investor.vanguard.com/etf/profile/overview/vcit',
    'VCSH': 'https://investor.vanguard.com/etf/profile/VCSH',
    'VCLT': 'https://investor.vanguard.com/etf/profile/VCLT'
}

PROVIDER_NAME = 'Vanguard Personal Investors'
DATASET_NAME = 'VANGUARDDD'
COUNTRY = 'USA'
CURRENCY = 'USD'

# =============================================================================
# TIMESTAMPED FOLDERS CONFIGURATION
# =============================================================================

# Generate timestamp for this run (format: YYYYMMDD_HHMMSS)
RUN_TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')

# Use timestamped folders to avoid conflicts between runs
USE_TIMESTAMPED_FOLDERS = True

# =============================================================================
# CUMULATIVE DATA CONFIGURATION
# =============================================================================

# Master data file path (contains historical cumulative data)
MASTER_DATA_FILE = r'D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\Master\Master_DATA.xlsx'

# Tracking file to store last known "as of" date and values
TRACKING_FILE = r'D:\Projects\SIMBA-RUNBOOKS\VANGUARDDD_RunBook\Master\tracking_state.json'

# When True, always rebuild master from scratch
# When False, append/update data in existing master
REBUILD_MASTER = False

# =============================================================================
# WEB SCRAPING SELECTORS
# =============================================================================

SELECTORS = {
    # Portfolio composition section
    'portfolio_section': 'section#portfolio-composition',
    'section_title': 'h2.portfolio-heading',

    # Characteristics container
    'characteristics_container': 'characteristics-contianer',
    'date_text': 'p.date.rps-paragraph-two',

    # Fixed income characteristics table
    'fixed_income_table': 'fixed-income-characteristic table.width',
    'table_rows': 'tr.fixed-income',
    'row_header': 'td.row-header',
    'row_data': 'td[data-rpa-tag-id*="symbol"]',

    # Specific data points
    'average_duration_label': 'Average duration',
    'fund_name_heading': 'h1.ticker span.fund-name',

    # RPA tags for direct access
    'symbol_avg_duration': 'td[data-rpa-tag-id="symbolAvgDuration"]',
}

# =============================================================================
# OUTPUT COLUMN STRUCTURE (EXACT ORDER - DO NOT CHANGE)
# =============================================================================

# Based on VANGUARDDD_META_20250421.xlsx
# Column order is ABSOLUTE and must match exactly

OUTPUT_COLUMNS = [
    {
        'code': 'VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION.B',
        'code_mnemonic': 'VANGUARDDD.INTERMEDIATETERMCORPORATEBONDETF.AVGDURATION',
        'description': 'Vanguard Intermediate-Term Corporate Bond ETF, Portfolio composition, Average duration',
        'product': 'VCIT',
        'url_key': 'VCIT',
        'unit': 'years',
        'metric': 'Average duration',
        'fund_name': 'Vanguard Intermediate-Term Corporate Bond ETF'
    },
    {
        'code': 'VANGUARDDD.SHORTTERMCORPORATEBONDETF.AVGDURATION.B',
        'code_mnemonic': 'VANGUARDDD.SHORTTERMCORPORATEBONDETF.AVGDURATION',
        'description': 'Vanguard Short-Term Corporate Bond ETF, Portfolio composition, Average duration',
        'product': 'VCSH',
        'url_key': 'VCSH',
        'unit': 'years',
        'metric': 'Average duration',
        'fund_name': 'Vanguard Short-Term Corporate Bond ETF'
    },
    {
        'code': 'VANGUARDDD.LONGTERMCORPORATEBONDETF.AVGDURATION.B',
        'code_mnemonic': 'VANGUARDDD.LONGTERMCORPORATEBONDETF.AVGDURATION',
        'description': 'Vanguard Long-Term Corporate Bond ETF, Portfolio composition, Average duration',
        'product': 'VCLT',
        'url_key': 'VCLT',
        'unit': 'years',
        'metric': 'Average duration',
        'fund_name': 'Vanguard Long-Term Corporate Bond ETF'
    }
]

# =============================================================================
# METADATA STANDARD FIELDS
# =============================================================================

METADATA_DEFAULTS = {
    'FREQUENCY': 'B',  # Business daily
    'MULTIPLIER': 0,
    'AGGREGATION_TYPE': 'END_OF_PERIOD',
    'UNIT_TYPE': 'LEVEL',
    'DATA_TYPE': 'UNITS',
    'DATA_UNIT': 'years',
    'SEASONALLY_ADJUSTED': 'NSA',
    'ANNUALIZED': 'FALSE',
    'PROVIDER': 'AfricaAI',
    'SOURCE': 'VANGUARDPI',
    'SOURCE_DESCRIPTION': PROVIDER_NAME,
    'COUNTRY': COUNTRY,
    'DATASET': DATASET_NAME
}

# Metadata file columns
METADATA_COLUMNS = [
    'CODE',
    'CODE_MNEMONIC',
    'DESCRIPTION',
    'FREQUENCY',
    'MULTIPLIER',
    'AGGREGATION_TYPE',
    'UNIT_TYPE',
    'DATA_TYPE',
    'DATA_UNIT',
    'SEASONALLY_ADJUSTED',
    'ANNUALIZED',
    'PROVIDER_MEASURE_URL',
    'PROVIDER',
    'SOURCE',
    'SOURCE_DESCRIPTION',
    'COUNTRY',
    'DATASET'
]

# =============================================================================
# DATE FORMATS
# =============================================================================

# Input date formats (from website "as of 12/31/2025")
INPUT_DATE_FORMATS = [
    '%m/%d/%Y',      # 12/31/2025
    '%m-%d-%Y',      # 12-31-2025
    '%Y-%m-%d',      # 2025-12-31
    '%B %d, %Y',     # December 31, 2025
    '%b %d, %Y',     # Dec 31, 2025
]

# Output date format (for master data file)
DATE_FORMAT_OUTPUT = '%Y-%m-%d'  # 2025-12-31

# Filename date format
FILENAME_DATE_FORMAT = '%Y%m%d'

# Log date format
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# =============================================================================
# BROWSER CONFIGURATION
# =============================================================================

HEADLESS_MODE = True
DEBUG_MODE = True
WAIT_TIMEOUT = 20
PAGE_LOAD_DELAY = 3
SCROLL_DELAY = 2  # Time to wait after scrolling to Portfolio Composition section

# =============================================================================
# OUTPUT CONFIGURATION
# =============================================================================

# Base directories
BASE_OUTPUT_DIR = './output'
BASE_LOG_DIR = './logs'

# Apply timestamping if enabled
if USE_TIMESTAMPED_FOLDERS:
    OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, RUN_TIMESTAMP)
    LOG_DIR = os.path.join(BASE_LOG_DIR, RUN_TIMESTAMP)
else:
    OUTPUT_DIR = BASE_OUTPUT_DIR
    LOG_DIR = BASE_LOG_DIR

# Latest folder (always contains most recent extraction)
LATEST_OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, 'latest')

# Master data directory (where cumulative master file is stored)
MASTER_DATA_DIR = './Master'

# File naming patterns
DATA_FILE_PATTERN = 'VANGUARDDD_DATA_{timestamp}.xlsx'
META_FILE_PATTERN = 'VANGUARDDD_META_{timestamp}.xlsx'
ZIP_FILE_PATTERN = 'VANGUARDDD_{timestamp}.zip'

# Master file naming
MASTER_FILE_NAME = 'Master_DATA.xlsx'

# Log file naming
LOG_FILE_PATTERN = 'vanguarddd_{timestamp}.log'

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = 'DEBUG' if DEBUG_MODE else 'INFO'

# Log format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Console output
LOG_TO_CONSOLE = True
LOG_TO_FILE = True

# =============================================================================
# VALIDATION SETTINGS
# =============================================================================

# Validate that all required products are found
REQUIRE_ALL_PRODUCTS = True

# Validate duration values (should be reasonable years)
MIN_DURATION_VALUE = 0.1  # Minimum 0.1 years
MAX_DURATION_VALUE = 30.0  # Maximum 30 years

# Validate "as of" date is not too old (warn if older than 60 days)
MAX_DATA_AGE_DAYS = 60

# =============================================================================
# ERROR HANDLING
# =============================================================================

# Continue processing even if some products fail
CONTINUE_ON_ERROR = False  # Set to False since we need all 3 products

# Maximum retries for page load failures
MAX_RETRIES = 3
RETRY_DELAY = 5.0  # Seconds between retries

# =============================================================================
# FORWARD-FILLING CONFIGURATION
# =============================================================================

# Enable forward-filling when data hasn't changed
ENABLE_FORWARD_FILL = True

# Enable backfilling when "as of" date or values change
ENABLE_BACKFILL = True

# Maximum number of days to backfill (safety limit)
MAX_BACKFILL_DAYS = 365
