"""
Paste-Mode Leaderboard Ingestion

This module handles daily paste-mode ingestion of Discord leaderboard messages.
It provides a fast way to add single-day updates without exporting Discord JSON.

Usage:
    python -m src.ingestion.paste_mode
    OR
    python src/ingestion/paste_mode.py

    Programmatic usage:
        from src.ingestion.paste_mode import ingest_leaderboard_text
        result = ingest_leaderboard_text(text, dataset="early_access")
"""

import sys
from pathlib import Path

# Add project root to path for direct script execution
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pandas as pd
from datetime import datetime
from typing import List, Optional

from src.config import (
    OUTPUT_FOLDER,
    MIN_DATE_EARLY_ACCESS,
    MAX_INPUT_SIZE,
    EXPECTED_LEADERBOARD_ROWS,
)
from src.utils import (
    setup_logging,
    cleanup_old_files,
    atomic_write_csv,
    validate_dataset,
    validate_input_size,
    DATE_RE,
    RANK1_RE,
    RANK_RE,
    strip_markdown,
)

# --- Module Logger ---
logger = setup_logging(__name__)


class IngestionError(Exception):
    """Custom exception for ingestion errors"""
    pass


class ValidationError(IngestionError):
    """Validation-specific errors"""
    pass


class DuplicateDateError(IngestionError):
    """Raised when attempting to ingest a date that already exists"""
    pass


def parse_leaderboard_text(text: str) -> pd.DataFrame:
    """
    Parse a raw copy-pasted Discord leaderboard message into a DataFrame.

    Args:
        text: Raw Discord message content (copy-pasted)

    Returns:
        DataFrame with columns: date, player_name, rank, score

    Raises:
        ValidationError: If parsing fails or validation checks fail
    """
    # Validate input size
    validate_input_size(text, MAX_INPUT_SIZE)

    lines = text.strip().splitlines()
    rows = []
    date_found = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Extract date
        if date_found is None:
            m_date = DATE_RE.search(line)
            if m_date:
                date_str = m_date.group(1)
                try:
                    # Parse DD/MM/YYYY format
                    date_found = datetime.strptime(date_str, "%d/%m/%Y").date()
                except ValueError as e:
                    raise ValidationError(f"Failed to parse date '{date_str}': {e}")

        # Extract rank 1 (crown emoji)
        m1 = RANK1_RE.search(line)
        if m1:
            name, score = m1.groups()
            rows.append({
                'date': date_found,
                'player_name': strip_markdown(name),
                'rank': 1,
                'score': int(score)
            })
            continue

        # Extract ranks 2-30
        m = RANK_RE.search(line)
        if m:
            rank, name, score = m.groups()
            rows.append({
                'date': date_found,
                'player_name': strip_markdown(name),
                'rank': int(rank),
                'score': int(score)
            })

    if date_found is None:
        raise ValidationError("Could not find date in leaderboard text. Expected format: 'date: DD/MM/YYYY'")

    if not rows:
        raise ValidationError("No leaderboard entries found in text")

    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])

    return df


def validate_leaderboard(df: pd.DataFrame) -> List[str]:
    """
    Validate parsed leaderboard data.

    Args:
        df: DataFrame with date, player_name, rank, score columns

    Returns:
        List of warning messages (empty if all validations pass)

    Raises:
        ValidationError: If critical validations fail
    """
    warnings = []

    # Check row count (must be exactly 30)
    if len(df) != EXPECTED_LEADERBOARD_ROWS:
        raise ValidationError(f"Expected exactly {EXPECTED_LEADERBOARD_ROWS} rows, found {len(df)}")

    # Check unique ranks (must be 1-30)
    ranks = set(df['rank'].tolist())
    expected_ranks = set(range(1, EXPECTED_LEADERBOARD_ROWS + 1))

    if ranks != expected_ranks:
        missing = expected_ranks - ranks
        extra = ranks - expected_ranks
        msg = "Rank validation failed:"
        if missing:
            msg += f" Missing ranks: {sorted(missing)}"
        if extra:
            msg += f" Unexpected ranks: {sorted(extra)}"
        raise ValidationError(msg)

    # Check for duplicate ranks
    dup_ranks = df[df['rank'].duplicated()]['rank'].unique()
    if len(dup_ranks) > 0:
        raise ValidationError(f"Duplicate ranks found: {list(dup_ranks)}")

    # Check for non-positive scores (soft warning)
    non_positive = df[df['score'] <= 0]
    if not non_positive.empty:
        warnings.append(f"Found {len(non_positive)} rows with non-positive scores")

    # Check if scores are weakly decreasing by rank (soft warning)
    df_sorted = df.sort_values('rank')
    scores = df_sorted['score'].tolist()
    non_decreasing_count = sum(1 for i in range(len(scores)-1) if scores[i] < scores[i+1])
    if non_decreasing_count > 0:
        warnings.append(f"Scores not strictly decreasing: {non_decreasing_count} inversions found")

    return warnings


def get_existing_dates(dataset: str = "early_access") -> set:
    """
    Get set of dates already in the dataset.

    Args:
        dataset: One of "early_access" or "full"

    Returns:
        Set of datetime.date objects
    """
    validate_dataset(dataset)

    pattern = f"{dataset}_leaderboard_*.csv"
    files = sorted(OUTPUT_FOLDER.glob(pattern))

    if not files:
        return set()

    # Load most recent file
    df = pd.read_csv(files[-1], parse_dates=['date'])
    return set(df['date'].dt.date)


def check_duplicate_date(date: datetime, dataset: str = "early_access") -> None:
    """
    Check if a date already exists in the dataset.

    Args:
        date: Date to check
        dataset: Dataset to check against

    Raises:
        DuplicateDateError: If the date already exists
    """
    existing_dates = get_existing_dates(dataset)

    if isinstance(date, datetime):
        date = date.date()
    elif isinstance(date, pd.Timestamp):
        date = date.date()

    if date in existing_dates:
        raise DuplicateDateError(
            f"Leaderboard for {date.strftime('%Y-%m-%d')} already exists in {dataset} dataset"
        )


def append_to_dataset(df_new: pd.DataFrame, dataset: str = "early_access") -> Path:
    """
    Append new leaderboard data to the existing dataset CSV.

    Args:
        df_new: DataFrame with new leaderboard data
        dataset: Target dataset

    Returns:
        Path to the updated CSV file
    """
    validate_dataset(dataset)

    pattern = f"{dataset}_leaderboard_*.csv"
    files = sorted(OUTPUT_FOLDER.glob(pattern))

    if not files:
        raise IngestionError(f"No existing {dataset} leaderboard file found")

    existing_file = files[-1]

    # Load existing data
    df_existing = pd.read_csv(existing_file, parse_dates=['date'])

    # Append new data
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)

    # Sort by date and rank
    df_combined = df_combined.sort_values(['date', 'rank']).reset_index(drop=True)

    # Determine new filename based on latest date
    new_last_date = df_combined['date'].max().strftime('%Y%m%d')
    new_filename = f"{dataset}_leaderboard_{new_last_date}.csv"
    new_path = OUTPUT_FOLDER / new_filename

    # Save updated dataset atomically
    atomic_write_csv(df_combined, new_path, index=False)

    # Clean up old leaderboard files (keep only the new one)
    cleanup_old_files(pattern, keep_file=new_path, folder=OUTPUT_FOLDER)

    # Also update full dataset if we're updating early_access
    if dataset == "early_access":
        _update_full_dataset(df_new)

    return new_path


def _update_full_dataset(df_new: pd.DataFrame) -> Optional[Path]:
    """
    Update the full leaderboard dataset with new data.

    Args:
        df_new: DataFrame with new leaderboard data

    Returns:
        Path to updated full dataset, or None if no full dataset exists
    """
    pattern = "full_leaderboard_*.csv"
    files = sorted(OUTPUT_FOLDER.glob(pattern))

    if not files:
        return None

    existing_file = files[-1]
    df_existing = pd.read_csv(existing_file, parse_dates=['date'])

    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined = df_combined.sort_values(['date', 'rank']).reset_index(drop=True)

    new_last_date = df_combined['date'].max().strftime('%Y%m%d')
    new_filename = f"full_leaderboard_{new_last_date}.csv"
    new_path = OUTPUT_FOLDER / new_filename

    atomic_write_csv(df_combined, new_path, index=False)

    # Clean up old full leaderboard files
    cleanup_old_files(pattern, keep_file=new_path, folder=OUTPUT_FOLDER)

    return new_path


def run_elo_update() -> dict:
    """
    Trigger the Elo ranking update pipeline.

    Returns:
        Results dictionary from the Elo ranking module
    """
    from src.elo.engine import main as elo_main
    return elo_main()


def ingest_leaderboard_text(
    text: str,
    dataset: str = "early_access",
    run_elo: bool = True,
    dry_run: bool = False
) -> dict:
    """
    Main entry point for paste-mode ingestion.

    Args:
        text: Raw Discord leaderboard message (copy-pasted)
        dataset: Target dataset ("early_access" or "full")
        run_elo: Whether to trigger Elo recomputation after ingestion
        dry_run: If True, validate only without saving

    Returns:
        Dictionary with:
            - success: bool
            - date: parsed date
            - rows: number of rows parsed
            - warnings: list of warning messages
            - csv_path: path to updated CSV (if not dry_run)
            - elo_results: Elo computation results (if run_elo=True)
            - rivalries_results: Rivalries computation results (if run_elo=True)

    Raises:
        ValidationError: If validation fails
        DuplicateDateError: If date already exists
        IngestionError: If ingestion fails
    """
    # Validate dataset parameter
    validate_dataset(dataset)

    result = {
        'success': False,
        'date': None,
        'rows': 0,
        'warnings': [],
        'csv_path': None,
        'elo_results': None,
        'rivalries_results': None
    }

    # Step 1: Parse the text
    logger.info("Parsing leaderboard text...")
    df = parse_leaderboard_text(text)
    result['date'] = df['date'].iloc[0].date()
    result['rows'] = len(df)
    logger.info(f"  Parsed {len(df)} rows for date {result['date']}")

    # Step 2: Validate
    logger.info("Validating data...")
    warnings = validate_leaderboard(df)
    result['warnings'] = warnings
    if warnings:
        for w in warnings:
            logger.warning(f"  Warning: {w}")
    else:
        logger.info("  All validations passed")

    # Step 3: Check for duplicate date
    logger.info(f"Checking for duplicate date in {dataset}...")
    check_duplicate_date(df['date'].iloc[0], dataset)
    logger.info("  No duplicate found")

    if dry_run:
        logger.info("[DRY RUN] Validation complete. No data was saved.")
        result['success'] = True
        return result

    # Step 4: Append to dataset
    logger.info(f"Appending to {dataset} dataset...")
    csv_path = append_to_dataset(df, dataset)
    result['csv_path'] = csv_path
    logger.info(f"  Saved to {csv_path}")

    # Step 5: Run Elo update (includes rivalries computation)
    if run_elo:
        logger.info("Triggering Elo ranking update...")
        elo_results = run_elo_update()
        result['elo_results'] = elo_results
        # Rivalries results are included in elo_results['rivalries']
        result['rivalries_results'] = elo_results.get('rivalries') if elo_results else None
        logger.info("  Elo and rivalries update complete")

    result['success'] = True
    logger.info(f"Ingestion complete for {result['date']}")
    return result


def main():
    """CLI interface for paste-mode ingestion."""
    import sys

    print("=" * 60)
    print("DFTL Paste-Mode Leaderboard Ingestion")
    print("=" * 60)
    print("\nPaste the Discord leaderboard message below.")
    print("When finished, press Enter twice (empty line) to process.\n")
    print("-" * 60)

    lines = []
    empty_count = 0

    try:
        while True:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
                lines.append(line)
            else:
                empty_count = 0
                lines.append(line)
    except EOFError:
        pass

    text = "\n".join(lines)

    if not text.strip():
        print("\nNo input received. Exiting.")
        sys.exit(1)

    print("-" * 60)
    print("\nProcessing input...\n")

    try:
        # First do a dry run to validate
        print("Step 1: Validation (dry run)")
        result = ingest_leaderboard_text(text, dry_run=True)

        # Ask for confirmation
        print(f"\nReady to ingest data for {result['date']}.")
        confirm = input("Proceed with ingestion? [y/N]: ").strip().lower()

        if confirm != 'y':
            print("Ingestion cancelled.")
            sys.exit(0)

        # Do the actual ingestion
        print("\nStep 2: Ingestion")
        result = ingest_leaderboard_text(text, dry_run=False)

        print("\n" + "=" * 60)
        print("SUCCESS!")
        print(f"  Date: {result['date']}")
        print(f"  Rows: {result['rows']}")
        print(f"  CSV: {result['csv_path']}")
        if result['warnings']:
            print(f"  Warnings: {len(result['warnings'])}")
        print("=" * 60)

    except ValidationError as e:
        print(f"\nVALIDATION ERROR: {e}")
        sys.exit(1)
    except DuplicateDateError as e:
        print(f"\nDUPLICATE DATE ERROR: {e}")
        sys.exit(1)
    except IngestionError as e:
        print(f"\nINGESTION ERROR: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\nINPUT ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
