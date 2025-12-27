"""
Unified logging module for the voice assistant project.
Provides consistent logging format with timestamps, log levels, and module names.
"""

import logging
import sys
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str = "voice_assistant",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    Set up and configure a logger with consistent formatting.
    
    Args:
        name: Logger name
        level: Logging level (default: INFO)
        log_file: Optional file path for file logging
        format_string: Optional custom format string
        
    Returns:
        Configured logger instance
    """
    if format_string is None:
        format_string = (
            "[%(asctime)s] %(levelname)s [%(name)s:%(funcName)s] %(message)s"
        )
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Create default logger instance
logger = setup_logger()

# Convenience functions for backward compatibility
def info(msg: str, *args, **kwargs) -> None:
    """Log info message."""
    logger.info(msg, *args, **kwargs)

def debug(msg: str, *args, **kwargs) -> None:
    """Log debug message."""
    logger.debug(msg, *args, **kwargs)

def warning(msg: str, *args, **kwargs) -> None:
    """Log warning message."""
    logger.warning(msg, *args, **kwargs)

def error(msg: str, *args, **kwargs) -> None:
    """Log error message."""
    logger.error(msg, *args, **kwargs)

def critical(msg: str, *args, **kwargs) -> None:
    """Log critical message."""
    logger.critical(msg, *args, **kwargs)

def exception(msg: str, *args, **kwargs) -> None:
    """Log exception with traceback."""
    logger.exception(msg, *args, **kwargs)


if __name__ == "__main__":
    # Test the logger
    logger.info("Logger test: INFO message")
    logger.debug("Logger test: DEBUG message")
    logger.warning("Logger test: WARNING message")
    logger.error("Logger test: ERROR message")
    print("Logger module loaded successfully.")
