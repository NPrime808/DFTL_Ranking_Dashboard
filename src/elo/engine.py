"""
Elo Ranking Engine for DFTL

This module computes Elo ratings from daily leaderboard data using a pairwise
comparison model. It supports multiple datasets and includes features like:
- Dynamic K-factor based on games played
- Uncertainty amplification for inactive players
- Activity gating to filter inactive players from rankings
- Soft rating compression to prevent extreme values

Usage:
    python -m src.elo.engine
    OR
    from src.elo import run_elo, compute_elo_ratings
"""

import sys
from pathlib import Path

# Enable both `python src/elo/engine.py` and `python -m src.elo.engine` execution.
# Required for src.config/src.utils imports to resolve correctly.
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import math
import statistics
import pandas as pd
from collections import defaultdict

from src.config import (
    OUTPUT_FOLDER,
    BASELINE_RATING,
    K_NORMALIZED,
    RATING_FLOOR,
    FLOOR_SOFT_ZONE,
    TARGET_MIN_RATING,
    TARGET_MAX_RATING,
    USE_HYBRID_COMPRESSION,
    SOFT_TARGET,
    HARD_CEILING,
    USE_DYNAMIC_K,
    DYNAMIC_K_NEW_PLAYER_GAMES,
    DYNAMIC_K_ESTABLISHED_GAMES,
    DYNAMIC_K_NEW_MULTIPLIER,
    DYNAMIC_K_PROVISIONAL_MULTIPLIER,
    USE_UNCERTAINTY,
    UNCERTAINTY_BASE,
    UNCERTAINTY_GROWTH_RATE,
    UNCERTAINTY_MAX,
    UNCERTAINTY_DECAY_RATE,
    USE_ACTIVITY_GATING,
    ACTIVITY_WINDOW_DAYS,
    MIN_GAMES_FOR_RANKING,
    ELO_MODEL,
    USE_LOG_SCALING,
    LOG_SCALE_FACTOR,
    USE_SCORE_GAP_WEIGHTING,
    USE_RATIO_BASED_WEIGHTING,
    RATIO_CAP,
    DAILY_K_FACTOR,
    DAILY_K_NEW_MULTIPLIER,
    DAILY_K_PROVISIONAL_MULTIPLIER,
    EARLY_ACCESS_PATTERN,
    FULL_PATTERN,
)
from src.utils import setup_logging, cleanup_old_files, atomic_write_csv
from src.elo.compression import scale_ratings_soft, scale_ratings_hybrid, create_rating_scaler

# --- Module Logger ---
logger = setup_logging(__name__)

# Fix Windows console encoding for Unicode characters
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[union-attr]
    except AttributeError:
        pass  # Python < 3.7


def expected_score(rating_a, rating_b):
    """Calculate expected probability of player A beating player B"""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def calculate_weight(score_i, score_j, max_gap):
    """
    Calculate weight based on score gap.

    Two modes:
    - Ratio-based (logarithmic): Rewards dominant performances where score_i >> score_j
      A 10x score ratio = maximum weight
    - Linear gap: Original method using absolute score difference
    """
    if not USE_SCORE_GAP_WEIGHTING:
        return 1.0

    if USE_RATIO_BASED_WEIGHTING and score_j > 0:
        ratio = score_i / score_j
        # log2(1) = 0 (tied), log2(10) ≈ 3.32 (dominant)
        # Normalize so ratio of RATIO_CAP (default 10x) maps to weight 1.0
        log_ratio = math.log2(max(ratio, 1.0))
        log_cap = math.log2(RATIO_CAP)
        weight = 0.5 + 0.5 * min(log_ratio / log_cap, 1.0)
        return weight

    # Fallback to linear gap method
    if max_gap == 0:
        return 1.0
    gap = score_i - score_j
    return 0.5 + 0.5 * (gap / max_gap)


def get_dynamic_k(games_played):
    """
    Calculate dynamic K-factor based on games played.
    New players adjust faster, established players are more stable.
    """
    if not USE_DYNAMIC_K:
        return K_NORMALIZED

    if games_played < DYNAMIC_K_NEW_PLAYER_GAMES:
        return K_NORMALIZED * DYNAMIC_K_NEW_MULTIPLIER
    elif games_played < DYNAMIC_K_ESTABLISHED_GAMES:
        return K_NORMALIZED * DYNAMIC_K_PROVISIONAL_MULTIPLIER
    else:
        return K_NORMALIZED


def calculate_confidence(games_played, threshold=30):
    """
    Calculate confidence score (0-1) based on games played.
    Confidence reaches 1.0 after threshold games.
    """
    return min(1.0, games_played / threshold)


def get_daily_k(games_played):
    """
    Calculate K-factor for daily result model based on games played.
    """
    if not USE_DYNAMIC_K:
        return DAILY_K_FACTOR

    if games_played < DYNAMIC_K_NEW_PLAYER_GAMES:
        return DAILY_K_FACTOR * DAILY_K_NEW_MULTIPLIER
    elif games_played < DYNAMIC_K_ESTABLISHED_GAMES:
        return DAILY_K_FACTOR * DAILY_K_PROVISIONAL_MULTIPLIER
    else:
        return DAILY_K_FACTOR


def calculate_uncertainty(inactivity_days):
    """
    Calculate uncertainty multiplier based on days of inactivity.
    """
    if not USE_UNCERTAINTY:
        return 1.0

    return min(
        UNCERTAINTY_MAX,
        UNCERTAINTY_BASE + inactivity_days * UNCERTAINTY_GROWTH_RATE
    )


def decay_uncertainty(current_uncertainty):
    """
    Decay uncertainty toward base after an active day.
    """
    if not USE_UNCERTAINTY:
        return 1.0

    excess = current_uncertainty - UNCERTAINTY_BASE
    return UNCERTAINTY_BASE + excess * (1 - UNCERTAINTY_DECAY_RATE)


def calculate_floor_factor(loser_rating):
    """
    Calculate the floor factor for winner gains when beating a near-floor player.
    """
    if loser_rating >= RATING_FLOOR + FLOOR_SOFT_ZONE:
        return 1.0
    elif loser_rating <= RATING_FLOOR:
        return 0.0
    else:
        return (loser_rating - RATING_FLOOR) / FLOOR_SOFT_ZONE


def process_daily_result_model(leaderboard_df, ratings, games_played, last_seen, uncertainty, date):
    """
    Process one day's leaderboard using the Daily Result Model.
    """
    players = leaderboard_df.sort_values('rank').to_dict('records')
    n = len(players)

    for p in players:
        name = p['player_name']
        if name not in ratings:
            ratings[name] = BASELINE_RATING
            games_played[name] = 0
            uncertainty[name] = UNCERTAINTY_BASE

    player_uncertainty = {}
    for p in players:
        name = p['player_name']
        if name in last_seen:
            days_inactive = (date - last_seen[name]).days
            uncertainty[name] = calculate_uncertainty(days_inactive)
        player_uncertainty[name] = uncertainty[name]

    players_with_elo = [(p['player_name'], ratings[p['player_name']]) for p in players]
    players_sorted_by_elo = sorted(players_with_elo, key=lambda x: x[1], reverse=True)

    expected_rank = {}
    i = 0
    while i < len(players_sorted_by_elo):
        current_elo = players_sorted_by_elo[i][1]
        j = i
        while j < len(players_sorted_by_elo) and players_sorted_by_elo[j][1] == current_elo:
            j += 1
        avg_rank = (i + 1 + j) / 2
        for k in range(i, j):
            expected_rank[players_sorted_by_elo[k][0]] = avg_rank
        i = j

    actual_rank = {p['player_name']: p['rank'] for p in players}
    rating_changes = {}

    for p in players:
        name = p['player_name']
        expected = expected_rank[name]
        actual = actual_rank[name]
        performance = (expected - actual) / (n - 1)
        k = get_daily_k(games_played[name])
        delta = k * performance
        if delta < 0:
            delta *= player_uncertainty[name]
        rating_changes[name] = delta

    for name, delta in rating_changes.items():
        ratings[name] += delta
        if ratings[name] < RATING_FLOOR:
            ratings[name] = RATING_FLOOR
        games_played[name] += 1
        last_seen[name] = date
        uncertainty[name] = decay_uncertainty(player_uncertainty[name])

    return rating_changes, player_uncertainty


def process_daily_leaderboard(leaderboard_df, ratings, games_played, last_seen, uncertainty, date):
    """
    Process one day's leaderboard and update ratings using pairwise comparisons.
    """
    players = leaderboard_df.sort_values('rank').to_dict('records')
    n = len(players)

    for p in players:
        name = p['player_name']
        if name not in ratings:
            ratings[name] = BASELINE_RATING
            games_played[name] = 0
            uncertainty[name] = UNCERTAINTY_BASE

    player_uncertainty = {}
    for p in players:
        name = p['player_name']
        if name in last_seen:
            days_inactive = (date - last_seen[name]).days
            uncertainty[name] = calculate_uncertainty(days_inactive)
        player_uncertainty[name] = uncertainty[name]

    max_gap = players[0]['score'] - players[-1]['score'] if n > 1 else 1
    rating_changes = defaultdict(float)

    for i in range(n):
        for j in range(i + 1, n):
            player_i = players[i]
            player_j = players[j]
            name_i = player_i['player_name']
            name_j = player_j['player_name']
            r_i = ratings[name_i]
            r_j = ratings[name_j]
            e_i = expected_score(r_i, r_j)
            weight = calculate_weight(player_i['score'], player_j['score'], max_gap)
            k_i = get_dynamic_k(games_played[name_i])
            k_j = get_dynamic_k(games_played[name_j])
            delta_i = k_i * weight * (1 - e_i)
            floor_factor = calculate_floor_factor(r_j)
            delta_i *= floor_factor
            delta_j = k_j * weight * (e_i - 1)
            rating_changes[name_i] += delta_i
            rating_changes[name_j] += delta_j

    if USE_LOG_SCALING:
        for name in rating_changes:
            raw_delta = rating_changes[name]
            if raw_delta != 0:
                sign = 1 if raw_delta > 0 else -1
                compressed = sign * LOG_SCALE_FACTOR * math.log(1 + abs(raw_delta) / LOG_SCALE_FACTOR)
                rating_changes[name] = compressed

    for name, delta in rating_changes.items():
        if delta < 0:
            delta *= player_uncertainty[name]
        ratings[name] += delta
        if ratings[name] < RATING_FLOOR:
            ratings[name] = RATING_FLOOR
        games_played[name] += 1
        last_seen[name] = date
        uncertainty[name] = decay_uncertainty(player_uncertainty[name])

    final_changes = {}
    for name, delta in rating_changes.items():
        if delta < 0:
            final_changes[name] = delta * player_uncertainty[name]
        else:
            final_changes[name] = delta

    return final_changes, player_uncertainty


def compute_elo_ratings(df):
    """
    Run Elo ranking on the full dataset.

    Args:
        df: DataFrame with columns [date, player_name, rank, score]

    Returns:
        Tuple of (final_ratings_df, daily_history_df, all_players_df)
    """
    ratings = {}
    games_played = defaultdict(int)
    last_seen = {}
    uncertainty = {}
    daily_history = []

    dates = sorted(df['date'].unique())
    logger.info(f"Processing {len(dates)} days of leaderboard data using '{ELO_MODEL}' model...")

    for date in dates:
        day_df = df[df['date'] == date]

        if ELO_MODEL == "daily_result":
            changes, day_uncertainty = process_daily_result_model(
                day_df, ratings, games_played, last_seen, uncertainty, date
            )
        else:
            changes, day_uncertainty = process_daily_leaderboard(
                day_df, ratings, games_played, last_seen, uncertainty, date
            )

        active_players_today = set()
        for player, player_last_seen in last_seen.items():
            days_since_seen = (date - player_last_seen).days
            if days_since_seen <= ACTIVITY_WINDOW_DAYS and games_played[player] >= MIN_GAMES_FOR_RANKING:
                active_players_today.add(player)

        active_ratings = [(player, ratings[player]) for player in active_players_today]
        active_ratings.sort(key=lambda x: x[1], reverse=True)
        active_rank_map = {player: rank + 1 for rank, (player, _) in enumerate(active_ratings)}

        for player, rating in ratings.items():
            active_rank = active_rank_map.get(player, None)
            daily_history.append({
                'date': date,
                'player_name': player,
                'rating': rating,
                'games_played': games_played[player],
                'uncertainty': uncertainty.get(player, UNCERTAINTY_BASE),
                'active_rank': active_rank
            })

    logger.info(f"Processed {len(dates)} days, {len(ratings)} unique players")

    raw_values = list(ratings.values())
    if raw_values:
        logger.info("Raw Rating Distribution (before compression):")
        logger.info(f"  Min: {min(raw_values):.2f}")
        logger.info(f"  Max: {max(raw_values):.2f}")
        logger.info(f"  Spread: {max(raw_values) - min(raw_values):.2f}")
        logger.info(f"  Mean: {statistics.mean(raw_values):.2f}")
        logger.info(f"  Median: {statistics.median(raw_values):.2f}")
        logger.info(f"  Std Dev: {statistics.stdev(raw_values) if len(raw_values) > 1 else 0:.2f}")

    if USE_HYBRID_COMPRESSION:
        scaled_ratings = scale_ratings_hybrid(
            ratings, BASELINE_RATING, TARGET_MIN_RATING, TARGET_MAX_RATING,
            hard_ceiling=HARD_CEILING
        )
        compression_method = f"hybrid (log→{SOFT_TARGET}, tanh→{HARD_CEILING})"
    else:
        scaled_ratings = scale_ratings_soft(ratings, BASELINE_RATING, TARGET_MIN_RATING, TARGET_MAX_RATING)
        compression_method = f"tanh (ceiling={TARGET_MAX_RATING})"

    scaled_values = list(scaled_ratings.values())
    if scaled_values:
        logger.info(f"Compressed Rating Distribution (after {compression_method} scaling):")
        logger.info(f"  Min: {min(scaled_values):.2f}")
        logger.info(f"  Max: {max(scaled_values):.2f}")
        logger.info(f"  Spread: {max(scaled_values) - min(scaled_values):.2f}")
        logger.info(f"  Mean: {statistics.mean(scaled_values):.2f}")
        logger.info(f"  Median: {statistics.median(scaled_values):.2f}")
        logger.info(f"  Std Dev: {statistics.stdev(scaled_values) if len(scaled_values) > 1 else 0:.2f}")

    last_date = dates[-1] if dates else None

    final_ratings = []
    for player, rating in scaled_ratings.items():
        gp = games_played[player]
        player_last_seen = last_seen[player]
        days_inactive = (last_date - player_last_seen).days if last_date else 0
        is_active = (days_inactive <= ACTIVITY_WINDOW_DAYS and gp >= MIN_GAMES_FOR_RANKING) if USE_ACTIVITY_GATING else True

        final_ratings.append({
            'player_name': player,
            'rating': round(rating, 2),
            'raw_rating': round(ratings[player], 2),
            'games_played': gp,
            'confidence': round(calculate_confidence(gp, DYNAMIC_K_ESTABLISHED_GAMES), 2),
            'last_seen': player_last_seen,
            'days_inactive': days_inactive,
            'uncertainty': round(uncertainty.get(player, UNCERTAINTY_BASE), 3),
            'is_active': is_active
        })

    final_df = pd.DataFrame(final_ratings)

    all_players_df = final_df.copy()
    all_players_df = all_players_df.sort_values('rating', ascending=False).reset_index(drop=True)
    all_players_df['active_rank'] = None
    active_mask = all_players_df['is_active']
    active_sorted = all_players_df[active_mask].sort_values('rating', ascending=False)
    for i, idx in enumerate(active_sorted.index):
        all_players_df.loc[idx, 'active_rank'] = i + 1

    if USE_ACTIVITY_GATING:
        final_df = final_df[final_df['is_active']].copy()

    final_df = final_df.sort_values('rating', ascending=False).reset_index(drop=True)
    final_df['active_rank'] = final_df.index + 1

    final_df = final_df[['active_rank', 'player_name', 'rating', 'raw_rating', 'games_played', 'confidence', 'last_seen', 'days_inactive', 'uncertainty', 'is_active']]
    all_players_df = all_players_df[['active_rank', 'player_name', 'rating', 'raw_rating', 'games_played', 'confidence', 'last_seen', 'days_inactive', 'uncertainty', 'is_active']]

    history_df = pd.DataFrame(daily_history)

    scale_single_rating = create_rating_scaler(
        ratings,
        use_hybrid=USE_HYBRID_COMPRESSION,
        baseline=BASELINE_RATING,
        target_min=TARGET_MIN_RATING,
        hard_ceiling=HARD_CEILING
    )

    history_df['rating'] = history_df['rating'].apply(scale_single_rating).round(2)
    history_df = history_df.sort_values(['player_name', 'date']).reset_index(drop=True)
    history_df['rating_change'] = history_df.groupby('player_name')['rating'].diff().round(2)
    first_game_mask = history_df['rating_change'].isna()
    history_df.loc[first_game_mask, 'rating_change'] = (
        history_df.loc[first_game_mask, 'rating'] - BASELINE_RATING
    ).round(2)

    history_df = history_df.merge(
        df[['date', 'player_name', 'rank', 'score']],
        on=['date', 'player_name'],
        how='left'
    )

    history_df = history_df.sort_values(['player_name', 'date']).reset_index(drop=True)

    history_df['is_win'] = (history_df['rank'] == 1).astype(int)
    history_df['wins'] = history_df.groupby('player_name')['is_win'].cumsum()
    history_df['is_top10'] = (history_df['rank'] <= 10).astype(int)
    history_df['top_10s'] = history_df.groupby('player_name')['is_top10'].cumsum()
    history_df['cumsum_rank'] = history_df.groupby('player_name')['rank'].cumsum()
    history_df['avg_daily_rank'] = (history_df['cumsum_rank'] / history_df['games_played']).round(1)
    history_df['avg_daily_rank'] = history_df.groupby('player_name')['avg_daily_rank'].ffill()
    history_df['win_rate'] = ((history_df['wins'] / history_df['games_played']) * 100).round(1)
    history_df['top_10s_rate'] = ((history_df['top_10s'] / history_df['games_played']) * 100).round(1)

    def calc_rolling_last7(group):
        played = group[group['rank'].notna()].copy()
        if len(played) == 0:
            return pd.Series(index=group.index, dtype=float)
        played['last_7'] = played['rank'].rolling(window=7, min_periods=1).mean().round(1)
        result = group[['rank']].merge(played[['last_7']], left_index=True, right_index=True, how='left')
        result['last_7'] = result['last_7'].ffill()
        return result['last_7']

    history_df['last_7'] = history_df.groupby('player_name', group_keys=False).apply(calc_rolling_last7, include_groups=False)

    def calc_rolling_prev7(group):
        played = group[group['rank'].notna()].copy()
        if len(played) < 8:
            return pd.Series(index=group.index, dtype=float)
        played['prev_7'] = played['rank'].shift(7).rolling(window=7, min_periods=1).mean()
        result = group[['rank']].merge(played[['prev_7']], left_index=True, right_index=True, how='left')
        result['prev_7'] = result['prev_7'].ffill()
        return result['prev_7']

    history_df['prev_7'] = history_df.groupby('player_name', group_keys=False).apply(calc_rolling_prev7, include_groups=False)

    def calc_trend(row):
        if pd.isna(row['prev_7']) or pd.isna(row['last_7']):
            return "→"
        diff = row['prev_7'] - row['last_7']
        if diff > 1.5:
            return "↑"
        elif diff < -1.5:
            return "↓"
        return "→"

    history_df['trend'] = history_df.apply(calc_trend, axis=1)

    def calc_rolling_consistency(group):
        played = group[group['rank'].notna()].copy()
        if len(played) < 2:
            return pd.Series(index=group.index, dtype=float)
        played['consistency'] = played['rank'].rolling(window=14, min_periods=2).std().round(1)
        result = group[['rank']].merge(played[['consistency']], left_index=True, right_index=True, how='left')
        result['consistency'] = result['consistency'].ffill()
        return result['consistency']

    history_df['consistency'] = history_df.groupby('player_name', group_keys=False).apply(calc_rolling_consistency, include_groups=False)
    history_df['peak_rating'] = history_df.groupby('player_name')['rating'].cummax().round(1)
    history_df = history_df.drop(columns=['is_win', 'is_top10', 'cumsum_rank', 'prev_7'])
    history_df['confidence'] = history_df['games_played'].apply(
        lambda gp: round(calculate_confidence(gp, DYNAMIC_K_ESTABLISHED_GAMES), 2)
    )
    history_df['uncertainty'] = history_df['uncertainty'].round(3)
    history_df = history_df.sort_values(['player_name', 'date']).reset_index(drop=True)
    history_df['active_rank_change'] = history_df.groupby('player_name')['active_rank'].transform(
        lambda x: -x.diff()
    )

    history_df = history_df[[
        'date', 'player_name', 'games_played', 'rank', 'score', 'rating', 'rating_change',
        'active_rank', 'active_rank_change', 'confidence', 'uncertainty',
        'wins', 'top_10s', 'avg_daily_rank', 'win_rate', 'top_10s_rate',
        'last_7', 'trend', 'consistency', 'peak_rating'
    ]]

    return final_df, history_df, all_players_df


def process_dataset(input_pattern, output_prefix, label):
    """Process a single leaderboard dataset and generate Elo ratings."""
    input_files = sorted(OUTPUT_FOLDER.glob(input_pattern))
    if not input_files:
        logger.error(f"No files matching {input_pattern} found in {OUTPUT_FOLDER}")
        return None, None, None

    input_csv = input_files[-1]
    logger.info("=" * 60)
    logger.info(f"Processing {label} data")
    logger.info("=" * 60)
    logger.info(f"Loading data from {input_csv}")
    df = pd.read_csv(input_csv, parse_dates=['date'])
    logger.info(f"Loaded {len(df)} rows, {df['date'].nunique()} unique dates")

    last_date = df['date'].max().strftime('%Y%m%d')
    final_ratings, daily_history, all_players = compute_elo_ratings(df)

    if USE_ACTIVITY_GATING:
        total_players = len(all_players)
        active_players = len(final_ratings)
        inactive_players = total_players - active_players
        logger.info(f"Activity Gating ({label}):")
        logger.info(f"  Total players: {total_players}")
        logger.info(f"  Active players (last {ACTIVITY_WINDOW_DAYS} days): {active_players}")
        logger.info(f"  Inactive players (hidden from rankings): {inactive_players}")

    logger.info(f"Top 20 Active Players by Elo Rating ({label}):")
    logger.info("\n" + final_ratings.head(20).to_string(index=False))
    logger.info(f"Bottom 10 Active Players by Elo Rating ({label}):")
    logger.info("\n" + final_ratings.tail(10).to_string(index=False))

    logger.info(f"Rating Statistics - Active Players ({label}):")
    logger.info(f"  Mean rating: {final_ratings['rating'].mean():.2f}")
    logger.info(f"  Median rating: {final_ratings['rating'].median():.2f}")
    logger.info(f"  Std deviation: {final_ratings['rating'].std():.2f}")
    logger.info(f"  Min rating: {final_ratings['rating'].min():.2f}")
    logger.info(f"  Max rating: {final_ratings['rating'].max():.2f}")

    ratings_csv = OUTPUT_FOLDER / f"{output_prefix}_elo_ratings_{last_date}.csv"
    all_ratings_csv = OUTPUT_FOLDER / f"{output_prefix}_elo_ratings_all_{last_date}.csv"
    history_csv = OUTPUT_FOLDER / f"{output_prefix}_elo_history_{last_date}.csv"

    atomic_write_csv(final_ratings, ratings_csv, index=False)
    atomic_write_csv(all_players, all_ratings_csv, index=False)
    atomic_write_csv(daily_history, history_csv, index=False)

    cleanup_old_files(f"{output_prefix}_elo_ratings_all_*.csv", keep_file=all_ratings_csv, folder=OUTPUT_FOLDER)
    for f in OUTPUT_FOLDER.glob(f"{output_prefix}_elo_ratings_*.csv"):
        if '_all_' not in f.name and f.resolve() != ratings_csv.resolve():
            f.unlink()
    cleanup_old_files(f"{output_prefix}_elo_history_*.csv", keep_file=history_csv, folder=OUTPUT_FOLDER)

    logger.info(f"Exported CSV files ({label}):")
    logger.info(f"  Active ratings: {ratings_csv}")
    logger.info(f"  All ratings (including inactive): {all_ratings_csv}")
    logger.info(f"  Daily history: {history_csv}")

    return final_ratings, daily_history, all_players


def main():
    results = {}

    ea_ratings, ea_history, ea_all = process_dataset(
        EARLY_ACCESS_PATTERN, "early_access", "Early Access"
    )
    if ea_ratings is not None:
        results['early_access'] = (ea_ratings, ea_history, ea_all)

    full_ratings, full_history, full_all = process_dataset(
        FULL_PATTERN, "full", "Full"
    )
    if full_ratings is not None:
        results['full'] = (full_ratings, full_history, full_all)

    # Update rivalries after Elo computation
    from src.elo.rivalries import main as rivalries_main
    logger.info("=" * 60)
    logger.info("Computing rivalries from updated Elo history...")
    logger.info("=" * 60)
    rivalries_results = rivalries_main()
    results['rivalries'] = rivalries_results

    return results


if __name__ == "__main__":
    results = main()
