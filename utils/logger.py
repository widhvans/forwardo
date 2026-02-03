
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Log file path
LOG_FILE = os.path.join(LOGS_DIR, f"forwarder_{datetime.now().strftime('%Y-%m-%d')}.log")

# Custom formatter
FORMATTER = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def setup_logger():
    """Setup and return the logger"""
    logger = logging.getLogger("TelegramForwarder")
    logger.setLevel(logging.INFO)
    
    # Check if handlers already exist to avoid duplicate logs
    if logger.handlers:
        return logger
        
    # File Handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(FORMATTER)
    file_handler.setLevel(logging.INFO)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(FORMATTER)
    console_handler.setLevel(logging.INFO)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logger()
