"""
Position Manager - Tracks and manages open positions.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

from ..polymarket.models import Position, PositionStatus, OrderSide
from .models import TradeAction


class PositionManager:
    """
    Manages trading positions including:
    - Position tracking
    - PnL calculation
    - Stop loss / take profit monitoring
    - Position history
    """

    def __init__(self):
        """Initialize position manager."""
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.max_closed_history = 500

        # Aggregate statistics
        self.total_realized_pnl: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0

    def open_position(
        self,
        action: TradeAction,
        execution_price: float
    ) -> Position:
        """
        Open a new position.

        Args:
            action: Trade action that was executed
            execution_price: Actual execution price

        Returns:
            New Position object
        """
        position = Position(
            position_id=str(uuid.uuid4()),
            market_id=action.signal.market_id or "",
            token_id=action.token_id,
            outcome="Yes" if action.signal.signal_type.value == "buy_yes" else "No",
            side=OrderSide.BUY if action.side == "BUY" else OrderSide.SELL,
            entry_price=execution_price,
            size=action.size,
            current_price=execution_price,
            status=PositionStatus.OPEN,
            opened_at=datetime.utcnow()
        )

        self.open_positions[position.position_id] = position
        self.total_trades += 1

        logger.info(f"Opened position {position.position_id}: {position.outcome} @ {execution_price} x {action.size}")

        return position

    def update_position_price(self, position_id: str, current_price: float) -> Optional[Position]:
        """
        Update position with current market price.

        Args:
            position_id: Position ID
            current_price: Current market price

        Returns:
            Updated position or None
        """
        position = self.open_positions.get(position_id)
        if not position:
            return None

        position.current_price = current_price
        return position

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "manual"
    ) -> Optional[tuple[Position, float]]:
        """
        Close a position.

        Args:
            position_id: Position ID
            exit_price: Exit price
            reason: Reason for closing

        Returns:
            Tuple of (closed position, realized PnL) or None
        """
        position = self.open_positions.get(position_id)
        if not position:
            logger.warning(f"Position {position_id} not found")
            return None

        # Calculate PnL
        position.current_price = exit_price
        pnl = position.unrealized_pnl
        position.realized_pnl = pnl

        # Update status
        position.status = PositionStatus.CLOSED
        position.closed_at = datetime.utcnow()

        # Move to closed positions
        del self.open_positions[position_id]
        self.closed_positions.append(position)

        # Trim history
        if len(self.closed_positions) > self.max_closed_history:
            self.closed_positions = self.closed_positions[-self.max_closed_history:]

        # Update statistics
        self.total_realized_pnl += pnl
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        logger.info(f"Closed position {position_id}: PnL ${pnl:.2f} ({reason})")

        return position, pnl

    def check_stop_losses(self, price_updates: Dict[str, float]) -> List[str]:
        """
        Check if any positions hit stop loss.

        Args:
            price_updates: Dict mapping token_id to current price

        Returns:
            List of position IDs that should be closed
        """
        to_close = []

        for position_id, position in self.open_positions.items():
            current_price = price_updates.get(position.token_id)
            if not current_price:
                continue

            position.current_price = current_price

            # Check if unrealized loss exceeds stop loss threshold (5%)
            if position.unrealized_pnl_pct <= -5.0:
                to_close.append(position_id)
                logger.warning(f"Position {position_id} hit stop loss: {position.unrealized_pnl_pct:.2f}%")

        return to_close

    def check_take_profits(self, price_updates: Dict[str, float]) -> List[str]:
        """
        Check if any positions hit take profit.

        Args:
            price_updates: Dict mapping token_id to current price

        Returns:
            List of position IDs that should be closed
        """
        to_close = []

        for position_id, position in self.open_positions.items():
            current_price = price_updates.get(position.token_id)
            if not current_price:
                continue

            position.current_price = current_price

            # Check if unrealized profit exceeds take profit threshold (10%)
            if position.unrealized_pnl_pct >= 10.0:
                to_close.append(position_id)
                logger.info(f"Position {position_id} hit take profit: {position.unrealized_pnl_pct:.2f}%")

        return to_close

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a position by ID."""
        return self.open_positions.get(position_id)

    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self.open_positions.values())

    def get_positions_for_symbol(self, symbol: str) -> List[Position]:
        """Get positions for a specific crypto symbol."""
        # This would need market_id to symbol mapping
        return list(self.open_positions.values())

    def get_total_exposure(self) -> float:
        """Get total USD value of open positions."""
        return sum(p.market_value for p in self.open_positions.values())

    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized PnL."""
        return sum(p.unrealized_pnl for p in self.open_positions.values())

    def get_statistics(self) -> Dict:
        """Get position statistics."""
        open_positions = self.get_open_positions()

        return {
            "open_positions_count": len(open_positions),
            "total_exposure_usd": self.get_total_exposure(),
            "unrealized_pnl": self.get_total_unrealized_pnl(),
            "realized_pnl": self.total_realized_pnl,
            "total_pnl": self.total_realized_pnl + self.get_total_unrealized_pnl(),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            "positions": [p.to_dict() for p in open_positions]
        }

    def get_closed_positions(self, limit: int = 20) -> List[Dict]:
        """Get recent closed positions."""
        return [p.to_dict() for p in self.closed_positions[-limit:]]
