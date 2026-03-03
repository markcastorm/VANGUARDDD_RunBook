# logger_setup.py
# Logging configuration for Vanguard ETF data collection

import os
import logging
import config


def setup_logging():
    """
    Configure logging for the application.
    Creates log directory and sets up file and console handlers.
    """

    # Create log directory if it doesn't exist
    os.makedirs(config.LOG_DIR, exist_ok=True)

    # Generate log file name with timestamp
    log_filename = config.LOG_FILE_PATTERN.format(timestamp=config.RUN_TIMESTAMP)
    log_filepath = os.path.join(config.LOG_DIR, log_filename)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL))

    # Clear any existing handlers
    root_logger.handlers = []

    # Create formatters
    formatter = logging.Formatter(
        config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT
    )

    # File handler
    if config.LOG_TO_FILE:
        file_handler = logging.FileHandler(log_filepath, mode='w', encoding='utf-8')
        file_handler.setLevel(getattr(logging, config.LOG_LEVEL))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Console handler
    if config.LOG_TO_CONSOLE:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Log initialization
    root_logger.info("="*70)
    root_logger.info("Logging initialized")
    root_logger.info(f"Log file: {log_filepath}")
    root_logger.info(f"Log level: {config.LOG_LEVEL}")
    root_logger.info("="*70)

    return log_filepath
