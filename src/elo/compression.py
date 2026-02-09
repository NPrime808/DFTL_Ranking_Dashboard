"""
Rating Compression Functions

These functions compress raw Elo ratings into bounded ranges to prevent
extreme values and maintain meaningful rating distributions.

Two compression strategies are available:
- Soft (tanh): Simple tanh-based compression toward bounds
- Hybrid: Two-zone compression with logarithmic + tanh for elite ratings
"""

import math
import statistics


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
                         hard_ceiling=3000):
    """
    Hybrid two-zone rating compression combining logarithmic and tanh functions.

    Zone 1 (logarithmic): Makes reaching 2800 difficult but achievable.
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
        hard_ceiling: absolute maximum (asymptotic), default 3000

    Returns:
        dict of player_name -> compressed rating
    """
    if not ratings_dict:
        return ratings_dict

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


def create_rating_scaler(raw_ratings, use_hybrid=True, baseline=1500, target_min=1000,
                         hard_ceiling=3000):
    """
    Create a rating scaler function based on the final raw rating distribution.

    This is used for scaling historical ratings consistently with the final
    compression parameters.

    Args:
        raw_ratings: dict of player_name -> raw rating (final ratings)
        use_hybrid: Whether to use hybrid compression
        baseline: Baseline rating (default 1500)
        target_min: Minimum rating target (default 1000)
        hard_ceiling: Maximum rating ceiling (default 3000)

    Returns:
        A function that takes a single raw rating and returns the scaled rating
    """
    values = list(raw_ratings.values())
    raw_median = statistics.median(values)
    raw_std = statistics.stdev(values) if len(values) > 1 else 1

    if use_hybrid:
        upper_range = hard_ceiling - baseline
        lower_range = baseline - target_min
        tanh_scale_upper = 5.5
        tanh_scale_lower = 2.5
        log_blend = 0.2
        elite_threshold = 8.0
        elite_factor = 0.6

        def scale_single_rating(rating):
            z_score = (rating - raw_median) / raw_std if raw_std > 0 else 0
            if z_score >= 0:
                if z_score > elite_threshold:
                    excess = z_score - elite_threshold
                    compressed_excess = math.log(1 + excess * elite_factor) / elite_factor
                    z_score_adjusted = elite_threshold + compressed_excess
                else:
                    z_score_adjusted = z_score
                log_z = math.log(1 + z_score_adjusted) * 1.8
                z_effective = z_score_adjusted * (1 - log_blend) + log_z * log_blend
                compressed = math.tanh(z_effective / tanh_scale_upper)
                return baseline + compressed * upper_range
            else:
                compressed = math.tanh(-z_score / tanh_scale_lower)
                return baseline - compressed * lower_range
    else:
        target_upper = 2800 - baseline  # Using old target_max
        target_lower = baseline - target_min
        scale_upper = 2.5
        scale_lower = 2.5

        def scale_single_rating(rating):
            z_score = (rating - raw_median) / raw_std if raw_std > 0 else 0
            if z_score >= 0:
                compressed = math.tanh(z_score / scale_upper)
                return baseline + compressed * target_upper
            else:
                compressed = math.tanh(-z_score / scale_lower)
                return baseline - compressed * target_lower

    return scale_single_rating
