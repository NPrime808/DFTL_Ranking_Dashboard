"""
Discord Leaderboard Parser

This module parses Discord JSON exports containing DFTL_BOT leaderboard messages
and converts them into structured CSV files for analysis.

Usage:
    python -m src.ingestion.discord_parser
    OR
    python src/ingestion/discord_parser.py
"""

import sys
from pathlib import Path

# Enable both `python src/ingestion/discord_parser.py` and `python -m src.ingestion.discord_parser` execution modes.
# This ensures src.config imports work regardless of how the script is invoked.
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import json
import pandas as pd

from src.config import (
    ASSETS_FOLDER,
    OUTPUT_FOLDER,
    MIN_DATE_EARLY_ACCESS,
    AUTHOR_NAME,
)
from src.utils import (
    setup_logging,
    cleanup_old_files,
    atomic_write_csv,
    DATE_RE,
    RANK1_RE,
    RANK_RE,
    strip_markdown,
)

# --- Module Logger ---
logger = setup_logging(__name__)


def parse_leaderboard_content(content: str) -> list[tuple[str | None, str, int, int]]:
    """
    Parse one leaderboard message content into a list of rows.

    Args:
        content: Raw message content from Discord

    Returns:
        List of tuples: (date_str, player_name, rank, score)
    """
    lines = content.splitlines()
    leaderboard_rows = []
    date_found = None

    for line in lines:
        # Extract date
        if not date_found:
            m_date = DATE_RE.search(line)
            if m_date:
                date_found = m_date.group(1)

        # Extract rank 1
        m1 = RANK1_RE.match(line)
        if m1:
            name, score = m1.groups()
            leaderboard_rows.append((date_found, strip_markdown(name), 1, int(score)))
            continue

        # Extract ranks 2-30
        m = RANK_RE.match(line)
        if m:
            rank, name, score = m.groups()
            leaderboard_rows.append((date_found, strip_markdown(name), int(rank), int(score)))

    return leaderboard_rows


def load_json_files(data_folder: Path) -> list[Path]:
    """
    Discover and return all JSON files in the data folder.

    Args:
        data_folder: Path to folder containing JSON files

    Returns:
        List of JSON file paths
    """
    json_files = list(data_folder.glob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files in {data_folder}")
    return json_files


def parse_json_file(json_file: Path, author_name: str) -> list[tuple]:
    """
    Parse a single JSON file and extract leaderboard data.

    Args:
        json_file: Path to JSON file
        author_name: Expected author name for bot messages

    Returns:
        List of leaderboard row tuples
    """
    rows: list[tuple] = []

    with open(json_file, encoding="utf-8") as f:
        json_data = json.load(f)

    # Handle dict with "messages" key or plain list
    if isinstance(json_data, dict) and "messages" in json_data:
        messages_list = json_data["messages"]
    elif isinstance(json_data, list):
        messages_list = json_data
    else:
        logger.warning(f"Skipping {json_file} — unrecognized format")
        return rows

    for msg in messages_list:
        # Skip if author is not the bot
        author = msg.get("author")
        if not isinstance(author, dict) or author.get("name") != author_name:
            continue

        content = msg.get("content")
        if not content or "Top 30 Daily Leaderboard" not in content:
            continue

        try:
            parsed_rows = parse_leaderboard_content(content)
            rows.extend(parsed_rows)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse message id {msg.get('id')}: {e}")

    return rows


def run_sanity_checks(dataframe: pd.DataFrame, label: str = "DataFrame") -> bool:
    """
    Run validation checks on the leaderboard data.

    Args:
        dataframe: DataFrame to validate
        label: Label for log messages

    Returns:
        True if all checks pass, False otherwise
    """
    issues = []

    # Check for positive scores
    negative_scores = dataframe[dataframe['score'] <= 0]
    if not negative_scores.empty:
        issues.append(f"Found {len(negative_scores)} rows with non-positive scores")

    # Check each date for 30 ranks and no duplicates
    for date, group in dataframe.groupby('date'):
        date_str = date.strftime('%Y-%m-%d') if pd.notna(date) else str(date)

        # Check rank count
        if len(group) != 30:
            issues.append(f"Date {date_str}: Expected 30 ranks, found {len(group)}")

        # Check for duplicate ranks
        dup_ranks = group[group['rank'].duplicated()]['rank'].unique()
        if len(dup_ranks) > 0:
            issues.append(f"Date {date_str}: Duplicate ranks found: {list(dup_ranks)}")

        # Check rank range (should be 1-30)
        if group['rank'].min() != 1 or group['rank'].max() != 30:
            issues.append(
                f"Date {date_str}: Rank range is {group['rank'].min()}-{group['rank'].max()}, "
                f"expected 1-30"
            )

    if issues:
        logger.warning(f"Sanity Check Warnings ({label}):")
        for issue in issues[:10]:
            logger.warning(f"  - {issue}")
        if len(issues) > 10:
            logger.warning(f"  ... and {len(issues) - 10} more issues")
        return False

    logger.info(f"Sanity Check Passed ({label})")
    return True


def create_dataframe(all_rows: list[tuple]) -> pd.DataFrame:
    """
    Create and clean a DataFrame from parsed rows.

    Args:
        all_rows: List of (date, player_name, rank, score) tuples

    Returns:
        Cleaned DataFrame
    """
    df = pd.DataFrame(all_rows, columns=["date", "player_name", "rank", "score"])

    # Clean and convert dates
    df['date'] = df['date'].astype(str).str.strip(" `")
    df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')

    # Check for parsing issues
    if df['date'].isna().any():
        logger.warning("Some dates could not be parsed. Check your data.")

    # Sort and reset index
    df = df.sort_values(by=["date", "rank"]).reset_index(drop=True)

    return df


def export_datasets(
    df: pd.DataFrame,
    min_date: str,
    output_folder: Path
) -> dict:
    """
    Export full, early access, and steam demo datasets.

    Args:
        df: Full DataFrame
        min_date: Minimum date for early access (ISO format)
        output_folder: Folder to save CSV files

    Returns:
        Dictionary with export paths
    """
    output_folder.mkdir(exist_ok=True)
    result = {}

    # Filtered DataFrame for early access
    df_filtered = df[df['date'] >= pd.to_datetime(min_date)].copy()

    # Steam demo DataFrame (before early access)
    df_steam_demo = df[df['date'] < pd.to_datetime(min_date)].copy()

    # Get last dates for filenames
    last_date_full = df['date'].max().strftime('%Y%m%d')
    last_date_early_access = (
        df_filtered['date'].max().strftime('%Y%m%d')
        if not df_filtered.empty else last_date_full
    )

    # Export full dataset
    full_csv = output_folder / f"full_leaderboard_{last_date_full}.csv"
    atomic_write_csv(df, full_csv, index=False)
    cleanup_old_files("full_leaderboard_*.csv", keep_file=full_csv, folder=output_folder)
    result['full'] = full_csv
    logger.info(f"Full data: {full_csv}")

    # Export early access dataset
    early_access_csv = output_folder / f"early_access_leaderboard_{last_date_early_access}.csv"
    atomic_write_csv(df_filtered, early_access_csv, index=False)
    cleanup_old_files("early_access_leaderboard_*.csv", keep_file=early_access_csv, folder=output_folder)
    result['early_access'] = early_access_csv
    logger.info(f"Early access data: {early_access_csv}")

    # Export steam demo dataset (only if data exists)
    if not df_steam_demo.empty:
        last_date_steam_demo = df_steam_demo['date'].max().strftime('%Y%m%d')
        steam_demo_csv = output_folder / f"steam_demo_leaderboard_{last_date_steam_demo}.csv"
        atomic_write_csv(df_steam_demo, steam_demo_csv, index=False)
        cleanup_old_files("steam_demo_leaderboard_*.csv", keep_file=steam_demo_csv, folder=output_folder)
        result['steam_demo'] = steam_demo_csv
        logger.info(f"Steam demo data: {steam_demo_csv}")

    return result


def main() -> pd.DataFrame:
    """
    Main entry point for Discord leaderboard parsing.

    Returns:
        The full parsed DataFrame
    """
    logger.info("=" * 60)
    logger.info("Discord Leaderboard Parser")
    logger.info("=" * 60)

    # Load and parse all JSON files
    json_files = load_json_files(ASSETS_FOLDER)
    all_rows = []

    for json_file in json_files:
        rows = parse_json_file(json_file, AUTHOR_NAME)
        all_rows.extend(rows)

    # Create DataFrame
    df = create_dataframe(all_rows)

    # Run sanity checks
    run_sanity_checks(df, "Full DataFrame")

    # Log summary
    df_filtered = df[df['date'] >= pd.to_datetime(MIN_DATE_EARLY_ACCESS)].copy()
    df_steam_demo = df[df['date'] < pd.to_datetime(MIN_DATE_EARLY_ACCESS)].copy()

    logger.info("Summary:")
    logger.info(f"  Full DataFrame shape: {df.shape}")
    logger.info(f"  Filtered DataFrame shape: {df_filtered.shape}")
    logger.info(f"  Date range (full): {df['date'].min()} to {df['date'].max()}")
    logger.info(f"  Date range (filtered): {df_filtered['date'].min()} to {df_filtered['date'].max()}")
    logger.info(f"  Unique players (filtered): {df_filtered['player_name'].nunique()}")

    if not df_filtered.empty:
        run_sanity_checks(df_filtered, "Filtered DataFrame")

    if not df_steam_demo.empty:
        logger.info(f"  Steam Demo DataFrame shape: {df_steam_demo.shape}")
        logger.info(f"  Date range (steam_demo): {df_steam_demo['date'].min()} to {df_steam_demo['date'].max()}")
        logger.info(f"  Unique players (steam_demo): {df_steam_demo['player_name'].nunique()}")
        run_sanity_checks(df_steam_demo, "Steam Demo DataFrame")

    # Export to CSV
    logger.info("Exporting CSV files...")
    export_datasets(df, MIN_DATE_EARLY_ACCESS, OUTPUT_FOLDER)

    logger.info("=" * 60)
    logger.info("Parsing complete")
    logger.info("=" * 60)

    return df


if __name__ == "__main__":
    main()
