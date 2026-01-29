"""
Elo Ranking System for DFTL

This module computes Elo ratings from daily leaderboard data using a pairwise
comparison model. It supports multiple datasets and includes features like:
- Dynamic K-factor based on games played
- Uncertainty amplification for inactive players
- Activity gating to filter inactive players from rankings
- Soft rating compression to prevent extreme values

Usage:
    python -m api.elo_ranking
    OR
    python api/elo_ranking.py
"""

import sys
from pathlib import Path

# Add project root to path for direct script execution
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pandas as pd
from collections import defaultdict

from api.config import (
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
from api.utils import setup_logging, cleanup_old_files, atomic_write_csv

# --- Module Logger ---
logger = setup_logging(__name__)

# Fix Windows console encoding for Unicode characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


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


def scale_ratings_hybrid(ratings_dict, baseline=1500, target_min=900, target_max=2800,
                         soft_target=2800, hard_ceiling=3000):
    """
    Hybrid two-zone rating compression combining logarithmic and tanh functions.

    Zone 1 (logarithmic): Makes reaching soft_target (2800) difficult but achievable.
        Uses a gentle logarithmic blend to create diminishing returns.
    Zone 2 (tanh): Compresses toward hard_ceiling (3000), the theoretical maximum.

    Key insight: by pushing the tanh asymptote to 3000 instead of 2800,
    the "invisible wall" effect occurs around 2850-2900, well above where
    players typically cluster (~2700-2750). Breaking 2800 becomes hard but possible
    for truly exceptional sustained performance.

    Mathematical behavior (with current tuning):
    - z-score ~4 (above average): ~2500-2600 rating
    - z-score ~6 (very good): ~2750-2850 rating (can break 2800)
    - z-score ~8 (excellent): ~2850-2900 rating
    - z-score ~10+ (exceptional): ~2950+ rating
    - Theoretical ceiling: 3000 (asymptotic, effectively unreachable)

    Args:
        ratings_dict: dict of player_name -> raw rating
        baseline: center point (median maps here), default 1500
        target_min: lower bound for compression, default 900
        target_max: ignored, kept for API compatibility with scale_ratings_soft
        soft_target: hard-but-achievable target, default 2800
        hard_ceiling: absolute maximum (asymptotic), default 3000

    Returns:
        dict of player_name -> compressed rating
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

    # Calculate compression ranges
    upper_range = hard_ceiling - baseline  # 1500 (baseline to 3000)
    lower_range = baseline - target_min     # 600 (baseline to 900)

    # Compression parameters (tuned for 2800 to be elite tier)
    # With these settings: only z≈8+ approaches 2800, ceiling at 3000
    tanh_scale_upper = 5.5   # Higher = gentler curve, harder to reach 2800
    tanh_scale_lower = 2.5   # Controls lower compression curve
    log_blend = 0.2          # Logarithmic blend factor (creates diminishing returns)

    # Super-elite compression: extra punishment for extreme outliers
    # Makes 2900 ridiculously hard (~15-20 dominant wins from current #1)
    elite_threshold = 8.0    # z-score threshold where extra compression kicks in
    elite_factor = 0.6       # Gentler compression (lower = less aggressive)

    scaled = {}
    for player, rating in ratings_dict.items():
        z_score = (rating - raw_median) / raw_std

        if z_score >= 0:
            # Super-elite compression: additional log compression for extreme outliers
            # This makes gains above elite_threshold increasingly difficult
            if z_score > elite_threshold:
                excess = z_score - elite_threshold
                # Apply additional log compression to the excess portion
                # Higher elite_factor = more aggressive compression
                compressed_excess = math.log(1 + excess * elite_factor) / elite_factor
                z_score_adjusted = elite_threshold + compressed_excess
            else:
                z_score_adjusted = z_score

            # Hybrid compression: blend linear z with log-compressed z
            # This creates diminishing returns as ratings increase
            # log(1+z) * 1.8 normalizes so that at z=2, log_z ≈ 2
            log_z = math.log(1 + z_score_adjusted) * 1.8
            z_effective = z_score_adjusted * (1 - log_blend) + log_z * log_blend

            # Tanh compression toward hard ceiling (3000)
            compressed = math.tanh(z_effective / tanh_scale_upper)
            scaled[player] = baseline + compressed * upper_range
        else:
            # Below median: standard tanh compression toward target_min
            compressed = math.tanh(-z_score / tanh_scale_lower)
            scaled[player] = baseline - compressed * lower_range

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


def process_daily_result_model(leaderboard_df, ratings, games_played, last_seen, uncertainty, date):
    """
    Process one day's leaderboard using the Daily Result Model.

    Instead of 29 pairwise comparisons, each player gets ONE Elo update
    based on how their actual rank compared to their expected rank.

    Key insight: Ranking 18th when expected 3rd is ONE bad day, not 17 losses.

    Args:
        leaderboard_df: DataFrame with columns [player_name, rank, score] for one day
        ratings: dict of player_name -> current rating
        games_played: dict of player_name -> number of games
        last_seen: dict of player_name -> last date seen
        uncertainty: dict of player_name -> current uncertainty multiplier
        date: current date being processed

    Returns:
        tuple of (rating_changes dict, uncertainty_snapshot dict for this day)
    """
    players = leaderboard_df.sort_values('rank').to_dict('records')
    n = len(players)

    # Initialize new players
    for p in players:
        name = p['player_name']
        if name not in ratings:
            ratings[name] = BASELINE_RATING
            games_played[name] = 0
            uncertainty[name] = UNCERTAINTY_BASE

    # Calculate inactivity-based uncertainty for players appearing today
    player_uncertainty = {}
    for p in players:
        name = p['player_name']
        if name in last_seen:
            days_inactive = (date - last_seen[name]).days
            uncertainty[name] = calculate_uncertainty(days_inactive)
        player_uncertainty[name] = uncertainty[name]

    # Step 1: Calculate expected rank for each player based on current Elo
    # When players have the same Elo, they share the average of their positions
    # This handles the cold-start problem where everyone starts at 1500
    players_with_elo = [(p['player_name'], ratings[p['player_name']]) for p in players]
    players_sorted_by_elo = sorted(players_with_elo, key=lambda x: x[1], reverse=True)

    # Handle ties: players with same Elo share average rank
    expected_rank = {}
    i = 0
    while i < len(players_sorted_by_elo):
        # Find all players with the same Elo
        current_elo = players_sorted_by_elo[i][1]
        j = i
        while j < len(players_sorted_by_elo) and players_sorted_by_elo[j][1] == current_elo:
            j += 1
        # Players from index i to j-1 have the same Elo
        # Their expected rank is the average of positions (i+1) to j
        avg_rank = (i + 1 + j) / 2  # average of (i+1, i+2, ..., j)
        for k in range(i, j):
            expected_rank[players_sorted_by_elo[k][0]] = avg_rank
        i = j

    # Step 2: Get actual ranks
    actual_rank = {p['player_name']: p['rank'] for p in players}

    # Step 3: Calculate single Elo update per player
    rating_changes = {}

    for p in players:
        name = p['player_name']
        expected = expected_rank[name]
        actual = actual_rank[name]

        # Performance: positive = beat expectations, negative = underperformed
        # Normalized to roughly [-1, +1] range
        # Example: expected 3rd, got 18th -> (3 - 18) / 29 = -0.52
        # Example: expected 20th, got 5th -> (20 - 5) / 29 = +0.52
        performance = (expected - actual) / (n - 1)

        # Get K-factor based on experience
        k = get_daily_k(games_played[name])

        # Calculate base rating change
        delta = k * performance

        # Apply uncertainty amplification to losses only
        if delta < 0:
            delta *= player_uncertainty[name]

        rating_changes[name] = delta

    # Apply rating changes
    for name, delta in rating_changes.items():
        ratings[name] += delta

        # Apply floor clamping: never go below the rating floor
        if ratings[name] < RATING_FLOOR:
            ratings[name] = RATING_FLOOR

        games_played[name] += 1
        last_seen[name] = date
        # Decay uncertainty after playing
        uncertainty[name] = decay_uncertainty(player_uncertainty[name])

    return rating_changes, player_uncertainty


def calculate_uncertainty(inactivity_days):
    """
    Calculate uncertainty multiplier based on days of inactivity.
    Uncertainty starts at UNCERTAINTY_BASE and grows linearly with inactivity,
    capped at UNCERTAINTY_MAX.

    Returns:
        float: Uncertainty multiplier (1.0 = no effect, higher = amplified losses)
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
    Uses exponential decay: new = base + (current - base) * (1 - decay_rate)

    Returns:
        float: New uncertainty value after decay
    """
    if not USE_UNCERTAINTY:
        return 1.0

    # Exponential decay toward base
    excess = current_uncertainty - UNCERTAINTY_BASE
    return UNCERTAINTY_BASE + excess * (1 - UNCERTAINTY_DECAY_RATE)


def calculate_floor_factor(loser_rating):
    """
    Calculate the floor factor for winner gains when beating a near-floor player.

    This prevents rating inflation by reducing/eliminating gains when beating
    players who are at or near the rating floor.

    Args:
        loser_rating: The rating of the losing player

    Returns:
        float: Factor from 0.0 (at floor) to 1.0 (at floor + soft_zone or above)
    """
    if loser_rating >= RATING_FLOOR + FLOOR_SOFT_ZONE:
        return 1.0  # Full gains
    elif loser_rating <= RATING_FLOOR:
        return 0.0  # No gains for beating floor players
    else:
        # Linear interpolation in the soft zone
        return (loser_rating - RATING_FLOOR) / FLOOR_SOFT_ZONE


def process_daily_leaderboard(leaderboard_df, ratings, games_played, last_seen, uncertainty, date):
    """
    Process one day's leaderboard and update ratings.

    Args:
        leaderboard_df: DataFrame with columns [player_name, rank, score] for one day
        ratings: dict of player_name -> current rating
        games_played: dict of player_name -> number of games
        last_seen: dict of player_name -> last date seen
        uncertainty: dict of player_name -> current uncertainty multiplier
        date: current date being processed

    Returns:
        tuple of (rating_changes dict, uncertainty_snapshot dict for this day)
    """
    players = leaderboard_df.sort_values('rank').to_dict('records')
    n = len(players)

    # Initialize new players
    for p in players:
        name = p['player_name']
        if name not in ratings:
            ratings[name] = BASELINE_RATING
            games_played[name] = 0
            uncertainty[name] = UNCERTAINTY_BASE

    # Calculate inactivity-based uncertainty for players appearing today
    # (before we update last_seen)
    player_uncertainty = {}
    for p in players:
        name = p['player_name']
        if name in last_seen:
            # Calculate days since last seen
            days_inactive = (date - last_seen[name]).days
            # Update uncertainty based on inactivity
            uncertainty[name] = calculate_uncertainty(days_inactive)
        player_uncertainty[name] = uncertainty[name]

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
            # Winner gains based on their expected score
            delta_i = k_i * weight * (1 - e_i)

            # Apply floor factor: reduce winner gains when beating near-floor players
            # This prevents inflation from floor-clamped losses
            floor_factor = calculate_floor_factor(r_j)
            delta_i *= floor_factor

            # Loser loses based on THEIR expected score (1 - e_i), not the winner's
            # delta_j = k_j * (actual_j - expected_j) = k_j * (0 - (1 - e_i)) = k_j * (e_i - 1)
            delta_j = k_j * weight * (e_i - 1)

            rating_changes[name_i] += delta_i
            rating_changes[name_j] += delta_j

    # Apply logarithmic scaling to compress large daily swings
    # This addresses: "one bad day = one penalty, not 17 penalties"
    # Formula: compressed = sign(x) * scale * log(1 + |x|/scale)
    if USE_LOG_SCALING:
        import math
        for name in rating_changes:
            raw_delta = rating_changes[name]
            if raw_delta != 0:
                sign = 1 if raw_delta > 0 else -1
                compressed = sign * LOG_SCALE_FACTOR * math.log(1 + abs(raw_delta) / LOG_SCALE_FACTOR)
                rating_changes[name] = compressed

    # Apply uncertainty to losses only, then apply rating changes
    for name, delta in rating_changes.items():
        if delta < 0:
            # Amplify losses by uncertainty
            delta *= player_uncertainty[name]
        ratings[name] += delta

        # Apply floor clamping: never go below the rating floor
        if ratings[name] < RATING_FLOOR:
            ratings[name] = RATING_FLOOR

        games_played[name] += 1
        last_seen[name] = date
        # Decay uncertainty after playing
        uncertainty[name] = decay_uncertainty(player_uncertainty[name])

    # Store the rating changes after uncertainty modification
    final_changes = {}
    for name, delta in rating_changes.items():
        if delta < 0:
            final_changes[name] = delta * player_uncertainty[name]
        else:
            final_changes[name] = delta

    return final_changes, player_uncertainty


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
    uncertainty = {}  # Track uncertainty per player

    # Track daily history
    daily_history = []

    # Process each date chronologically
    dates = sorted(df['date'].unique())
    logger.info(f"Processing {len(dates)} days of leaderboard data using '{ELO_MODEL}' model...")

    for date in dates:
        day_df = df[df['date'] == date]

        # Process the day using selected model
        if ELO_MODEL == "daily_result":
            changes, day_uncertainty = process_daily_result_model(
                day_df, ratings, games_played, last_seen, uncertainty, date
            )
        else:  # pairwise (original)
            changes, day_uncertainty = process_daily_leaderboard(
                day_df, ratings, games_played, last_seen, uncertainty, date
            )

        # Determine which players are active on this date (played within last 7 days AND have minimum games)
        active_players_today = set()
        for player, player_last_seen in last_seen.items():
            days_since_seen = (date - player_last_seen).days
            if days_since_seen <= ACTIVITY_WINDOW_DAYS and games_played[player] >= MIN_GAMES_FOR_RANKING:
                active_players_today.add(player)

        # Calculate active_rank for active players only (by rating)
        active_ratings = [(player, ratings[player]) for player in active_players_today]
        active_ratings.sort(key=lambda x: x[1], reverse=True)
        active_rank_map = {player: rank + 1 for rank, (player, _) in enumerate(active_ratings)}

        # Record snapshot of all ratings after this day
        for player, rating in ratings.items():
            # active_rank is None if player is not active on this date
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

    # Log raw rating statistics BEFORE compression
    raw_values = list(ratings.values())
    if raw_values:
        import statistics
        logger.info("Raw Rating Distribution (before compression):")
        logger.info(f"  Min: {min(raw_values):.2f}")
        logger.info(f"  Max: {max(raw_values):.2f}")
        logger.info(f"  Spread: {max(raw_values) - min(raw_values):.2f}")
        logger.info(f"  Mean: {statistics.mean(raw_values):.2f}")
        logger.info(f"  Median: {statistics.median(raw_values):.2f}")
        logger.info(f"  Std Dev: {statistics.stdev(raw_values) if len(raw_values) > 1 else 0:.2f}")

    # Scale final ratings using selected compression method
    if USE_HYBRID_COMPRESSION:
        scaled_ratings = scale_ratings_hybrid(
            ratings, BASELINE_RATING, TARGET_MIN_RATING, TARGET_MAX_RATING,
            soft_target=SOFT_TARGET, hard_ceiling=HARD_CEILING
        )
        compression_method = f"hybrid (log→{SOFT_TARGET}, tanh→{HARD_CEILING})"
    else:
        scaled_ratings = scale_ratings_soft(ratings, BASELINE_RATING, TARGET_MIN_RATING, TARGET_MAX_RATING)
        compression_method = f"tanh (ceiling={TARGET_MAX_RATING})"

    # Log compressed rating statistics for comparison
    scaled_values = list(scaled_ratings.values())
    if scaled_values:
        logger.info(f"Compressed Rating Distribution (after {compression_method} scaling):")
        logger.info(f"  Min: {min(scaled_values):.2f}")
        logger.info(f"  Max: {max(scaled_values):.2f}")
        logger.info(f"  Spread: {max(scaled_values) - min(scaled_values):.2f}")
        logger.info(f"  Mean: {statistics.mean(scaled_values):.2f}")
        logger.info(f"  Median: {statistics.median(scaled_values):.2f}")
        logger.info(f"  Std Dev: {statistics.stdev(scaled_values) if len(scaled_values) > 1 else 0:.2f}")

    # Determine the last date in the dataset for activity gating
    last_date = dates[-1] if dates else None

    # Build final ratings DataFrame
    final_ratings = []
    for player, rating in scaled_ratings.items():
        gp = games_played[player]
        player_last_seen = last_seen[player]

        # Calculate days since last active
        days_inactive = (last_date - player_last_seen).days if last_date else 0

        # Determine if player is active (within activity window AND has minimum games)
        is_active = (days_inactive <= ACTIVITY_WINDOW_DAYS and gp >= MIN_GAMES_FOR_RANKING) if USE_ACTIVITY_GATING else True

        final_ratings.append({
            'player_name': player,
            'rating': round(rating, 2),
            'raw_rating': round(ratings[player], 2),  # Uncompressed rating for comparison
            'games_played': gp,
            'confidence': round(calculate_confidence(gp, DYNAMIC_K_ESTABLISHED_GAMES), 2),
            'last_seen': player_last_seen,
            'days_inactive': days_inactive,
            'uncertainty': round(uncertainty.get(player, UNCERTAINTY_BASE), 3),
            'is_active': is_active
        })

    final_df = pd.DataFrame(final_ratings)

    # Create two DataFrames: active (for display) and all (for reference)
    all_players_df = final_df.copy()
    all_players_df = all_players_df.sort_values('rating', ascending=False).reset_index(drop=True)
    # Inactive players get no active_rank (null), active players get ranked among themselves
    all_players_df['active_rank'] = None
    active_mask = all_players_df['is_active']
    # Rank only active players
    active_sorted = all_players_df[active_mask].sort_values('rating', ascending=False)
    for i, idx in enumerate(active_sorted.index):
        all_players_df.loc[idx, 'active_rank'] = i + 1

    # Filter to active players only for the main rankings
    if USE_ACTIVITY_GATING:
        final_df = final_df[final_df['is_active']].copy()

    final_df = final_df.sort_values('rating', ascending=False).reset_index(drop=True)
    final_df['active_rank'] = final_df.index + 1

    # Reorder columns (active_rank first, include raw_rating for comparison)
    final_df = final_df[['active_rank', 'player_name', 'rating', 'raw_rating', 'games_played', 'confidence', 'last_seen', 'days_inactive', 'uncertainty', 'is_active']]
    all_players_df = all_players_df[['active_rank', 'player_name', 'rating', 'raw_rating', 'games_played', 'confidence', 'last_seen', 'days_inactive', 'uncertainty', 'is_active']]

    # Build daily history DataFrame and scale ratings using same compression method
    history_df = pd.DataFrame(daily_history)

    # Use same scaling parameters from final ratings for consistency
    import statistics
    import math
    raw_values = list(ratings.values())
    raw_median = statistics.median(raw_values)
    raw_std = statistics.stdev(raw_values) if len(raw_values) > 1 else 1

    if USE_HYBRID_COMPRESSION:
        # Hybrid compression: log toward soft target, tanh toward hard ceiling
        upper_range = HARD_CEILING - BASELINE_RATING
        lower_range = BASELINE_RATING - TARGET_MIN_RATING
        tanh_scale_upper = 5.5
        tanh_scale_lower = 2.5
        log_blend = 0.2
        elite_threshold = 8.0
        elite_factor = 0.6

        def scale_single_rating(rating):
            z_score = (rating - raw_median) / raw_std if raw_std > 0 else 0
            if z_score >= 0:
                # Super-elite compression for extreme outliers
                if z_score > elite_threshold:
                    excess = z_score - elite_threshold
                    compressed_excess = math.log(1 + excess * elite_factor) / elite_factor
                    z_score_adjusted = elite_threshold + compressed_excess
                else:
                    z_score_adjusted = z_score
                log_z = math.log(1 + z_score_adjusted) * 1.8
                z_effective = z_score_adjusted * (1 - log_blend) + log_z * log_blend
                compressed = math.tanh(z_effective / tanh_scale_upper)
                return BASELINE_RATING + compressed * upper_range
            else:
                compressed = math.tanh(-z_score / tanh_scale_lower)
                return BASELINE_RATING - compressed * lower_range
    else:
        # Original tanh compression
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

    # --- Pre-compute cumulative and rolling stats for dashboard performance ---
    # Sort by player and date for cumulative calculations
    history_df = history_df.sort_values(['player_name', 'date']).reset_index(drop=True)

    # Cumulative wins (rank == 1)
    history_df['is_win'] = (history_df['rank'] == 1).astype(int)
    history_df['wins'] = history_df.groupby('player_name')['is_win'].cumsum()

    # Cumulative top 10s (rank <= 10)
    history_df['is_top10'] = (history_df['rank'] <= 10).astype(int)
    history_df['top_10s'] = history_df.groupby('player_name')['is_top10'].cumsum()

    # Cumulative average daily rank
    history_df['cumsum_rank'] = history_df.groupby('player_name')['rank'].cumsum()
    history_df['avg_daily_rank'] = (history_df['cumsum_rank'] / history_df['games_played']).round(1)
    # Forward-fill avg_daily_rank for days when player didn't play (so they show last known average)
    history_df['avg_daily_rank'] = history_df.groupby('player_name')['avg_daily_rank'].ffill()

    # Win rate and top 10 rate (percentage)
    history_df['win_rate'] = ((history_df['wins'] / history_df['games_played']) * 100).round(1)
    history_df['top_10s_rate'] = ((history_df['top_10s'] / history_df['games_played']) * 100).round(1)

    # Rolling 7-game average rank (last_7)
    # IMPORTANT: Only compute on rows where player actually played (rank is not NaN)
    # This ensures the rolling window covers actual games, not calendar days
    played_mask = history_df['rank'].notna()

    # Create a temporary df with only played games for proper rolling calculation
    def calc_rolling_last7(group):
        played = group[group['rank'].notna()].copy()
        if len(played) == 0:
            return pd.Series(index=group.index, dtype=float)
        played['last_7'] = played['rank'].rolling(window=7, min_periods=1).mean().round(1)
        # Merge back and forward-fill
        result = group[['rank']].merge(played[['last_7']], left_index=True, right_index=True, how='left')
        result['last_7'] = result['last_7'].ffill()
        return result['last_7']

    history_df['last_7'] = history_df.groupby('player_name', group_keys=False).apply(calc_rolling_last7, include_groups=False)

    # Previous 7-game average (games 8-14 back) for trend calculation
    # Same fix: only count actual games, not calendar days
    def calc_rolling_prev7(group):
        played = group[group['rank'].notna()].copy()
        if len(played) < 8:  # Need at least 8 games for prev_7
            return pd.Series(index=group.index, dtype=float)
        played['prev_7'] = played['rank'].shift(7).rolling(window=7, min_periods=1).mean()
        # Merge back and forward-fill
        result = group[['rank']].merge(played[['prev_7']], left_index=True, right_index=True, how='left')
        result['prev_7'] = result['prev_7'].ffill()
        return result['prev_7']

    history_df['prev_7'] = history_df.groupby('player_name', group_keys=False).apply(calc_rolling_prev7, include_groups=False)

    # Trend: compare last_7 vs prev_7 (lower rank = better, so improving = prev_7 > last_7)
    def calc_trend(row):
        if pd.isna(row['prev_7']) or pd.isna(row['last_7']):
            return "→"  # Not enough data
        diff = row['prev_7'] - row['last_7']  # positive = improving
        if diff > 1.5:
            return "↑"  # Improving
        elif diff < -1.5:
            return "↓"  # Declining
        return "→"  # Stable

    history_df['trend'] = history_df.apply(calc_trend, axis=1)

    # Rolling 14-game consistency (std dev of ranks)
    # Same fix: only count actual games, not calendar days
    def calc_rolling_consistency(group):
        played = group[group['rank'].notna()].copy()
        if len(played) < 2:  # Need at least 2 games for std
            return pd.Series(index=group.index, dtype=float)
        played['consistency'] = played['rank'].rolling(window=14, min_periods=2).std().round(1)
        # Merge back and forward-fill
        result = group[['rank']].merge(played[['consistency']], left_index=True, right_index=True, how='left')
        result['consistency'] = result['consistency'].ffill()
        return result['consistency']

    history_df['consistency'] = history_df.groupby('player_name', group_keys=False).apply(calc_rolling_consistency, include_groups=False)

    # Peak rating (max rating achieved up to this point)
    history_df['peak_rating'] = history_df.groupby('player_name')['rating'].cummax().round(1)

    # Clean up temporary columns
    history_df = history_df.drop(columns=['is_win', 'is_top10', 'cumsum_rank', 'prev_7'])

    # Add confidence column based on games played at that point in time
    history_df['confidence'] = history_df['games_played'].apply(
        lambda gp: round(calculate_confidence(gp, DYNAMIC_K_ESTABLISHED_GAMES), 2)
    )

    # Round uncertainty for display
    history_df['uncertainty'] = history_df['uncertainty'].round(3)

    # Calculate active_rank_change (previous active_rank - current active_rank, positive = improved)
    # Need to handle nulls carefully (inactive periods)
    history_df = history_df.sort_values(['player_name', 'date']).reset_index(drop=True)
    history_df['active_rank_change'] = history_df.groupby('player_name')['active_rank'].transform(
        lambda x: -x.diff()  # negative diff because lower rank is better
    )

    # Reorder columns: include all pre-computed stats for dashboard performance
    history_df = history_df[[
        'date', 'player_name', 'games_played', 'rank', 'score', 'rating', 'rating_change',
        'active_rank', 'active_rank_change', 'confidence', 'uncertainty',
        # Pre-computed cumulative stats
        'wins', 'top_10s', 'avg_daily_rank', 'win_rate', 'top_10s_rate',
        # Pre-computed rolling stats
        'last_7', 'trend', 'consistency', 'peak_rating'
    ]]

    return final_df, history_df, all_players_df


def process_dataset(input_pattern, output_prefix, label):
    """Process a single leaderboard dataset and generate Elo ratings."""
    # Find the most recent file matching the pattern
    input_files = sorted(OUTPUT_FOLDER.glob(input_pattern))
    if not input_files:
        logger.error(f"No files matching {input_pattern} found in {OUTPUT_FOLDER}")
        return None, None, None

    input_csv = input_files[-1]  # Most recent (sorted by date in filename)
    logger.info("=" * 60)
    logger.info(f"Processing {label} data")
    logger.info("=" * 60)
    logger.info(f"Loading data from {input_csv}")
    df = pd.read_csv(input_csv, parse_dates=['date'])
    logger.info(f"Loaded {len(df)} rows, {df['date'].nunique()} unique dates")

    # Get the date from the data for output filenames
    last_date = df['date'].max().strftime('%Y%m%d')

    # Run Elo ranking
    final_ratings, daily_history, all_players = run_elo_ranking(df)

    # Display activity gating info
    if USE_ACTIVITY_GATING:
        total_players = len(all_players)
        active_players = len(final_ratings)
        inactive_players = total_players - active_players
        logger.info(f"Activity Gating ({label}):")
        logger.info(f"  Total players: {total_players}")
        logger.info(f"  Active players (last {ACTIVITY_WINDOW_DAYS} days): {active_players}")
        logger.info(f"  Inactive players (hidden from rankings): {inactive_players}")

    # Display top players
    logger.info(f"Top 20 Active Players by Elo Rating ({label}):")
    logger.info("\n" + final_ratings.head(20).to_string(index=False))

    # Display bottom players
    logger.info(f"Bottom 10 Active Players by Elo Rating ({label}):")
    logger.info("\n" + final_ratings.tail(10).to_string(index=False))

    # Summary stats
    logger.info(f"Rating Statistics - Active Players ({label}):")
    logger.info(f"  Mean rating: {final_ratings['rating'].mean():.2f}")
    logger.info(f"  Median rating: {final_ratings['rating'].median():.2f}")
    logger.info(f"  Std deviation: {final_ratings['rating'].std():.2f}")
    logger.info(f"  Min rating: {final_ratings['rating'].min():.2f}")
    logger.info(f"  Max rating: {final_ratings['rating'].max():.2f}")

    # Export to CSV with date in filename
    ratings_csv = OUTPUT_FOLDER / f"{output_prefix}_elo_ratings_{last_date}.csv"
    all_ratings_csv = OUTPUT_FOLDER / f"{output_prefix}_elo_ratings_all_{last_date}.csv"
    history_csv = OUTPUT_FOLDER / f"{output_prefix}_elo_history_{last_date}.csv"

    atomic_write_csv(final_ratings, ratings_csv, index=False)
    atomic_write_csv(all_players, all_ratings_csv, index=False)
    atomic_write_csv(daily_history, history_csv, index=False)

    # Clean up old output files (keep only the newest)
    # Note: cleanup _all_ files first, then use exclude pattern for regular ratings
    cleanup_old_files(f"{output_prefix}_elo_ratings_all_*.csv", keep_file=all_ratings_csv, folder=OUTPUT_FOLDER)
    # Manually cleanup non-_all_ rating files to avoid matching _all_ files
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

    # Process early access data
    ea_ratings, ea_history, ea_all = process_dataset(
        EARLY_ACCESS_PATTERN, "early_access", "Early Access"
    )
    if ea_ratings is not None:
        results['early_access'] = (ea_ratings, ea_history, ea_all)

    # Process full data
    full_ratings, full_history, full_all = process_dataset(
        FULL_PATTERN, "full", "Full"
    )
    if full_ratings is not None:
        results['full'] = (full_ratings, full_history, full_all)

    return results


if __name__ == "__main__":
    results = main()
