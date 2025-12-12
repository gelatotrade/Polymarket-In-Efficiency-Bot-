"""
Data models for Polymarket integration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum


class MarketType(Enum):
    """Type of prediction market."""
    CRYPTO_PRICE_15M = "crypto_15m"
    CRYPTO_PRICE_DAILY = "crypto_daily"
    CRYPTO_PRICE_WEEKLY = "crypto_weekly"
    OTHER = "other"


class OrderSide(Enum):
    """Order side."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type."""
    GTC = "GTC"  # Good Till Cancelled
    GTD = "GTD"  # Good Till Date
    FOK = "FOK"  # Fill Or Kill


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PositionStatus(Enum):
    """Position status."""
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class OrderBookLevel:
    """Single level in the order book."""
    price: float
    size: float

    @property
    def value(self) -> float:
        """Total value at this level."""
        return self.price * self.size


@dataclass
class OrderBook:
    """
    Order book for a market outcome.
    """
    token_id: str
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        """Get the best bid."""
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        """Get the best ask."""
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        """Get the mid price."""
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Get the bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None

    @property
    def spread_pct(self) -> Optional[float]:
        """Get the spread as percentage of mid price."""
        if self.mid_price and self.spread:
            return (self.spread / self.mid_price) * 100
        return None

    def get_total_bid_liquidity(self, depth: int = None) -> float:
        """Get total bid liquidity up to depth levels."""
        bids = self.bids[:depth] if depth else self.bids
        return sum(level.value for level in bids)

    def get_total_ask_liquidity(self, depth: int = None) -> float:
        """Get total ask liquidity up to depth levels."""
        asks = self.asks[:depth] if depth else self.asks
        return sum(level.value for level in asks)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "token_id": self.token_id,
            "best_bid": self.best_bid.price if self.best_bid else None,
            "best_ask": self.best_ask.price if self.best_ask else None,
            "mid_price": self.mid_price,
            "spread": self.spread,
            "spread_pct": self.spread_pct,
            "bid_liquidity": self.get_total_bid_liquidity(5),
            "ask_liquidity": self.get_total_ask_liquidity(5),
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class MarketOutcome:
    """
    Single outcome in a market (e.g., "Yes" or "No").
    """
    outcome_id: str
    token_id: str
    outcome: str  # "Yes", "No", or price level like "$100,000"
    price: float  # Current price (0-1)
    order_book: Optional[OrderBook] = None

    @property
    def implied_probability(self) -> float:
        """Get implied probability from price."""
        return self.price

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "outcome_id": self.outcome_id,
            "token_id": self.token_id,
            "outcome": self.outcome,
            "price": self.price,
            "implied_probability": self.implied_probability,
            "order_book": self.order_book.to_dict() if self.order_book else None
        }


@dataclass
class Market:
    """
    Polymarket prediction market.
    """
    market_id: str
    condition_id: str
    question: str
    description: str
    market_type: MarketType
    crypto_symbol: Optional[str]  # BTC, ETH, SOL, XRP
    outcomes: List[MarketOutcome] = field(default_factory=list)
    volume: float = 0.0
    liquidity: float = 0.0
    end_date: Optional[datetime] = None
    resolution_source: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # For 15-minute markets
    price_threshold: Optional[float] = None  # e.g., 100000 for "BTC above $100,000"
    threshold_type: Optional[str] = None  # "above", "below", "between"

    def get_yes_outcome(self) -> Optional[MarketOutcome]:
        """Get the 'Yes' outcome."""
        for outcome in self.outcomes:
            if outcome.outcome.lower() == "yes":
                return outcome
        return None

    def get_no_outcome(self) -> Optional[MarketOutcome]:
        """Get the 'No' outcome."""
        for outcome in self.outcomes:
            if outcome.outcome.lower() == "no":
                return outcome
        return None

    def get_implied_price(self) -> Optional[float]:
        """
        Get the implied price based on market odds.

        For a market like "BTC above $100,000?", if Yes is trading at 60%,
        the implied price is approximately $100,000 (adjusted by probability).
        """
        if not self.price_threshold:
            return None

        yes_outcome = self.get_yes_outcome()
        if not yes_outcome:
            return None

        # Simple interpolation based on probability
        # This is a simplified model
        prob = yes_outcome.price

        if self.threshold_type == "above":
            # Higher probability of "above" means price is likely higher
            # Estimate based on threshold ± some range
            range_estimate = self.price_threshold * 0.05  # 5% range
            return self.price_threshold + (prob - 0.5) * 2 * range_estimate

        return self.price_threshold

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "question": self.question,
            "market_type": self.market_type.value,
            "crypto_symbol": self.crypto_symbol,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "volume": self.volume,
            "liquidity": self.liquidity,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active,
            "price_threshold": self.price_threshold,
            "implied_price": self.get_implied_price()
        }


@dataclass
class Order:
    """
    Trading order.
    """
    order_id: str
    market_id: str
    token_id: str
    side: OrderSide
    order_type: OrderType
    price: float
    size: float
    filled_size: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    @property
    def remaining_size(self) -> float:
        """Get remaining unfilled size."""
        return self.size - self.filled_size

    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.filled_size >= self.size

    @property
    def fill_percentage(self) -> float:
        """Get fill percentage."""
        return (self.filled_size / self.size * 100) if self.size > 0 else 0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "price": self.price,
            "size": self.size,
            "filled_size": self.filled_size,
            "remaining_size": self.remaining_size,
            "status": self.status.value,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Position:
    """
    Open position in a market.
    """
    position_id: str
    market_id: str
    token_id: str
    outcome: str
    side: OrderSide
    entry_price: float
    size: float
    current_price: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    realized_pnl: float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized PnL."""
        if self.status == PositionStatus.CLOSED:
            return 0.0

        if self.side == OrderSide.BUY:
            return (self.current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - self.current_price) * self.size

    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized PnL percentage."""
        cost = self.entry_price * self.size
        if cost == 0:
            return 0.0
        return (self.unrealized_pnl / cost) * 100

    @property
    def market_value(self) -> float:
        """Get current market value."""
        return self.current_price * self.size

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "position_id": self.position_id,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "outcome": self.outcome,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "size": self.size,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "market_value": self.market_value,
            "status": self.status.value,
            "opened_at": self.opened_at.isoformat()
        }


@dataclass
class Trade:
    """
    Executed trade record.
    """
    trade_id: str
    order_id: str
    market_id: str
    token_id: str
    side: OrderSide
    price: float
    size: float
    fee: float = 0.0
    executed_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_cost(self) -> float:
        """Get total cost including fees."""
        return self.price * self.size + self.fee

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "trade_id": self.trade_id,
            "order_id": self.order_id,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "side": self.side.value,
            "price": self.price,
            "size": self.size,
            "fee": self.fee,
            "total_cost": self.total_cost,
            "executed_at": self.executed_at.isoformat()
        }
