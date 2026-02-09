"""
Rivalry Statistics Computation for DFTL

This module computes head-to-head rivalry statistics from Elo history data.
It identifies the greatest rivalries based on multiple metrics:
- Most Battles: Pairs with the most head-to-head encounters
- Closest Rivals: Pairs with the tightest win records (closest to 50-50)
- Elite Showdowns: Top players who frequently battle each other

Usage:
    python -m src.elo.rivalries
    OR
    from src.elo.rivalries import compute_rivalries, process_rivalries
"""

import sys
from pathlib import Path

# Enable both `python src/elo/rivalries.py` and `python -m src.elo.rivalries` execution modes.
# This ensures src.config imports work regardless of how the script is invoked.
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from collections import defaultdict
from itertools import combinations

import numpy as np
import pandas as pd

from src.config import EARLY_ACCESS_PATTERN, FULL_PATTERN, OUTPUT_FOLDER
from src.utils import atomic_write_csv, cleanup_old_files, setup_logging

# --- Module Logger ---
logger = setup_logging(__name__)

# --- Configuration ---
MIN_ENCOUNTERS = 7  # Minimum games to qualify as a rivalry
TOP_N_RIVALRIES = 10  # Number of rivalries to include per category
GAP_PENALTY_K = 20  # Controls how much absolute win gap affects closeness


def compute_rivalries(df_history: pd.DataFrame) -> pd.DataFrame:
    """
    Compute rivalry statistics for all player pairs.

    Args:
        df_history: DataFrame with columns [date, player_name, rank, score, ...]
                   Rows with NaN rank are players who didn't play that day.

    Returns:
        DataFrame with rivalry stats for each qualifying pair:
        - player1, player2: Player names (alphabetically ordered)
        - total_encounters: Days both players participated
        - p1_wins, p2_wins: Number of wins for each player
        - p1_avg_rank, p2_avg_rank: Average rank when they met
        - closeness: ratio_closeness × gap_penalty (penalizes large absolute gaps)
        - elite_score: total_encounters / avg_combined_rank (higher = more elite)
    """
    logger.info("Computing rivalry statistics...")

    # Filter to rows where player actually played (has a rank)
    df_played = df_history[df_history['rank'].notna()].copy()
    df_played['rank'] = df_played['rank'].astype(int)

    if df_played.empty:
        logger.warning("No played games found in history")
        return pd.DataFrame()

    # Group by date and collect players who played each day
    logger.info("Grouping games by date...")
    games_by_date = df_played.groupby('date')[['player_name', 'rank']].apply(
        lambda x: x.set_index('player_name')['rank'].to_dict(),
        include_groups=False
    ).to_dict()

    # Track head-to-head stats for each pair
    # Key: (player1, player2) where player1 < player2 alphabetically
    rivalry_stats: defaultdict[tuple[str, str], dict] = defaultdict(lambda: {
        'encounters': 0,
        'p1_wins': 0,
        'p2_wins': 0,
        'p1_ranks': [],
        'p2_ranks': [],
    })

    logger.info(f"Processing {len(games_by_date)} days of games...")

    for _, players_ranks in games_by_date.items():
        players = list(players_ranks.keys())

        # Generate all pairs for this day
        for p1, p2 in combinations(players, 2):
            # Ensure consistent ordering (alphabetical)
            if p1 > p2:
                p1, p2 = p2, p1

            rank1 = players_ranks[p1 if p1 in players_ranks else p2]
            rank2 = players_ranks[p2 if p2 in players_ranks else p1]

            # Re-fetch with correct ordering
            rank1 = players_ranks.get(p1)
            rank2 = players_ranks.get(p2)

            if rank1 is None or rank2 is None:
                continue

            key = (p1, p2)
            rivalry_stats[key]['encounters'] += 1
            rivalry_stats[key]['p1_ranks'].append(rank1)
            rivalry_stats[key]['p2_ranks'].append(rank2)

            # Lower rank = winner
            if rank1 < rank2:
                rivalry_stats[key]['p1_wins'] += 1
            elif rank2 < rank1:
                rivalry_stats[key]['p2_wins'] += 1
            # Ties: neither gets a win

    logger.info(f"Found {len(rivalry_stats)} total player pairs")

    # Convert to DataFrame
    rows = []
    for (p1, p2), stats in rivalry_stats.items():
        if stats['encounters'] < MIN_ENCOUNTERS:
            continue

        p1_avg_rank = np.mean(stats['p1_ranks'])
        p2_avg_rank = np.mean(stats['p2_ranks'])
        avg_combined_rank = (p1_avg_rank + p2_avg_rank) / 2

        total = stats['encounters']
        win_diff = abs(stats['p1_wins'] - stats['p2_wins'])

        # Closeness with gap penalty:
        # - Ratio component: 1 - (diff/total) - how close the win% is to 50-50
        # - Gap penalty: 1 / (1 + diff/k) - penalizes large absolute gaps
        # This means 36-24 (gap=12) feels closer than 72-48 (gap=24) even at same ratio
        ratio_closeness = 1 - (win_diff / total) if total > 0 else 0
        gap_penalty = 1 / (1 + win_diff / GAP_PENALTY_K)
        closeness = ratio_closeness * gap_penalty

        # Elite score: more encounters at higher ranks = higher score
        elite_score = total / avg_combined_rank if avg_combined_rank > 0 else 0

        rows.append({
            'player1': p1,
            'player2': p2,
            'total_encounters': total,
            'p1_wins': stats['p1_wins'],
            'p2_wins': stats['p2_wins'],
            'p1_avg_rank': round(p1_avg_rank, 2),
            'p2_avg_rank': round(p2_avg_rank, 2),
            'avg_combined_rank': round(avg_combined_rank, 2),
            'closeness': round(closeness, 4),
            'elite_score': round(elite_score, 2),
        })

    df_rivalries = pd.DataFrame(rows)
    logger.info(f"Found {len(df_rivalries)} qualifying rivalries (>= {MIN_ENCOUNTERS} encounters)")

    return df_rivalries


def get_top_rivalries(df_rivalries: pd.DataFrame, n: int = TOP_N_RIVALRIES) -> dict:
    """
    Get top N rivalries for each category.

    Returns:
        dict with keys 'most_battles', 'closest', 'elite' containing DataFrames
    """
    if df_rivalries.empty:
        return {
            'most_battles': pd.DataFrame(),
            'closest': pd.DataFrame(),
            'elite': pd.DataFrame(),
        }

    return {
        'most_battles': df_rivalries.nlargest(n, 'total_encounters'),
        'closest': df_rivalries.nlargest(n, 'closeness'),
        'elite': df_rivalries.nlargest(n, 'elite_score'),
    }


def process_rivalries(history_csv: Path, output_prefix: str, label: str) -> pd.DataFrame:
    """
    Process rivalry statistics for a dataset.

    Args:
        history_csv: Path to the Elo history CSV file
        output_prefix: Prefix for output files (e.g., 'early_access', 'full')
        label: Human-readable label for logging

    Returns:
        DataFrame with all qualifying rivalries
    """
    logger.info(f"Processing rivalries for {label} dataset...")

    if not history_csv.exists():
        logger.warning(f"History file not found: {history_csv}")
        return pd.DataFrame()

    # Load history data
    df_history = pd.read_csv(history_csv, parse_dates=['date'])
    logger.info(f"Loaded {len(df_history)} history records")

    # Compute rivalries
    df_rivalries = compute_rivalries(df_history)

    if df_rivalries.empty:
        logger.warning(f"No qualifying rivalries found for {label}")
        return df_rivalries

    # Extract date from history filename (e.g., early_access_elo_history_20250131.csv)
    # This ensures rivalries date matches the data's last date, not today's date
    date_str = history_csv.stem.split('_')[-1]  # Get YYYYMMDD from filename
    output_csv = OUTPUT_FOLDER / f"{output_prefix}_rivalries_{date_str}.csv"

    atomic_write_csv(df_rivalries, output_csv, index=False)
    logger.info(f"Exported rivalries to: {output_csv}")

    # Clean up old rivalries files (keep only the new one)
    cleanup_old_files(f"{output_prefix}_rivalries_*.csv", keep_file=output_csv, folder=OUTPUT_FOLDER)

    # Log top rivalries for each category
    top = get_top_rivalries(df_rivalries, n=5)

    logger.info(f"\nTop 5 Most Battles ({label}):")
    for _, row in top['most_battles'].head().iterrows():
        logger.info(f"  {row['player1']} vs {row['player2']}: {row['total_encounters']} games ({row['p1_wins']}-{row['p2_wins']})")

    logger.info(f"\nTop 5 Closest Rivals ({label}):")
    for _, row in top['closest'].head().iterrows():
        logger.info(f"  {row['player1']} vs {row['player2']}: {row['closeness']:.1%} close ({row['p1_wins']}-{row['p2_wins']})")

    logger.info(f"\nTop 5 Elite Showdowns ({label}):")
    for _, row in top['elite'].head().iterrows():
        logger.info(f"  {row['player1']} vs {row['player2']}: score {row['elite_score']:.1f} (avg rank {row['avg_combined_rank']:.1f})")

    return df_rivalries


def find_latest_history(pattern: str) -> Path | None:
    """Find the most recent history CSV matching the pattern."""
    prefix = "early_access" if "early" in pattern.lower() else "full"
    history_files = list(OUTPUT_FOLDER.glob(f"{prefix}_elo_history_*.csv"))

    if not history_files:
        return None

    # Sort by date in filename (descending)
    history_files.sort(key=lambda p: p.stem.split('_')[-1], reverse=True)
    return history_files[0]


def main():
    """Process rivalries for all datasets."""
    results = {}

    # Early Access dataset
    ea_history = find_latest_history(EARLY_ACCESS_PATTERN)
    if ea_history:
        ea_rivalries = process_rivalries(ea_history, "early_access", "Early Access")
        if not ea_rivalries.empty:
            results['early_access'] = ea_rivalries
    else:
        logger.warning("No Early Access history file found")

    # Full dataset
    full_history = find_latest_history(FULL_PATTERN)
    if full_history:
        full_rivalries = process_rivalries(full_history, "full", "Full")
        if not full_rivalries.empty:
            results['full'] = full_rivalries
    else:
        logger.warning("No Full history file found")

    return results


if __name__ == "__main__":
    results = main()
