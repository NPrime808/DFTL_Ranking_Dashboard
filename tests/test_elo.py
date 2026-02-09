"""
Tests for Elo calculation functions.
"""

import pytest

from src.elo.engine import (
    calculate_confidence,
    calculate_floor_factor,
)
from src.config import RATING_FLOOR, FLOOR_SOFT_ZONE


class TestCalculateConfidence:
    """Tests for calculate_confidence function."""

    def test_zero_games(self):
        assert calculate_confidence(0, 30) == 0.0

    def test_half_threshold(self):
        assert calculate_confidence(15, 30) == 0.5

    def test_at_threshold(self):
        assert calculate_confidence(30, 30) == 1.0

    def test_above_threshold_capped(self):
        # Should cap at 1.0
        assert calculate_confidence(50, 30) == 1.0

    def test_different_threshold(self):
        assert calculate_confidence(10, 20) == 0.5


class TestFloorFactor:
    """Tests for calculate_floor_factor function."""

    def test_above_soft_zone(self):
        # Well above floor - full factor
        high_rating = RATING_FLOOR + FLOOR_SOFT_ZONE + 100
        assert calculate_floor_factor(high_rating) == 1.0

    def test_at_floor(self):
        # At floor - zero factor
        assert calculate_floor_factor(RATING_FLOOR) == 0.0

    def test_below_floor(self):
        # Below floor - zero factor
        assert calculate_floor_factor(RATING_FLOOR - 50) == 0.0

    def test_middle_of_soft_zone(self):
        # Middle of soft zone - 50%
        mid_rating = RATING_FLOOR + (FLOOR_SOFT_ZONE / 2)
        result = calculate_floor_factor(mid_rating)
        assert 0.4 <= result <= 0.6  # Allow small float imprecision

    def test_at_soft_zone_boundary(self):
        # At edge of soft zone - full factor
        boundary = RATING_FLOOR + FLOOR_SOFT_ZONE
        assert calculate_floor_factor(boundary) == 1.0


class TestEloMathProperties:
    """Tests for mathematical properties of Elo calculations."""

    def test_reliability_weight_monotonic(self):
        """Reliability weight should increase with more games."""
        weights = [calculate_confidence(g, 30) for g in range(0, 35, 5)]
        for i in range(len(weights) - 1):
            assert weights[i] <= weights[i + 1]

    def test_reliability_weight_bounds(self):
        """Reliability weight should always be between 0 and 1."""
        for games in range(0, 100):
            weight = calculate_confidence(games, 30)
            assert 0.0 <= weight <= 1.0

    def test_floor_factor_monotonic(self):
        """Floor factor should increase with higher rating."""
        ratings = range(RATING_FLOOR - 50, RATING_FLOOR + FLOOR_SOFT_ZONE + 100, 20)
        factors = [calculate_floor_factor(r) for r in ratings]
        for i in range(len(factors) - 1):
            assert factors[i] <= factors[i + 1]

    def test_floor_factor_bounds(self):
        """Floor factor should always be between 0 and 1."""
        for rating in range(500, 2000, 50):
            factor = calculate_floor_factor(rating)
            assert 0.0 <= factor <= 1.0
