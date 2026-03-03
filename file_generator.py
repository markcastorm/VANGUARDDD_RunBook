# file_generator.py
# Generate Excel output files for Vanguard ETF data

import os
import logging
import shutil
import zipfile
import pandas as pd
from datetime import datetime
import config

# Setup logging
logger = logging.getLogger(__name__)


class VanguardDDFileGenerator:
    """Generates Excel output files (DATA, META, ZIP) from master data"""

    def __init__(self):
        self.logger = logger

    def create_data_file(self, master_df, output_dir):
        """
        Create DATA Excel file from master DataFrame.

        Args:
            master_df: Master DataFrame with all data
            output_dir: Directory to save file

        Returns:
            str: Path to created file
        """

        self.logger.info("Creating DATA file...")

        try:
            # Generate filename
            filename = config.DATA_FILE_PATTERN.format(timestamp=config.RUN_TIMESTAMP)
            filepath = os.path.join(output_dir, filename)

            # Save to Excel (no index, no header - master already has headers in rows 0 and 1)
            master_df.to_excel(filepath, index=False, header=False, engine='openpyxl')

            self.logger.info(f"Created DATA file: {filename}")
            return filepath

        except Exception as e:
            self.logger.error(f"Error creating DATA file: {e}")
            return None

    def create_meta_file(self, output_dir):
        """
        Create META Excel file with metadata for all columns.

        Args:
            output_dir: Directory to save file

        Returns:
            str: Path to created file
        """

        self.logger.info("Creating META file...")

        try:
            # Generate filename
            filename = config.META_FILE_PATTERN.format(timestamp=config.RUN_TIMESTAMP)
            filepath = os.path.join(output_dir, filename)

            # Build metadata rows
            meta_rows = []

            for col_info in config.OUTPUT_COLUMNS:
                row = {
                    'CODE': col_info['code'],
                    'CODE_MNEMONIC': col_info['code_mnemonic'],
                    'DESCRIPTION': col_info['description'],
                    'FREQUENCY': config.METADATA_DEFAULTS['FREQUENCY'],
                    'MULTIPLIER': config.METADATA_DEFAULTS['MULTIPLIER'],
                    'AGGREGATION_TYPE': config.METADATA_DEFAULTS['AGGREGATION_TYPE'],
                    'UNIT_TYPE': config.METADATA_DEFAULTS['UNIT_TYPE'],
                    'DATA_TYPE': config.METADATA_DEFAULTS['DATA_TYPE'],
                    'DATA_UNIT': config.METADATA_DEFAULTS['DATA_UNIT'],
                    'SEASONALLY_ADJUSTED': config.METADATA_DEFAULTS['SEASONALLY_ADJUSTED'],
                    'ANNUALIZED': config.METADATA_DEFAULTS['ANNUALIZED'],
                    'PROVIDER_MEASURE_URL': config.URLS[col_info['url_key']],
                    'PROVIDER': config.METADATA_DEFAULTS['PROVIDER'],
                    'SOURCE': config.METADATA_DEFAULTS['SOURCE'],
                    'SOURCE_DESCRIPTION': config.METADATA_DEFAULTS['SOURCE_DESCRIPTION'],
                    'COUNTRY': config.METADATA_DEFAULTS['COUNTRY'],
                    'DATASET': config.METADATA_DEFAULTS['DATASET']
                }
                meta_rows.append(row)

            # Create DataFrame
            meta_df = pd.DataFrame(meta_rows, columns=config.METADATA_COLUMNS)

            # Save to Excel
            meta_df.to_excel(filepath, index=False, engine='openpyxl')

            self.logger.info(f"Created META file: {filename}")
            return filepath

        except Exception as e:
            self.logger.error(f"Error creating META file: {e}")
            return None

    def create_zip_file(self, data_file, meta_file, output_dir):
        """
        Create ZIP file containing DATA and META files.

        Args:
            data_file: Path to DATA file
            meta_file: Path to META file
            output_dir: Directory to save ZIP

        Returns:
            str: Path to created ZIP file
        """

        self.logger.info("Creating ZIP file...")

        try:
            # Generate filename
            zip_filename = config.ZIP_FILE_PATTERN.format(timestamp=config.RUN_TIMESTAMP)
            zip_filepath = os.path.join(output_dir, zip_filename)

            # Create ZIP
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add DATA file
                if data_file and os.path.exists(data_file):
                    zipf.write(data_file, os.path.basename(data_file))
                    self.logger.info(f"Added to ZIP: {os.path.basename(data_file)}")

                # Add META file
                if meta_file and os.path.exists(meta_file):
                    zipf.write(meta_file, os.path.basename(meta_file))
                    self.logger.info(f"Added to ZIP: {os.path.basename(meta_file)}")

            self.logger.info(f"Created ZIP file: {zip_filename}")
            return zip_filepath

        except Exception as e:
            self.logger.error(f"Error creating ZIP file: {e}")
            return None

    def copy_to_latest(self, files, latest_dir):
        """
        Copy files to 'latest' directory.

        Args:
            files: Dict of file paths
            latest_dir: Path to latest directory
        """

        self.logger.info("Copying files to 'latest' directory...")

        try:
            # Create latest directory
            os.makedirs(latest_dir, exist_ok=True)

            for file_type, filepath in files.items():
                if filepath and os.path.exists(filepath):
                    dest = os.path.join(latest_dir, os.path.basename(filepath))
                    shutil.copy2(filepath, dest)
                    self.logger.info(f"Copied {file_type}: {os.path.basename(filepath)}")

        except Exception as e:
            self.logger.error(f"Error copying to latest: {e}")

    def generate_files(self, master_df):
        """
        Main method: Generate all output files.

        Args:
            master_df: Master DataFrame with all data

        Returns:
            dict with paths to all generated files
        """

        self.logger.info("\n" + "="*70)
        self.logger.info("GENERATING OUTPUT FILES")
        self.logger.info("="*70)

        # Create output directory
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        output_files = {}

        # Create DATA file
        data_file = self.create_data_file(master_df, config.OUTPUT_DIR)
        output_files['data_file'] = data_file

        # Create META file
        meta_file = self.create_meta_file(config.OUTPUT_DIR)
        output_files['meta_file'] = meta_file

        # Create ZIP file
        zip_file = self.create_zip_file(data_file, meta_file, config.OUTPUT_DIR)
        output_files['zip_file'] = zip_file

        # Copy to latest directory
        self.copy_to_latest(output_files, config.LATEST_OUTPUT_DIR)

        self.logger.info("="*70 + "\n")

        return output_files


def main():
    """Test the file generator"""
    from logger_setup import setup_logging
    import pandas as pd

    setup_logging()

    # Load master data for testing
    master_df = pd.read_excel(config.MASTER_DATA_FILE, header=None)

    generator = VanguardDDFileGenerator()
    output_files = generator.generate_files(master_df)

    if output_files:
        print("\n[SUCCESS] Files generated")
        for file_type, filepath in output_files.items():
            if filepath:
                print(f"  {file_type}: {filepath}")
    else:
        print("\n[FAILED] Could not generate files")


if __name__ == '__main__':
    main()
