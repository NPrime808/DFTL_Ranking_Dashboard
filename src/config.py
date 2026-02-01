"""
Central configuration for DFTL Score System.

All shared constants and configuration values should be defined here
to avoid duplication and ensure consistency across modules.
"""

from pathlib import Path

# --- Project Paths ---
PROJECT_ROOT = Path(__file__).parent.parent
DATA_FOLDER = PROJECT_ROOT / "data"
OUTPUT_FOLDER = DATA_FOLDER / "processed"
ASSETS_FOLDER = DATA_FOLDER / "raw"

# --- Dataset Configuration ---
MIN_DATE_EARLY_ACCESS = "2025-11-10"
AUTHOR_NAME = "DFTL_BOT"

# Allowed dataset names (for validation)
ALLOWED_DATASETS = frozenset({"early_access", "full"})

# Input file patterns
EARLY_ACCESS_PATTERN = "early_access_leaderboard_*.csv"
FULL_PATTERN = "full_leaderboard_*.csv"

# --- Elo System Configuration ---
BASELINE_RATING = 1500  # Starting rating for all new players
K_FACTOR = 180  # Elo K-factor (higher = faster rating changes)
K_NORMALIZED = K_FACTOR / 29  # Normalized per pairwise comparison

# Rating bounds
RATING_FLOOR = 1000  # Hard floor: players can never go below this
FLOOR_SOFT_ZONE = 100  # Soft zone for reduced winner gains
TARGET_MIN_RATING = 1000
TARGET_MAX_RATING = 2800

# --- Hybrid Compression Configuration ---
# Set USE_HYBRID_COMPRESSION = True to use the two-zone compression model
# - Logarithmic compression toward SOFT_TARGET (hard but achievable)
# - Tanh compression toward HARD_CEILING (theoretical maximum)
USE_HYBRID_COMPRESSION = True
SOFT_TARGET = 2700   # Hard-but-achievable rating (log compression zone)
HARD_CEILING = 3000  # Theoretical maximum (tanh asymptote)

# --- Dynamic K Configuration ---
USE_DYNAMIC_K = True
DYNAMIC_K_NEW_PLAYER_GAMES = 10
DYNAMIC_K_ESTABLISHED_GAMES = 30
DYNAMIC_K_NEW_MULTIPLIER = 1.5
DYNAMIC_K_PROVISIONAL_MULTIPLIER = 1.2

# --- Uncertainty Configuration ---
USE_UNCERTAINTY = True
UNCERTAINTY_BASE = 1.0
UNCERTAINTY_GROWTH_RATE = 0.05
UNCERTAINTY_MAX = 1.5
UNCERTAINTY_DECAY_RATE = 0.5

# --- Activity Gating Configuration ---
USE_ACTIVITY_GATING = True
ACTIVITY_WINDOW_DAYS = 7
MIN_GAMES_FOR_RANKING = 7

# --- Elo Model Configuration ---
ELO_MODEL = "pairwise"  # "pairwise" or "daily_result"
USE_LOG_SCALING = True
LOG_SCALE_FACTOR = 30
USE_SCORE_GAP_WEIGHTING = True
USE_RATIO_BASED_WEIGHTING = True
RATIO_CAP = 10

# Daily Result Model config
DAILY_K_FACTOR = 32
DAILY_K_NEW_MULTIPLIER = 2.0
DAILY_K_PROVISIONAL_MULTIPLIER = 1.5

# --- Input Validation ---
MAX_INPUT_SIZE = 50_000  # Maximum input text size in bytes (~50KB)
EXPECTED_LEADERBOARD_ROWS = 30  # Expected number of rows per leaderboard
