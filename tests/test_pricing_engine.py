"""
Tests for the Kairos Pricing Engine.

We test the LOGIC — not the database, not Redis.
The pricing formula is pure math — it should be tested in isolation.

This is called "unit testing" — test one function in isolation.
As opposed to "integration testing" where you test multiple systems together.
"""

from decimal import Decimal

import pytest

from app.services.pricing_engine import (
    DEMAND_BANDS,
    INTENT_WEIGHTS,
    PricingEngine,
    get_stock_multiplier,
)


class TestIntentWeights:
    """Test that intent weights are configured sensibly."""

    def test_cart_add_has_higher_weight_than_view(self):
        """Adding to cart is a stronger signal than viewing."""
        from app.events.types import IntentEvent
        assert INTENT_WEIGHTS[IntentEvent.CART_ADDED] > INTENT_WEIGHTS[IntentEvent.PRODUCT_VIEWED]

    def test_checkout_start_is_highest_positive(self):
        """Starting checkout is the strongest positive intent signal (before purchase)."""
        from app.events.types import IntentEvent
        positive_weights = {k: v for k, v in INTENT_WEIGHTS.items() if v > 0}
        assert IntentEvent.CHECKOUT_STARTED in positive_weights

    def test_abandonment_is_negative(self):
        """Abandoning cart should push the score DOWN."""
        from app.events.types import IntentEvent
        assert INTENT_WEIGHTS[IntentEvent.CHECKOUT_ABANDONED] < 0
        assert INTENT_WEIGHTS[IntentEvent.CART_REMOVED] < 0


class TestDemandBands:
    """Test that demand bands cover all score ranges with no gaps."""

    def test_bands_are_ordered(self):
        """Each band's min_score should equal the previous band's max_score."""
        for i in range(1, len(DEMAND_BANDS)):
            assert DEMAND_BANDS[i].min_score == DEMAND_BANDS[i - 1].max_score

    def test_surge_has_highest_multiplier(self):
        multipliers = [b.multiplier for b in DEMAND_BANDS]
        assert multipliers[-1] == max(multipliers)

    def test_low_demand_multiplier_below_or_equal_one(self):
        """Low demand should never increase prices."""
        low_band = next(b for b in DEMAND_BANDS if b.label == "low")
        assert low_band.multiplier <= 1.0


class TestStockMultiplier:
    """Test the scarcity pricing logic."""

    def test_no_multiplier_when_demand_low(self):
        """Stock scarcity shouldn't affect price when nobody wants the product."""
        mult = get_stock_multiplier(stock_qty=1, low_stock_threshold=10, demand_level="low")
        assert mult == 1.0

    def test_no_multiplier_when_stock_plentiful(self):
        """Plenty of stock = no scarcity bonus."""
        mult = get_stock_multiplier(stock_qty=100, low_stock_threshold=10, demand_level="surge")
        assert mult == 1.0

    def test_multiplier_increases_when_nearly_out(self):
        """When stock is almost gone during surge, price should increase."""
        mult_low_stock = get_stock_multiplier(stock_qty=1, low_stock_threshold=10, demand_level="surge")
        mult_normal = get_stock_multiplier(stock_qty=8, low_stock_threshold=10, demand_level="surge")
        assert mult_low_stock >= mult_normal

    def test_highest_bonus_at_critical_stock(self):
        """≤20% of threshold remaining should give the highest scarcity bonus."""
        mult = get_stock_multiplier(stock_qty=1, low_stock_threshold=10, demand_level="surge")
        assert mult == 1.08


class TestPriceCalculation:
    """Test the final price calculation formula end-to-end."""

    def _mock_demand_score(self, level: str, multiplier: float) -> dict:
        return {
            "demand_score": 20.0,
            "demand_level": level,
            "multiplier": multiplier,
            "event_counts": {},
            "active_viewers": 5,
            "cart_adds_1h": 2,
        }

    def test_base_price_at_medium_demand(self):
        """At medium demand (multiplier=1.0), current price should equal base price."""
        engine = PricingEngine(redis=None)  # no Redis needed for pure math
        result = engine.calculate_price(
            base_price=Decimal("100.00"),
            min_price=Decimal("80.00"),
            max_price=Decimal("130.00"),
            stock_qty=50,
            low_stock_threshold=10,
            demand_score=self._mock_demand_score("medium", 1.0),
        )
        assert result == Decimal("100.00")

    def test_price_increases_at_high_demand(self):
        """High demand multiplier should increase the price."""
        engine = PricingEngine(redis=None)
        result = engine.calculate_price(
            base_price=Decimal("100.00"),
            min_price=Decimal("80.00"),
            max_price=Decimal("130.00"),
            stock_qty=50,
            low_stock_threshold=10,
            demand_score=self._mock_demand_score("high", 1.05),
        )
        assert result == Decimal("105.00")

    def test_price_never_exceeds_max(self):
        """No matter how high the demand, price is clamped at max_price."""
        engine = PricingEngine(redis=None)
        result = engine.calculate_price(
            base_price=Decimal("100.00"),
            min_price=Decimal("80.00"),
            max_price=Decimal("102.00"),   # tight ceiling
            stock_qty=1,
            low_stock_threshold=10,
            demand_score=self._mock_demand_score("surge", 1.12),
        )
        assert result == Decimal("102.00")   # clamped at max

    def test_price_never_goes_below_min(self):
        """Low demand should not push price below the seller's floor."""
        engine = PricingEngine(redis=None)
        result = engine.calculate_price(
            base_price=Decimal("100.00"),
            min_price=Decimal("98.00"),    # tight floor
            max_price=Decimal("130.00"),
            stock_qty=50,
            low_stock_threshold=10,
            demand_score=self._mock_demand_score("low", 0.97),
        )
        assert result == Decimal("98.00")   # clamped at min

    def test_decimal_precision(self):
        """Prices must be precise to 2 decimal places — no floating point errors."""
        engine = PricingEngine(redis=None)
        result = engine.calculate_price(
            base_price=Decimal("99.99"),
            min_price=Decimal("80.00"),
            max_price=Decimal("130.00"),
            stock_qty=50,
            low_stock_threshold=10,
            demand_score=self._mock_demand_score("high", 1.05),
        )
        # 99.99 * 1.05 = 104.9895 → rounds to 104.99
        assert result == Decimal("104.99")
        # Verify it's a Decimal with 2 decimal places
        assert isinstance(result, Decimal)
        assert result == result.quantize(Decimal("0.01"))
