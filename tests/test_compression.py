"""
Tests for rating compression functions.
"""

import pytest

from src.elo.compression import scale_ratings_soft, scale_ratings_hybrid


class TestScaleRatingsSoft:
    """Tests for scale_ratings_soft function."""

    def test_empty_dict(self):
        result = scale_ratings_soft({})
        assert result == {}

    def test_single_player_returns_baseline(self):
        result = scale_ratings_soft({"player1": 1600})
        assert result["player1"] == 1500  # Baseline

    def test_median_player_at_baseline(self):
        ratings = {"low": 1400, "mid": 1500, "high": 1600}
        result = scale_ratings_soft(ratings)
        # Median (1500) should map to baseline (1500)
        assert result["mid"] == 1500

    def test_preserves_relative_order(self):
        ratings = {"a": 1200, "b": 1500, "c": 1800}
        result = scale_ratings_soft(ratings)
        assert result["a"] < result["b"] < result["c"]

    def test_respects_bounds(self):
        # Extreme ratings should still be within bounds
        ratings = {"low": 500, "mid": 1500, "high": 2500}
        result = scale_ratings_soft(ratings, baseline=1500, target_min=900, target_max=2800)

        for rating in result.values():
            assert 900 <= rating <= 2800

    def test_all_same_ratings_returns_baseline(self):
        ratings = {"a": 1500, "b": 1500, "c": 1500}
        result = scale_ratings_soft(ratings)
        for v in result.values():
            assert v == 1500


class TestScaleRatingsHybrid:
    """Tests for scale_ratings_hybrid function."""

    def test_empty_dict(self):
        result = scale_ratings_hybrid({})
        assert result == {}

    def test_single_player_returns_baseline(self):
        result = scale_ratings_hybrid({"player1": 1600})
        assert result["player1"] == 1500  # Baseline

    def test_preserves_relative_order(self):
        ratings = {"a": 1200, "b": 1500, "c": 1800}
        result = scale_ratings_hybrid(ratings)
        assert result["a"] < result["b"] < result["c"]

    def test_respects_hard_ceiling(self):
        # Even extreme ratings should not exceed hard ceiling
        ratings = {"low": 500, "mid": 1500, "high": 3000}
        result = scale_ratings_hybrid(ratings, hard_ceiling=3000)

        for rating in result.values():
            assert rating <= 3000

    def test_respects_floor(self):
        ratings = {"low": 500, "mid": 1500, "high": 2500}
        result = scale_ratings_hybrid(ratings, target_min=900)

        for rating in result.values():
            assert rating >= 900


class TestCompressionProperties:
    """Tests for mathematical properties of compression."""

    def test_soft_compression_uses_z_scores(self):
        """Compression uses z-scores with asymmetric target ranges."""
        # Ratings symmetric around median (1500)
        ratings = {"below": 1300, "at": 1500, "above": 1700}
        result = scale_ratings_soft(ratings)

        # Distance from baseline
        below_distance = result["at"] - result["below"]
        above_distance = result["above"] - result["at"]

        # Ranges are asymmetric: upper=1300 (2800-1500), lower=600 (1500-900)
        # Same z-score magnitude → distances proportional to target ranges
        # Ratio of distances ≈ ratio of ranges (1300/600 ≈ 2.17)
        expected_ratio = (2800 - 1500) / (1500 - 900)  # 1300/600
        actual_ratio = above_distance / below_distance

        assert abs(actual_ratio - expected_ratio) < 0.1
        # Median maps to baseline
        assert result["at"] == 1500

    def test_compression_is_monotonic(self):
        """Higher raw ratings should always produce higher compressed ratings."""
        ratings = {f"p{i}": 1000 + i * 100 for i in range(10)}
        result = scale_ratings_soft(ratings)

        values = [result[f"p{i}"] for i in range(10)]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1]

    def test_hybrid_harder_to_reach_ceiling(self):
        """Hybrid should make it harder to reach high ratings than soft."""
        ratings = {"low": 1000, "mid": 1500, "high": 2200}

        soft = scale_ratings_soft(ratings)
        hybrid = scale_ratings_hybrid(ratings)

        # Hybrid should compress high ratings more than soft
        # (i.e., high rating should be lower in hybrid)
        assert hybrid["high"] <= soft["high"]

    def test_both_methods_produce_valid_output(self):
        """Both methods should produce numeric outputs for valid inputs."""
        ratings = {"a": 1200, "b": 1400, "c": 1600, "d": 1800}

        soft = scale_ratings_soft(ratings)
        hybrid = scale_ratings_hybrid(ratings)

        for method_result in [soft, hybrid]:
            assert len(method_result) == 4
            for v in method_result.values():
                assert isinstance(v, (int, float))
                assert not (v != v)  # Check for NaN
