"""
Data Ingestion

Modules:
- discord_parser: Parse Discord JSON exports
- paste_mode: Daily paste-mode ingestion
"""


def __getattr__(name):
    """Lazy imports to avoid RuntimeWarning when running modules directly."""
    if name == "ingest_leaderboard_text":
        from src.ingestion.paste_mode import ingest_leaderboard_text
        return ingest_leaderboard_text
    if name == "parse_discord_exports":
        from src.ingestion.discord_parser import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
