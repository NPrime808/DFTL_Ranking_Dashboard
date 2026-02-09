"""
Tests for leaderboard parsing functions and regex patterns.
"""

import pytest

from src.utils import DATE_RE, RANK1_RE, RANK_RE, strip_markdown
from src.ingestion.discord_parser import parse_leaderboard_content


class TestStripMarkdown:
    """Tests for strip_markdown utility."""

    def test_removes_bold_asterisks(self):
        assert strip_markdown("**PlayerName**") == "PlayerName"

    def test_removes_single_asterisks(self):
        assert strip_markdown("*PlayerName*") == "PlayerName"

    def test_removes_backticks(self):
        assert strip_markdown("`PlayerName`") == "PlayerName"

    def test_strips_whitespace(self):
        assert strip_markdown("  PlayerName  ") == "PlayerName"

    def test_handles_plain_text(self):
        assert strip_markdown("PlayerName") == "PlayerName"

    def test_handles_mixed_formatting(self):
        assert strip_markdown("**`Player Name`**") == "Player Name"


class TestDateRegex:
    """Tests for DATE_RE pattern."""

    def test_matches_basic_date(self):
        match = DATE_RE.search("date: 25/01/2025")
        assert match is not None
        assert match.group(1) == "25/01/2025"

    def test_matches_with_backticks(self):
        match = DATE_RE.search("`date: 25/01/2025`")
        assert match is not None
        assert match.group(1) == "25/01/2025"

    def test_case_insensitive(self):
        match = DATE_RE.search("DATE: 25/01/2025")
        assert match is not None
        assert match.group(1) == "25/01/2025"

    def test_no_match_invalid_format(self):
        match = DATE_RE.search("2025-01-25")
        assert match is None


class TestRank1Regex:
    """Tests for RANK1_RE pattern (crown emoji rank 1)."""

    def test_matches_bold_player(self):
        match = RANK1_RE.match(":crown_dftl: **PlayerName** - 12345")
        assert match is not None
        assert match.group(1) == "PlayerName"
        assert match.group(2) == "12345"

    def test_matches_plain_player(self):
        match = RANK1_RE.match(":crown_dftl: PlayerName - 9876")
        assert match is not None
        assert match.group(1) == "PlayerName"
        assert match.group(2) == "9876"

    def test_matches_player_with_spaces(self):
        match = RANK1_RE.match(":crown_dftl: **Player Name** - 5000")
        assert match is not None
        assert match.group(1) == "Player Name"

    def test_no_match_without_crown(self):
        match = RANK1_RE.match("#1 **PlayerName** - 12345")
        assert match is None


class TestRankRegex:
    """Tests for RANK_RE pattern (ranks 2-30)."""

    def test_matches_rank_2(self):
        match = RANK_RE.match("#2 **PlayerName** - 11000")
        assert match is not None
        assert match.group(1) == "2"
        assert match.group(2) == "PlayerName"
        assert match.group(3) == "11000"

    def test_matches_rank_30(self):
        match = RANK_RE.match("#30 **LastPlayer** - 500")
        assert match is not None
        assert match.group(1) == "30"
        assert match.group(2) == "LastPlayer"

    def test_matches_plain_player(self):
        match = RANK_RE.match("#5 PlayerName - 8000")
        assert match is not None
        assert match.group(2) == "PlayerName"

    def test_no_match_rank_1(self):
        # Rank 1 uses crown emoji, not #1
        match = RANK_RE.match(":crown_dftl: **PlayerName** - 12345")
        assert match is None


class TestParseLeaderboardContent:
    """Tests for parse_leaderboard_content function."""

    def test_parses_complete_leaderboard(self):
        content = """Top 30 Daily Leaderboard
date: 25/01/2025

:crown_dftl: **Winner** - 15000
#2 **Second** - 14000
#3 **Third** - 13000"""

        rows = parse_leaderboard_content(content)

        assert len(rows) == 3
        assert rows[0] == ("25/01/2025", "Winner", 1, 15000)
        assert rows[1] == ("25/01/2025", "Second", 2, 14000)
        assert rows[2] == ("25/01/2025", "Third", 3, 13000)

    def test_handles_missing_date(self):
        content = """:crown_dftl: **Winner** - 15000
#2 **Second** - 14000"""

        rows = parse_leaderboard_content(content)

        assert len(rows) == 2
        assert rows[0][0] is None  # No date found
        assert rows[0][1] == "Winner"

    def test_ignores_non_leaderboard_lines(self):
        content = """Top 30 Daily Leaderboard
date: 25/01/2025

Some random text here
:crown_dftl: **Winner** - 15000
More random text
#2 **Second** - 14000"""

        rows = parse_leaderboard_content(content)

        assert len(rows) == 2

    def test_empty_content(self):
        rows = parse_leaderboard_content("")
        assert rows == []
