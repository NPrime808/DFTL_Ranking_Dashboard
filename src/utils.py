"""
Shared utilities for DFTL Score System.

This module provides common functions used across multiple modules
to avoid code duplication.
"""

import sys
from pathlib import Path

# Enable both `python src/utils.py` and `python -m src.utils` execution modes.
# This ensures src.config imports work regardless of how the script is invoked.
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import logging
import re
import shutil
import tempfile

from src.config import ALLOWED_DATASETS, OUTPUT_FOLDER

# --- Shared Regex Patterns for Leaderboard Parsing ---
# Date format: date: DD/MM/YYYY (optional backticks, case-insensitive)
DATE_RE = re.compile(r"`?date:\s*(\d{2}/\d{2}/\d{4})`?", re.IGNORECASE)

# Rank 1: :crown_dftl: **PlayerName** - 12345 (handles optional markdown)
RANK1_RE = re.compile(r":crown_dftl:\s*\*{0,2}(.+?)\*{0,2}\s+-\s+(\d+)\s*$")

# Ranks 2-30: #N **PlayerName** - 12345 (handles optional markdown)
RANK_RE = re.compile(r"#(\d+)\s+\*{0,2}(.+?)\*{0,2}\s+-\s+(\d+)\s*$")


def strip_markdown(name: str) -> str:
    """Remove **bold**, `backticks`, and leading/trailing spaces."""
    return re.sub(r"[*`]", "", name).strip()

# --- Logging Setup ---
def setup_logging(name: str | None = None, level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return a logger with consistent formatting.

    Args:
        name: Logger name (usually __name__ from the calling module)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger


# --- File Operations ---
def cleanup_old_files(pattern: str, keep_file: Path | None = None, folder: Path | None = None) -> list[Path]:
    """
    Remove old files matching pattern, optionally keeping one specific file.

    Args:
        pattern: Glob pattern to match files (e.g., "early_access_leaderboard_*.csv")
        keep_file: Path to the file that should NOT be deleted (usually the newest)
        folder: Folder to search in (default: OUTPUT_FOLDER)

    Returns:
        List of deleted file paths
    """
    logger = setup_logging(__name__)
    target_folder = folder or OUTPUT_FOLDER
    deleted = []

    for f in target_folder.glob(pattern):
        if keep_file and f.resolve() == keep_file.resolve():
            continue
        try:
            f.unlink()
            deleted.append(f)
            logger.debug(f"Deleted old file: {f}")
        except Exception as e:
            logger.warning(f"Could not delete {f}: {e}")

    return deleted


def atomic_write_csv(df, path: Path, **kwargs) -> None:
    """
    Write a DataFrame to CSV atomically using a temporary file.

    This prevents data corruption if the write is interrupted.

    Args:
        df: pandas DataFrame to write
        path: Destination path for the CSV file
        **kwargs: Additional arguments to pass to df.to_csv()
    """
    logger = setup_logging(__name__)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix='.csv',
            dir=path.parent  # Same filesystem for atomic move
        ) as tmp:
            df.to_csv(tmp.name, **kwargs)
            tmp_path = Path(tmp.name)

        # Atomic move (rename) to final destination
        shutil.move(str(tmp_path), str(path))
        logger.debug(f"Atomically wrote {len(df)} rows to {path}")

    except Exception:
        # Clean up temp file if it exists
        if 'tmp_path' in locals() and tmp_path.exists():
            tmp_path.unlink()
        raise


# --- Validation ---
def validate_dataset(dataset: str) -> None:
    """
    Validate that a dataset name is allowed.

    Args:
        dataset: Dataset name to validate

    Raises:
        ValueError: If dataset name is not in ALLOWED_DATASETS
    """
    if dataset not in ALLOWED_DATASETS:
        raise ValueError(
            f"Invalid dataset: '{dataset}'. "
            f"Allowed values: {', '.join(sorted(ALLOWED_DATASETS))}"
        )


def validate_input_size(text: str, max_size: int) -> None:
    """
    Validate that input text does not exceed maximum size.

    Args:
        text: Input text to validate
        max_size: Maximum allowed size in bytes

    Raises:
        ValueError: If input exceeds max_size
    """
    if len(text) > max_size:
        raise ValueError(
            f"Input too large: {len(text):,} bytes. "
            f"Maximum allowed: {max_size:,} bytes"
        )


__all__ = [
    # Logging
    'setup_logging',
    # File operations
    'cleanup_old_files',
    'atomic_write_csv',
    # Validation
    'validate_dataset',
    'validate_input_size',
    # Leaderboard parsing
    'DATE_RE',
    'RANK1_RE',
    'RANK_RE',
    'strip_markdown',
]
