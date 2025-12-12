"""
Data models for price feeds.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum


class PriceSource(Enum):
    """Price data source identifier."""
    CHAINLINK_SCRAPE = "chainlink_scrape"
    CHAINLINK_ONCHAIN = "chainlink_onchain"
    CHAINLINK_API = "chainlink_api"
    POLYMARKET = "polymarket"


@dataclass
class PriceData:
    """
    Represents a single price data point.
    """
    symbol: str  # BTC, ETH, SOL, XRP
    price: float
    timestamp: datetime
    source: PriceSource
    confidence: float = 1.0  # 0-1 confidence score
    volume_24h: Optional[float] = None
    change_24h_pct: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None

    @property
    def age_seconds(self) -> float:
        """Get the age of this price data in seconds."""
        return (datetime.utcnow() - self.timestamp).total_seconds()

    def is_stale(self, max_age_seconds: float = 30.0) -> bool:
        """Check if this price data is stale."""
        return self.age_seconds > max_age_seconds

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value,
            "confidence": self.confidence,
            "volume_24h": self.volume_24h,
            "change_24h_pct": self.change_24h_pct,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "age_seconds": self.age_seconds
        }


@dataclass
class PriceFeed:
    """
    Represents a price feed with historical data.
    """
    symbol: str
    current_price: Optional[PriceData] = None
    price_history: List[PriceData] = field(default_factory=list)
    max_history_size: int = 1000

    def update(self, price_data: PriceData) -> None:
        """Update the feed with new price data."""
        self.current_price = price_data
        self.price_history.append(price_data)

        # Trim history if needed
        if len(self.price_history) > self.max_history_size:
            self.price_history = self.price_history[-self.max_history_size:]

    def get_price_at_time(self, target_time: datetime) -> Optional[PriceData]:
        """Get the closest price data to a specific time."""
        if not self.price_history:
            return None

        closest = min(
            self.price_history,
            key=lambda p: abs((p.timestamp - target_time).total_seconds())
        )
        return closest

    def get_recent_prices(self, count: int = 10) -> List[PriceData]:
        """Get the most recent price data points."""
        return self.price_history[-count:] if self.price_history else []

    def get_price_change(self, seconds_ago: float = 60.0) -> Optional[float]:
        """Calculate price change over a time period."""
        if not self.current_price or len(self.price_history) < 2:
            return None

        target_time = datetime.utcnow()
        from datetime import timedelta
        past_time = target_time - timedelta(seconds=seconds_ago)

        past_price = self.get_price_at_time(past_time)
        if not past_price:
            return None

        return ((self.current_price.price - past_price.price) / past_price.price) * 100

    def get_volatility(self, window_size: int = 60) -> Optional[float]:
        """Calculate volatility over recent price history."""
        recent = self.get_recent_prices(window_size)
        if len(recent) < 2:
            return None

        prices = [p.price for p in recent]
        import statistics
        return statistics.stdev(prices) / statistics.mean(prices) * 100


@dataclass
class PriceLag:
    """
    Represents the detected lag between oracle and Polymarket prices.
    """
    symbol: str
    oracle_price: float
    polymarket_price: float
    oracle_timestamp: datetime
    polymarket_timestamp: datetime
    lag_seconds: float
    price_difference_pct: float

    @property
    def is_profitable(self) -> bool:
        """Check if the lag presents a profitable opportunity."""
        # Consider profitable if lag is significant and price diff is substantial
        return self.lag_seconds >= 10.0 and abs(self.price_difference_pct) >= 0.3

    @property
    def direction(self) -> str:
        """Get the direction of price movement."""
        if self.price_difference_pct > 0:
            return "UP"
        elif self.price_difference_pct < 0:
            return "DOWN"
        return "NEUTRAL"

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "oracle_price": self.oracle_price,
            "polymarket_price": self.polymarket_price,
            "oracle_timestamp": self.oracle_timestamp.isoformat(),
            "polymarket_timestamp": self.polymarket_timestamp.isoformat(),
            "lag_seconds": self.lag_seconds,
            "price_difference_pct": self.price_difference_pct,
            "direction": self.direction,
            "is_profitable": self.is_profitable
        }
