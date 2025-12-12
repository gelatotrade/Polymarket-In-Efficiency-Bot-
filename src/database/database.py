"""
Database operations using async SQLAlchemy.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from loguru import logger

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, and_

from .models import Base, PriceRecord, SignalRecord, TradeRecord, PositionRecord, DailyStats


class Database:
    """
    Async database operations for the trading bot.
    """

    def __init__(self, database_url: str):
        """
        Initialize database.

        Args:
            database_url: SQLAlchemy database URL
        """
        self.database_url = database_url
        self.engine = None
        self.async_session = None

    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        logger.info(f"Initializing database: {self.database_url}")

        self.engine = create_async_engine(self.database_url, echo=False)
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized")

    async def close(self) -> None:
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
        logger.info("Database closed")

    # Price Records

    async def save_price(
        self,
        symbol: str,
        price: float,
        source: str,
        timestamp: datetime
    ) -> PriceRecord:
        """Save a price record."""
        async with self.async_session() as session:
            record = PriceRecord(
                symbol=symbol,
                price=price,
                source=source,
                timestamp=timestamp
            )
            session.add(record)
            await session.commit()
            return record

    async def get_recent_prices(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[PriceRecord]:
        """Get recent price records."""
        async with self.async_session() as session:
            result = await session.execute(
                select(PriceRecord)
                .where(PriceRecord.symbol == symbol)
                .order_by(PriceRecord.timestamp.desc())
                .limit(limit)
            )
            return result.scalars().all()

    # Signal Records

    async def save_signal(self, signal_data: Dict) -> SignalRecord:
        """Save a signal record."""
        async with self.async_session() as session:
            record = SignalRecord(
                symbol=signal_data.get("symbol"),
                signal_type=signal_data.get("signal_type"),
                strength=signal_data.get("strength"),
                oracle_price=signal_data.get("oracle_price"),
                market_price=signal_data.get("market_price"),
                price_threshold=signal_data.get("price_threshold"),
                lag_seconds=signal_data.get("lag_seconds"),
                price_diff_pct=signal_data.get("price_diff_pct"),
                confidence=signal_data.get("confidence"),
                reason=signal_data.get("reason"),
                market_id=signal_data.get("market_id"),
                token_id=signal_data.get("token_id"),
                is_actionable=signal_data.get("is_actionable", False),
                timestamp=signal_data.get("timestamp", datetime.utcnow())
            )
            session.add(record)
            await session.commit()
            return record

    async def get_recent_signals(
        self,
        symbol: Optional[str] = None,
        limit: int = 50
    ) -> List[SignalRecord]:
        """Get recent signals."""
        async with self.async_session() as session:
            query = select(SignalRecord).order_by(SignalRecord.timestamp.desc())
            if symbol:
                query = query.where(SignalRecord.symbol == symbol)
            query = query.limit(limit)

            result = await session.execute(query)
            return result.scalars().all()

    # Trade Records

    async def save_trade(self, trade_data: Dict) -> TradeRecord:
        """Save a trade record."""
        async with self.async_session() as session:
            record = TradeRecord(
                trade_id=trade_data.get("trade_id"),
                order_id=trade_data.get("order_id"),
                signal_id=trade_data.get("signal_id"),
                symbol=trade_data.get("symbol"),
                market_id=trade_data.get("market_id"),
                token_id=trade_data.get("token_id"),
                side=trade_data.get("side"),
                order_type=trade_data.get("order_type"),
                requested_price=trade_data.get("requested_price"),
                executed_price=trade_data.get("executed_price"),
                size=trade_data.get("size"),
                fee=trade_data.get("fee", 0),
                status=trade_data.get("status"),
                executed_at=trade_data.get("executed_at", datetime.utcnow())
            )
            session.add(record)
            await session.commit()
            return record

    async def get_trades(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[TradeRecord]:
        """Get trade records."""
        async with self.async_session() as session:
            query = select(TradeRecord).order_by(TradeRecord.executed_at.desc())

            conditions = []
            if symbol:
                conditions.append(TradeRecord.symbol == symbol)
            if start_date:
                conditions.append(TradeRecord.executed_at >= start_date)
            if end_date:
                conditions.append(TradeRecord.executed_at <= end_date)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.limit(limit)
            result = await session.execute(query)
            return result.scalars().all()

    # Position Records

    async def save_position(self, position_data: Dict) -> PositionRecord:
        """Save a position record."""
        async with self.async_session() as session:
            record = PositionRecord(
                position_id=position_data.get("position_id"),
                symbol=position_data.get("symbol"),
                market_id=position_data.get("market_id"),
                token_id=position_data.get("token_id"),
                outcome=position_data.get("outcome"),
                side=position_data.get("side"),
                entry_price=position_data.get("entry_price"),
                size=position_data.get("size"),
                status=position_data.get("status"),
                opened_at=position_data.get("opened_at", datetime.utcnow()),
                metadata=position_data.get("metadata")
            )
            session.add(record)
            await session.commit()
            return record

    async def update_position(
        self,
        position_id: str,
        exit_price: float,
        realized_pnl: float,
        close_reason: str
    ) -> Optional[PositionRecord]:
        """Update a position when closed."""
        async with self.async_session() as session:
            result = await session.execute(
                select(PositionRecord).where(PositionRecord.position_id == position_id)
            )
            record = result.scalar_one_or_none()

            if record:
                record.exit_price = exit_price
                record.realized_pnl = realized_pnl
                record.status = "closed"
                record.closed_at = datetime.utcnow()
                record.close_reason = close_reason
                await session.commit()

            return record

    # Daily Stats

    async def get_daily_stats(self, date: datetime) -> Optional[DailyStats]:
        """Get stats for a specific date."""
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)

        async with self.async_session() as session:
            result = await session.execute(
                select(DailyStats).where(DailyStats.date == start_of_day)
            )
            return result.scalar_one_or_none()

    async def update_daily_stats(self, stats_data: Dict) -> DailyStats:
        """Update or create daily stats."""
        date = stats_data.get("date", datetime.utcnow())
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)

        async with self.async_session() as session:
            result = await session.execute(
                select(DailyStats).where(DailyStats.date == start_of_day)
            )
            record = result.scalar_one_or_none()

            if record:
                for key, value in stats_data.items():
                    if key != "date" and hasattr(record, key):
                        setattr(record, key, value)
            else:
                record = DailyStats(date=start_of_day, **stats_data)
                session.add(record)

            await session.commit()
            return record

    # Analytics

    async def get_performance_summary(
        self,
        days: int = 30
    ) -> Dict:
        """Get performance summary for last N days."""
        start_date = datetime.utcnow() - timedelta(days=days)

        async with self.async_session() as session:
            # Get trades
            trades = await session.execute(
                select(TradeRecord)
                .where(TradeRecord.executed_at >= start_date)
            )
            trade_list = trades.scalars().all()

            # Get closed positions
            positions = await session.execute(
                select(PositionRecord)
                .where(
                    and_(
                        PositionRecord.closed_at >= start_date,
                        PositionRecord.status == "closed"
                    )
                )
            )
            position_list = positions.scalars().all()

            # Calculate stats
            total_pnl = sum(p.realized_pnl or 0 for p in position_list)
            winning = len([p for p in position_list if (p.realized_pnl or 0) > 0])
            losing = len([p for p in position_list if (p.realized_pnl or 0) < 0])

            return {
                "period_days": days,
                "total_trades": len(trade_list),
                "total_positions": len(position_list),
                "winning_positions": winning,
                "losing_positions": losing,
                "win_rate": (winning / len(position_list) * 100) if position_list else 0,
                "total_pnl": total_pnl,
                "avg_pnl_per_trade": total_pnl / len(position_list) if position_list else 0
            }
