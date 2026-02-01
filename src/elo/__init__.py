"""
Elo Rating System

Modules:
- compression: Rating compression functions (tanh, hybrid)
- engine: Core Elo computation and ranking logic
"""


def __getattr__(name):
    """Lazy imports to avoid RuntimeWarning when running modules directly."""
    if name == "scale_ratings_soft":
        from src.elo.compression import scale_ratings_soft
        return scale_ratings_soft
    if name == "scale_ratings_hybrid":
        from src.elo.compression import scale_ratings_hybrid
        return scale_ratings_hybrid
    if name == "compute_elo_ratings":
        from src.elo.engine import compute_elo_ratings
        return compute_elo_ratings
    if name == "run_elo":
        from src.elo.engine import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
