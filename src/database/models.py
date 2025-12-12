"""
SQLAlchemy database models.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class PriceRecord(Base):
    """Historical price data."""
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    price = Column(Float, nullable=False)
    source = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PriceRecord(symbol={self.symbol}, price={self.price}, timestamp={self.timestamp})>"


class SignalRecord(Base):
    """Trading signal history."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    signal_type = Column(String(20), nullable=False)
    strength = Column(String(20), nullable=False)
    oracle_price = Column(Float, nullable=False)
    market_price = Column(Float, nullable=False)
    price_threshold = Column(Float)
    lag_seconds = Column(Float, nullable=False)
    price_diff_pct = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    reason = Column(Text)
    market_id = Column(String(100))
    token_id = Column(String(100))
    is_actionable = Column(Boolean, default=False)
    was_executed = Column(Boolean, default=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SignalRecord(symbol={self.symbol}, type={self.signal_type}, timestamp={self.timestamp})>"


class TradeRecord(Base):
    """Executed trade history."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(100), unique=True, nullable=False)
    order_id = Column(String(100))
    signal_id = Column(Integer)
    symbol = Column(String(10), nullable=False, index=True)
    market_id = Column(String(100))
    token_id = Column(String(100), nullable=False)
    side = Column(String(10), nullable=False)
    order_type = Column(String(10), nullable=False)
    requested_price = Column(Float)
    executed_price = Column(Float, nullable=False)
    size = Column(Float, nullable=False)
    fee = Column(Float, default=0)
    status = Column(String(20), nullable=False)
    executed_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TradeRecord(id={self.trade_id}, symbol={self.symbol}, side={self.side})>"


class PositionRecord(Base):
    """Position history."""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(String(100), unique=True, nullable=False)
    symbol = Column(String(10), nullable=False, index=True)
    market_id = Column(String(100))
    token_id = Column(String(100), nullable=False)
    outcome = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    size = Column(Float, nullable=False)
    realized_pnl = Column(Float)
    status = Column(String(20), nullable=False)
    opened_at = Column(DateTime, nullable=False, index=True)
    closed_at = Column(DateTime)
    close_reason = Column(String(50))
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PositionRecord(id={self.position_id}, symbol={self.symbol}, status={self.status})>"


class DailyStats(Base):
    """Daily performance statistics."""
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, unique=True, index=True)
    total_signals = Column(Integer, default=0)
    actionable_signals = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0)
    total_volume = Column(Float, default=0)
    max_drawdown = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        total = self.winning_trades + self.losing_trades
        return (self.winning_trades / total * 100) if total > 0 else 0

    def __repr__(self):
        return f"<DailyStats(date={self.date}, pnl={self.total_pnl})>"
