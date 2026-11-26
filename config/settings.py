"""Centralized environment-aware project settings."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
DATA_REPORTS_DIR = DATA_DIR / "reports"
LOG_DIR = Path(os.getenv("LOG_DIR", PROJECT_ROOT / "logs"))
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
