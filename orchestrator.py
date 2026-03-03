#!/usr/bin/env python3
# orchestrator.py
# Main orchestrator for Vanguard ETF Average Duration data collection

import os
import sys
from datetime import datetime
import config
from logger_setup import setup_logging
from scraper import VanguardDDScraper
from parser import VanguardDDParser
from file_generator import VanguardDDFileGenerator
import logging

logger = logging.getLogger(__name__)


def print_banner():
    """Print a welcome banner"""
    print("\n" + "="*70)
    print(" Vanguard ETF - Average Duration Data Collection System")
    print(" Tracking Corporate Bond ETF Duration Data - Cumulative Tracking")
    print("="*70 + "\n")


def print_configuration():
    """Print current configuration"""
    print("Configuration:")
    print("-" * 70)
    print(f"  Products: {len(config.OUTPUT_COLUMNS)}")
    for col_info in config.OUTPUT_COLUMNS:
        print(f"    - {col_info['product']}: {col_info['fund_name']}")
    print(f"  Output: {config.OUTPUT_DIR}")
    print(f"  Master Data: {config.MASTER_DATA_FILE}")
    print(f"  Tracking File: {config.TRACKING_FILE}")
    print(f"  Rebuild Master: {'Yes' if config.REBUILD_MASTER else 'No'}")
    print(f"  Timestamp: {config.RUN_TIMESTAMP}")
    print("-" * 70 + "\n")


def main():
    """Main execution flow"""

    try:
        # Setup logging
        setup_logging()

        print_banner()
        print_configuration()

        # Step 1: Scrape ETF data
        print("STEP 1: Scraping ETF Data from Vanguard Website")
        print("="*70 + "\n")

        scraper = VanguardDDScraper()
        scraped_results = scraper.scrape_all_products()

        if not scraped_results:
            logger.error("Failed to scrape ETF data")
            print("\n[ERROR] Failed to scrape ETF data. Exiting.")
            sys.exit(1)

        print(f"[SUCCESS] Scraped data from {len(scraped_results)} products\n")

        # Display scraped data
        for product, data in scraped_results.items():
            print(f"  {product}:")
            print(f"    'as of' Date: {data.get('date_str')}")
            print(f"    Duration: {data.get('duration_str')}")

        logger.info(f"Successfully scraped {len(scraped_results)} products")

        # Step 2: Parse data and merge with master data (forward/backfill logic)
        print("\nSTEP 2: Parsing Data and Applying Forward/Backfill Logic")
        print("="*70 + "\n")

        parser = VanguardDDParser()
        updated_master_df = parser.parse_and_merge(scraped_results)

        if updated_master_df is None or len(updated_master_df) == 0:
            logger.error("No data was parsed or merged")
            print("\n[ERROR] No data was parsed or merged. Exiting.")
            sys.exit(1)

        print(f"[SUCCESS] Updated master data: {len(updated_master_df)} total rows")

        # Show date range
        if len(updated_master_df) > 2:
            # Skip first 2 rows (headers)
            data_rows = updated_master_df.iloc[2:]
            if len(data_rows) > 0:
                first_date = data_rows.iloc[0, 0]
                last_date = data_rows.iloc[-1, 0]
                print(f"  Date range: {first_date} to {last_date}")

        # Show last 3 rows
        print(f"\n  Latest 3 rows:")
        print(updated_master_df.tail(3).to_string(index=False, header=False))
        print()

        logger.info(f"Successfully updated master with {len(updated_master_df)} rows")

        # Step 3: Generate output files
        print("\nSTEP 3: Generating Excel Output Files")
        print("="*70 + "\n")

        generator = VanguardDDFileGenerator()
        output_files = generator.generate_files(updated_master_df)

        if not output_files:
            logger.error("Failed to generate output files")
            print("\n[ERROR] Failed to generate output files. Exiting.")
            sys.exit(1)

        # Step 4: Summary
        print("\n" + "="*70)
        print(" EXECUTION COMPLETE")
        print("="*70 + "\n")

        print("Summary:")
        print(f"  Total records in master: {len(updated_master_df) - 2}")  # Subtract 2 header rows

        # Count products with data
        products_with_data = len(config.OUTPUT_COLUMNS)
        print(f"  Products tracked: {products_with_data}")
        print()

        print("Output files:")
        if output_files.get('data_file'):
            print(f"  DATA: {os.path.basename(output_files['data_file'])}")
        if output_files.get('meta_file'):
            print(f"  META: {os.path.basename(output_files['meta_file'])}")
        if output_files.get('zip_file'):
            print(f"  ZIP:  {os.path.basename(output_files['zip_file'])}")
        print()

        if output_files.get('data_file'):
            print(f"Output directory: {os.path.dirname(output_files['data_file'])}")
        print(f"Latest files: {config.LATEST_OUTPUT_DIR}")
        print(f"Master data: {config.MASTER_DATA_FILE}")
        print()

        print("="*70 + "\n")

        logger.info("Orchestrator completed successfully")

        return 0

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Process interrupted by user")
        logger.warning("Process interrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        logger.exception("Unexpected error in orchestrator")
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())
