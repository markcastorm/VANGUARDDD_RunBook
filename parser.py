# parser.py
# Parser for Vanguard ETF Average Duration data with forward/backfill logic

import logging
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import config

# Setup logging
logger = logging.getLogger(__name__)


class VanguardDDParser:
    """Parses Vanguard ETF data and manages cumulative master data with forward/backfill logic"""

    def __init__(self):
        self.debug = config.DEBUG_MODE
        self.logger = logger

    def parse_date(self, date_str):
        """
        Parse date string from various formats to datetime object.
        Handles formats like "12/31/2025", "2025-12-31", etc.

        Returns datetime object or None if parsing fails.
        """

        if not date_str:
            return None

        date_str = date_str.strip()

        for date_format in config.INPUT_DATE_FORMATS:
            try:
                dt = datetime.strptime(date_str, date_format)
                return dt
            except ValueError:
                continue

        self.logger.warning(f"Could not parse date: {date_str}")
        return None

    def parse_duration_value(self, duration_str):
        """
        Parse duration value from string (e.g., "6.0 years" -> 6.0).
        Handles various formats: "6.0 years", "6.0", "6 years"

        Returns float or None if parsing fails.
        """

        if not duration_str or duration_str.strip() == '':
            return None

        try:
            # Remove "years", "year", whitespace
            duration_str = duration_str.strip().lower()
            duration_str = duration_str.replace('years', '').replace('year', '').strip()

            # Convert to float
            duration = float(duration_str)

            # Validate duration is within reasonable range
            if config.MIN_DURATION_VALUE <= duration <= config.MAX_DURATION_VALUE:
                return duration
            else:
                self.logger.warning(f"Duration {duration} years outside valid range")
                return None

        except ValueError:
            self.logger.warning(f"Could not parse duration value: {duration_str}")
            return None

    def parse_scraped_data(self, scraped_results):
        """
        Parse the scraped results from all products.

        Args:
            scraped_results: Dict with product keys and their scraped data

        Returns:
            dict with 'date', 'date_str', and 'durations' (keyed by column code)
        """

        self.logger.info("Parsing scraped data...")

        if not scraped_results:
            self.logger.error("No scraped results to parse")
            return None

        # All products should have the same "as of" date
        # Get date from first product
        first_product = list(scraped_results.keys())[0]
        date_str = scraped_results[first_product].get('date_str')

        if not date_str:
            self.logger.error("No date found in scraped data")
            return None

        # Parse the date
        date_obj = self.parse_date(date_str)

        if not date_obj:
            self.logger.error(f"Could not parse date: {date_str}")
            return None

        self.logger.info(f"Parsed 'as of' date: {date_obj.strftime(config.DATE_FORMAT_OUTPUT)}")

        # Parse durations for each product
        durations = {}

        for col_info in config.OUTPUT_COLUMNS:
            product_key = col_info['url_key']
            code = col_info['code']

            if product_key not in scraped_results:
                self.logger.warning(f"Product {product_key} not in scraped results")
                durations[code] = None
                continue

            duration_str = scraped_results[product_key].get('duration_str')

            if not duration_str:
                self.logger.warning(f"No duration string for {product_key}")
                durations[code] = None
                continue

            duration = self.parse_duration_value(duration_str)

            if duration is not None:
                durations[code] = duration
                self.logger.info(f"{product_key}: {duration} years")
            else:
                self.logger.warning(f"Could not parse duration for {product_key}")
                durations[code] = None

        # Check if we have at least some valid durations
        valid_durations = [v for v in durations.values() if v is not None]

        if len(valid_durations) == 0:
            self.logger.error("No valid durations parsed")
            return None

        return {
            'as_of_date': date_obj,
            'as_of_date_str': date_obj.strftime(config.DATE_FORMAT_OUTPUT),
            'durations': durations
        }

    def load_tracking_state(self):
        """
        Load the last known tracking state from JSON file.

        Returns:
            dict with 'as_of_date', 'durations', 'last_run_date' or None if file doesn't exist
        """

        if not os.path.exists(config.TRACKING_FILE):
            self.logger.warning("Tracking file not found - this is the first run")
            return None

        try:
            with open(config.TRACKING_FILE, 'r') as f:
                state = json.load(f)

            # Convert date strings back to datetime objects
            if 'as_of_date' in state and state['as_of_date']:
                state['as_of_date'] = datetime.strptime(state['as_of_date'], config.DATE_FORMAT_OUTPUT)

            if 'last_run_date' in state and state['last_run_date']:
                state['last_run_date'] = datetime.strptime(state['last_run_date'], config.DATE_FORMAT_OUTPUT)

            self.logger.info(f"Loaded tracking state: as_of={state.get('as_of_date')}, durations={state.get('durations')}")
            return state

        except Exception as e:
            self.logger.error(f"Error loading tracking state: {e}")
            return None

    def save_tracking_state(self, as_of_date, durations, last_run_date):
        """
        Save current tracking state to JSON file.

        Args:
            as_of_date: datetime object of "as of" date
            durations: dict of {code: duration_value}
            last_run_date: datetime object of last run date
        """

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(config.TRACKING_FILE), exist_ok=True)

            state = {
                'as_of_date': as_of_date.strftime(config.DATE_FORMAT_OUTPUT) if as_of_date else None,
                'durations': durations,
                'last_run_date': last_run_date.strftime(config.DATE_FORMAT_OUTPUT) if last_run_date else None,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            with open(config.TRACKING_FILE, 'w') as f:
                json.dump(state, f, indent=2)

            self.logger.info(f"Saved tracking state to {config.TRACKING_FILE}")

        except Exception as e:
            self.logger.error(f"Error saving tracking state: {e}")

    def load_master_data(self):
        """
        Load master data file.

        Returns:
            pandas DataFrame or None if error
        """

        if not os.path.exists(config.MASTER_DATA_FILE):
            self.logger.error(f"Master data file not found: {config.MASTER_DATA_FILE}")
            return None

        try:
            # Read Excel file with no header (we'll handle rows manually)
            df = pd.read_excel(config.MASTER_DATA_FILE, header=None)

            self.logger.info(f"Loaded master data: {len(df)} rows")
            return df

        except Exception as e:
            self.logger.error(f"Error loading master data: {e}")
            return None

    def save_master_data(self, df):
        """
        Save updated master data file.

        Args:
            df: pandas DataFrame to save
        """

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(config.MASTER_DATA_FILE), exist_ok=True)

            # Save to Excel without index or header
            df.to_excel(config.MASTER_DATA_FILE, index=False, header=False)

            self.logger.info(f"Saved master data: {len(df)} rows")

        except Exception as e:
            self.logger.error(f"Error saving master data: {e}")

    def get_today_date(self):
        """Get today's date"""
        return datetime.now().date()

    def find_date_row_index(self, df, target_date):
        """
        Find the row index for a specific date in the master data.

        Args:
            df: master DataFrame
            target_date: datetime object or date object

        Returns:
            int: row index (0-based) or None if not found
        """

        target_date_str = target_date.strftime(config.DATE_FORMAT_OUTPUT) if isinstance(target_date, datetime) else target_date.strftime(config.DATE_FORMAT_OUTPUT)

        # Search column 0 for the date (skip first 2 rows which are headers)
        for idx in range(2, len(df)):
            cell_value = df.iloc[idx, 0]

            if pd.isna(cell_value):
                continue

            # Convert to string and compare
            if isinstance(cell_value, datetime):
                cell_date_str = cell_value.strftime(config.DATE_FORMAT_OUTPUT)
            else:
                cell_date_str = str(cell_value)

            if target_date_str in cell_date_str:
                return idx

        return None

    def update_master_with_forward_fill(self, df, today, durations):
        """
        Forward-fill: Add today's row with previous day's values.

        Args:
            df: master DataFrame
            today: today's date (date object)
            durations: dict of {code: duration_value}

        Returns:
            Updated DataFrame
        """

        self.logger.info("SCENARIO 1: FORWARD-FILL (no change detected)")

        # Create new row
        new_row = [today] + [durations.get(col['code']) for col in config.OUTPUT_COLUMNS]

        # Append to DataFrame
        df.loc[len(df)] = new_row

        self.logger.info(f"Added row for {today}: {new_row[1:]}")

        return df

    def update_master_with_backfill(self, df, as_of_date, durations, today):
        """
        Backfill: Update from as_of_date to today with new values.

        Args:
            df: master DataFrame
            as_of_date: "as of" date from scraped data (datetime object)
            durations: dict of {code: duration_value}
            today: today's date (date object)

        Returns:
            Updated DataFrame
        """

        self.logger.info("SCENARIO 2/3: BACKFILL (date or values changed)")

        # Find the row index for as_of_date
        start_idx = self.find_date_row_index(df, as_of_date)

        if start_idx is None:
            self.logger.warning(f"Could not find {as_of_date} in master data - appending from today")
            # Just add today's row
            new_row = [today] + [durations.get(col['code']) for col in config.OUTPUT_COLUMNS]
            df.loc[len(df)] = new_row
            return df

        self.logger.info(f"Found as_of_date {as_of_date.date()} at row index {start_idx}")

        # Backfill from as_of_date to the last row in master
        rows_updated = 0
        for idx in range(start_idx, len(df)):
            # Update duration columns (columns 1, 2, 3)
            for col_idx, col_info in enumerate(config.OUTPUT_COLUMNS, start=1):
                df.iloc[idx, col_idx] = durations.get(col_info['code'])
            rows_updated += 1

        self.logger.info(f"Backfilled {rows_updated} existing rows")

        # Check if we need to add today's row (if today is beyond last row in master)
        last_date_in_master = df.iloc[-1, 0]

        if isinstance(last_date_in_master, str):
            last_date_in_master = datetime.strptime(last_date_in_master, config.DATE_FORMAT_OUTPUT).date()
        elif isinstance(last_date_in_master, datetime):
            last_date_in_master = last_date_in_master.date()

        if today > last_date_in_master:
            # Need to fill gap from last_date_in_master+1 to today
            current_date = last_date_in_master + timedelta(days=1)

            while current_date <= today:
                # Skip weekends (assuming business days only)
                if current_date.weekday() < 5:  # Monday=0, Sunday=6
                    new_row = [current_date] + [durations.get(col['code']) for col in config.OUTPUT_COLUMNS]
                    df.loc[len(df)] = new_row
                    self.logger.info(f"Added row for {current_date}: {new_row[1:]}")

                current_date += timedelta(days=1)

        return df

    def parse_and_merge(self, scraped_results):
        """
        Main method: Parse scraped data and merge with master using forward/backfill logic.

        Args:
            scraped_results: Dict with scraped data from all products

        Returns:
            Updated DataFrame or None
        """

        # Parse scraped data
        parsed = self.parse_scraped_data(scraped_results)

        if not parsed:
            return None

        scraped_as_of_date = parsed['as_of_date']
        scraped_durations = parsed['durations']

        # Load tracking state
        tracking = self.load_tracking_state()

        # Load master data
        master_df = self.load_master_data()

        if master_df is None:
            return None

        # Get today's date
        today = self.get_today_date()

        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"DECISION LOGIC")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Today: {today}")
        self.logger.info(f"Scraped 'as of' date: {scraped_as_of_date.date()}")
        self.logger.info(f"Scraped durations: {scraped_durations}")

        # DECISION TREE
        if tracking:
            last_as_of_date = tracking.get('as_of_date')
            last_durations = tracking.get('durations')

            self.logger.info(f"Last 'as of' date: {last_as_of_date.date() if last_as_of_date else 'None'}")
            self.logger.info(f"Last durations: {last_durations}")

            # Check if anything changed
            date_changed = (scraped_as_of_date.date() != last_as_of_date.date()) if last_as_of_date else True
            values_changed = (scraped_durations != last_durations)

            if not date_changed and not values_changed:
                # SCENARIO 1: No change - forward fill
                self.logger.info("Decision: FORWARD-FILL (no changes)")
                master_df = self.update_master_with_forward_fill(master_df, today, scraped_durations)
            else:
                # SCENARIO 2/3: Date or values changed - backfill
                if date_changed:
                    self.logger.info(f"Decision: BACKFILL (date changed from {last_as_of_date.date()} to {scraped_as_of_date.date()})")
                else:
                    self.logger.info("Decision: BACKFILL (values changed)")

                master_df = self.update_master_with_backfill(master_df, scraped_as_of_date, scraped_durations, today)
        else:
            # First run - just add today's row
            self.logger.info("Decision: FIRST RUN - adding today's row")
            master_df = self.update_master_with_forward_fill(master_df, today, scraped_durations)

        # Save updated master data
        self.save_master_data(master_df)

        # Save tracking state
        self.save_tracking_state(scraped_as_of_date, scraped_durations, datetime.now())

        self.logger.info(f"{'='*70}\n")

        return master_df


def main():
    """Test the parser"""
    from logger_setup import setup_logging

    setup_logging()

    parser = VanguardDDParser()

    # Test with mock data
    mock_results = {
        'VCIT': {'date_str': '12/31/2025', 'duration_str': '6.0 years'},
        'VCSH': {'date_str': '12/31/2025', 'duration_str': '2.6 years'},
        'VCLT': {'date_str': '12/31/2025', 'duration_str': '12.1 years'}
    }

    df = parser.parse_and_merge(mock_results)

    if df is not None:
        print("\n[SUCCESS] Master data updated")
        print(f"Total rows: {len(df)}")
        print("\nLast 5 rows:")
        print(df.tail(5).to_string())
    else:
        print("\n[FAILED] Could not update master data")


if __name__ == '__main__':
    main()
