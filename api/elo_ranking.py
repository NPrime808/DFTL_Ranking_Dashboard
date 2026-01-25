import pandas as pd
from pathlib import Path
from collections import defaultdict
import sys

# Fix Windows console encoding for Unicode characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# --- CONFIG ---
BASELINE_RATING = 1500
K_FACTOR = 180  # Elo K-factor (higher = faster rating changes)
# Normalize K by number of opponents (29) to prevent rating explosion
# Each player faces 29 opponents per day, so effective K per comparison is lower
K_NORMALIZED = K_FACTOR / 29
USE_SCORE_GAP_WEIGHTING = True  # Weight updates by score difference
USE_RATIO_BASED_WEIGHTING = True  # Use score ratio (logarithmic) instead of linear gap
RATIO_CAP = 10  # Score ratio at which weight reaches maximum (10x = dominant performance)
USE_DYNAMIC_K = True  # Adjust K based on games played (new players adjust faster)

# Dynamic K thresholds
DYNAMIC_K_NEW_PLAYER_GAMES = 10  # Games until "provisional" period ends
DYNAMIC_K_ESTABLISHED_GAMES = 30  # Games until fully "established"
DYNAMIC_K_NEW_MULTIPLIER = 1.5  # K multiplier for new players
DYNAMIC_K_PROVISIONAL_MULTIPLIER = 1.2  # K multiplier for provisional players

# Target rating bounds (soft targets for asymmetric scaling)
TARGET_MIN_RATING = 900
TARGET_MAX_RATING = 2800

# --- Paths ---
OUTPUT_FOLDER = Path(r"C:\Users\Nicol\DFTL_score_system\output")
# Input file patterns
STEAM_DEMO_PATTERN = "steam_demo_leaderboard_*.csv"
EARLY_ACCESS_PATTERN = "early_access_leaderboard_*.csv"
FULL_PATTERN = "full_leaderboard_*.csv"


def expected_score(rating_a, rating_b):
    """Calculate expected probability of player A beating player B"""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def scale_ratings_soft(ratings_dict, baseline=1500, target_min=900, target_max=2800):
    """
    Scale ratings using soft compression (tanh-like).
    - Median maps to baseline (1500)
    - Proportional gaps preserved near median
    - Extremes gently compressed toward bounds
    - Top player reaches ~90-95% of way to target_max
    """
    if not ratings_dict:
        return ratings_dict

    import statistics
    import math
    values = list(ratings_dict.values())

    if len(values) < 2:
        return {k: baseline for k in ratings_dict}

    raw_median = statistics.median(values)
    raw_std = statistics.stdev(values)

    if raw_std == 0:
        return {k: baseline for k in ratings_dict}

    target_upper = target_max - baseline  # 1300
    target_lower = baseline - target_min  # 600

    # Scale factor: how many std devs to reach ~95% of target bound
    # tanh(2) ≈ 0.96, so 2 std devs reaches ~96% of bound
    scale_upper = 2.5  # std devs to reach ~95% of upper bound
    scale_lower = 2.5  # std devs to reach ~95% of lower bound

    scaled = {}
    for player, rating in ratings_dict.items():
        z_score = (rating - raw_median) / raw_std

        if z_score >= 0:
            # Soft compression toward upper bound using tanh
            compressed = math.tanh(z_score / scale_upper)
            scaled[player] = baseline + compressed * target_upper
        else:
            # Soft compression toward lower bound using tanh
            compressed = math.tanh(-z_score / scale_lower)
            scaled[player] = baseline - compressed * target_lower

    return scaled


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
        import math
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


def process_daily_leaderboard(leaderboard_df, ratings, games_played, last_seen, date):
    """
    Process one day's leaderboard and update ratings.

    Args:
        leaderboard_df: DataFrame with columns [player_name, rank, score] for one day
        ratings: dict of player_name -> current rating
        games_played: dict of player_name -> number of games
        last_seen: dict of player_name -> last date seen
        date: current date being processed

    Returns:
        dict of rating changes for this day (for history tracking)
    """
    players = leaderboard_df.sort_values('rank').to_dict('records')
    n = len(players)

    # Initialize new players
    for p in players:
        name = p['player_name']
        if name not in ratings:
            ratings[name] = BASELINE_RATING
            games_played[name] = 0

    # Calculate max score gap for weighting
    max_gap = players[0]['score'] - players[-1]['score'] if n > 1 else 1

    # Track rating changes for this day
    rating_changes = defaultdict(float)

    # All pairwise comparisons: player i (higher rank) vs player j (lower rank)
    for i in range(n):
        for j in range(i + 1, n):
            player_i = players[i]  # Winner (higher rank = lower number)
            player_j = players[j]  # Loser

            name_i = player_i['player_name']
            name_j = player_j['player_name']

            # Get current ratings
            r_i = ratings[name_i]
            r_j = ratings[name_j]

            # Expected scores
            e_i = expected_score(r_i, r_j)

            # Weight by score gap
            weight = calculate_weight(player_i['score'], player_j['score'], max_gap)

            # Get dynamic K for each player based on experience
            k_i = get_dynamic_k(games_played[name_i])
            k_j = get_dynamic_k(games_played[name_j])

            # Rating updates (player i won, player j lost)
            delta_i = k_i * weight * (1 - e_i)
            delta_j = k_j * weight * (0 - e_i)

            rating_changes[name_i] += delta_i
            rating_changes[name_j] += delta_j

    # Apply rating changes
    for name, delta in rating_changes.items():
        ratings[name] += delta
        games_played[name] += 1
        last_seen[name] = date

    return dict(rating_changes)


def run_elo_ranking(df):
    """
    Run Elo ranking on the full dataset.

    Args:
        df: DataFrame with columns [date, player_name, rank, score]

    Returns:
        Tuple of (final_ratings_df, daily_history_df)
    """
    # Initialize tracking dicts
    ratings = {}
    games_played = defaultdict(int)
    last_seen = {}

    # Track daily history
    daily_history = []

    # Process each date chronologically
    dates = sorted(df['date'].unique())
    print(f"Processing {len(dates)} days of leaderboard data...")

    for date in dates:
        day_df = df[df['date'] == date]

        # Process the day
        changes = process_daily_leaderboard(day_df, ratings, games_played, last_seen, date)

        # Record snapshot of all ratings after this day
        for player, rating in ratings.items():
            daily_history.append({
                'date': date,
                'player_name': player,
                'rating': rating,
                'games_played': games_played[player]
            })

    print(f"Processed {len(dates)} days, {len(ratings)} unique players")

    # Scale final ratings using soft compression
    scaled_ratings = scale_ratings_soft(ratings, BASELINE_RATING, TARGET_MIN_RATING, TARGET_MAX_RATING)

    # Build final ratings DataFrame
    final_ratings = []
    for player, rating in scaled_ratings.items():
        gp = games_played[player]
        final_ratings.append({
            'player_name': player,
            'rating': round(rating, 2),
            'games_played': gp,
            'confidence': round(calculate_confidence(gp, DYNAMIC_K_ESTABLISHED_GAMES), 2),
            'last_seen': last_seen[player]
        })

    final_df = pd.DataFrame(final_ratings)
    final_df = final_df.sort_values('rating', ascending=False).reset_index(drop=True)
    final_df['rank'] = final_df.index + 1

    # Reorder columns
    final_df = final_df[['rank', 'player_name', 'rating', 'games_played', 'confidence', 'last_seen']]

    # Build daily history DataFrame and scale ratings using soft compression
    history_df = pd.DataFrame(daily_history)

    # Use same scaling parameters from final ratings for consistency
    import statistics
    import math
    raw_values = list(ratings.values())
    raw_median = statistics.median(raw_values)
    raw_std = statistics.stdev(raw_values) if len(raw_values) > 1 else 1
    target_upper = TARGET_MAX_RATING - BASELINE_RATING
    target_lower = BASELINE_RATING - TARGET_MIN_RATING
    scale_upper = 2.5
    scale_lower = 2.5

    def scale_single_rating(rating):
        z_score = (rating - raw_median) / raw_std if raw_std > 0 else 0
        if z_score >= 0:
            compressed = math.tanh(z_score / scale_upper)
            return BASELINE_RATING + compressed * target_upper
        else:
            compressed = math.tanh(-z_score / scale_lower)
            return BASELINE_RATING - compressed * target_lower

    history_df['rating'] = history_df['rating'].apply(scale_single_rating).round(2)

    # Sort history by player name (alphabetically) then by date
    history_df = history_df.sort_values(['player_name', 'date']).reset_index(drop=True)

    # Add rating change column (difference from previous day for each player)
    history_df['rating_change'] = history_df.groupby('player_name')['rating'].diff().round(2)
    # First entry for each player: show change from baseline (1500)
    first_game_mask = history_df['rating_change'].isna()
    history_df.loc[first_game_mask, 'rating_change'] = (
        history_df.loc[first_game_mask, 'rating'] - BASELINE_RATING
    ).round(2)

    # Merge with original data to get rank and score for each day played
    history_df = history_df.merge(
        df[['date', 'player_name', 'rank', 'score']],
        on=['date', 'player_name'],
        how='left'
    )

    # Add confidence column based on games played at that point in time
    history_df['confidence'] = history_df['games_played'].apply(
        lambda gp: round(calculate_confidence(gp, DYNAMIC_K_ESTABLISHED_GAMES), 2)
    )

    # Reorder columns: date, player_name, games_played, rank, score, rating, rating_change, confidence
    history_df = history_df[['date', 'player_name', 'games_played', 'rank', 'score', 'rating', 'rating_change', 'confidence']]

    return final_df, history_df


def process_dataset(input_pattern, output_prefix, label):
    """Process a single leaderboard dataset and generate Elo ratings."""
    # Find the most recent file matching the pattern
    input_files = sorted(OUTPUT_FOLDER.glob(input_pattern))
    if not input_files:
        print(f"Error: No files matching {input_pattern} found in {OUTPUT_FOLDER}")
        return None, None

    input_csv = input_files[-1]  # Most recent (sorted by date in filename)
    print(f"\n{'='*60}")
    print(f"Processing {label} data")
    print(f"{'='*60}")
    print(f"Loading data from {input_csv}")
    df = pd.read_csv(input_csv, parse_dates=['date'])
    print(f"Loaded {len(df)} rows, {df['date'].nunique()} unique dates")

    # Get the date from the data for output filenames
    last_date = df['date'].max().strftime('%Y%m%d')

    # Run Elo ranking
    final_ratings, daily_history = run_elo_ranking(df)

    # Display top players
    print(f"\n--- Top 20 Players by Elo Rating ({label}) ---")
    print(final_ratings.head(20).to_string(index=False))

    # Display bottom players
    print(f"\n--- Bottom 10 Players by Elo Rating ({label}) ---")
    print(final_ratings.tail(10).to_string(index=False))

    # Summary stats
    print(f"\n--- Rating Statistics ({label}) ---")
    print(f"Mean rating: {final_ratings['rating'].mean():.2f}")
    print(f"Median rating: {final_ratings['rating'].median():.2f}")
    print(f"Std deviation: {final_ratings['rating'].std():.2f}")
    print(f"Min rating: {final_ratings['rating'].min():.2f}")
    print(f"Max rating: {final_ratings['rating'].max():.2f}")

    # Export to CSV with date in filename
    ratings_csv = OUTPUT_FOLDER / f"{output_prefix}_elo_ratings_{last_date}.csv"
    history_csv = OUTPUT_FOLDER / f"{output_prefix}_elo_history_{last_date}.csv"

    final_ratings.to_csv(ratings_csv, index=False)
    daily_history.to_csv(history_csv, index=False)

    print(f"\n--- Exported CSV files ({label}) ---")
    print(f"Final ratings: {ratings_csv}")
    print(f"Daily history: {history_csv}")

    return final_ratings, daily_history


def main():
    results = {}

    # Process steam demo data
    demo_ratings, demo_history = process_dataset(
        STEAM_DEMO_PATTERN, "steam_demo", "Steam Demo"
    )
    if demo_ratings is not None:
        results['steam_demo'] = (demo_ratings, demo_history)

    # Process early access data
    ea_ratings, ea_history = process_dataset(
        EARLY_ACCESS_PATTERN, "early_access", "Early Access"
    )
    if ea_ratings is not None:
        results['early_access'] = (ea_ratings, ea_history)

    # Process full data
    full_ratings, full_history = process_dataset(
        FULL_PATTERN, "full", "Full"
    )
    if full_ratings is not None:
        results['full'] = (full_ratings, full_history)

    return results


if __name__ == "__main__":
    results = main()
