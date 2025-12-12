"""
Risk Manager - Controls trading risk and position limits.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger

from .models import TradeAction, Signal


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_position_size_usd: float = 100.0
    max_daily_loss_usd: float = 50.0
    max_concurrent_positions: int = 3
    max_slippage_pct: float = 0.5
    stop_loss_pct: float = 5.0
    min_liquidity_usd: float = 500.0
    max_exposure_pct: float = 50.0  # Max % of balance in positions
    cooldown_after_loss_seconds: float = 60.0


@dataclass
class RiskState:
    """Current risk state."""
    daily_pnl: float = 0.0
    daily_trades: int = 0
    daily_losses: int = 0
    current_exposure_usd: float = 0.0
    last_loss_time: Optional[datetime] = None
    in_cooldown: bool = False
    positions_count: int = 0
    day_start: datetime = field(default_factory=lambda: datetime.utcnow().replace(hour=0, minute=0, second=0))

    def reset_daily(self) -> None:
        """Reset daily statistics."""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.daily_losses = 0
        self.day_start = datetime.utcnow().replace(hour=0, minute=0, second=0)


class RiskManager:
    """
    Manages trading risk including position sizing, loss limits, and exposure.

    Features:
    - Maximum daily loss limit
    - Position size limits
    - Exposure management
    - Cooldown periods after losses
    - Liquidity checks
    """

    def __init__(self, limits: Optional[RiskLimits] = None):
        """
        Initialize risk manager.

        Args:
            limits: Risk limit configuration
        """
        self.limits = limits or RiskLimits()
        self.state = RiskState()
        self._trade_history: List[Dict] = []

    def check_daily_reset(self) -> None:
        """Check if daily stats should be reset."""
        now = datetime.utcnow()
        if now.date() > self.state.day_start.date():
            logger.info("Resetting daily risk statistics")
            self.state.reset_daily()

    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is currently allowed.

        Returns:
            Tuple of (can_trade, reason)
        """
        self.check_daily_reset()

        # Check daily loss limit
        if abs(self.state.daily_pnl) >= self.limits.max_daily_loss_usd and self.state.daily_pnl < 0:
            return False, f"Daily loss limit reached (${self.state.daily_pnl:.2f})"

        # Check concurrent positions
        if self.state.positions_count >= self.limits.max_concurrent_positions:
            return False, f"Max concurrent positions reached ({self.state.positions_count})"

        # Check cooldown
        if self.state.in_cooldown:
            if self.state.last_loss_time:
                cooldown_end = self.state.last_loss_time + timedelta(seconds=self.limits.cooldown_after_loss_seconds)
                if datetime.utcnow() < cooldown_end:
                    remaining = (cooldown_end - datetime.utcnow()).seconds
                    return False, f"In cooldown after loss ({remaining}s remaining)"
                else:
                    self.state.in_cooldown = False

        return True, "OK"

    def validate_trade(self, action: TradeAction) -> tuple[bool, str]:
        """
        Validate a trade action against risk limits.

        Args:
            action: Trade action to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check if trading allowed
        can_trade, reason = self.can_trade()
        if not can_trade:
            return False, reason

        # Check position size
        if action.size > self.limits.max_position_size_usd:
            return False, f"Position size ${action.size:.2f} exceeds limit ${self.limits.max_position_size_usd:.2f}"

        # Check slippage
        if action.max_slippage > self.limits.max_slippage_pct / 100:
            return False, f"Slippage {action.max_slippage*100:.1f}% exceeds limit {self.limits.max_slippage_pct:.1f}%"

        # Check signal confidence
        if action.signal.confidence < 0.5:
            return False, f"Signal confidence {action.signal.confidence:.2f} too low"

        return True, "OK"

    def adjust_position_size(
        self,
        requested_size: float,
        confidence: float,
        market_liquidity: float
    ) -> float:
        """
        Adjust position size based on risk factors.

        Args:
            requested_size: Requested position size
            confidence: Signal confidence
            market_liquidity: Market liquidity in USD

        Returns:
            Adjusted position size
        """
        size = requested_size

        # Scale by confidence
        size *= confidence

        # Don't exceed max position size
        size = min(size, self.limits.max_position_size_usd)

        # Don't exceed 10% of market liquidity
        max_from_liquidity = market_liquidity * 0.10
        size = min(size, max_from_liquidity)

        # Reduce size if we have losses today
        if self.state.daily_losses > 0:
            reduction_factor = max(0.5, 1.0 - (self.state.daily_losses * 0.1))
            size *= reduction_factor

        # Minimum size threshold
        min_size = 5.0
        if size < min_size:
            return 0.0  # Don't trade if size too small

        return round(size, 2)

    def on_trade_opened(self, position_size: float) -> None:
        """Record a new position opened."""
        self.state.positions_count += 1
        self.state.current_exposure_usd += position_size
        self.state.daily_trades += 1

    def on_trade_closed(self, pnl: float, position_size: float) -> None:
        """
        Record a position closed.

        Args:
            pnl: Profit/loss in USD
            position_size: Position size that was closed
        """
        self.state.positions_count = max(0, self.state.positions_count - 1)
        self.state.current_exposure_usd = max(0, self.state.current_exposure_usd - position_size)
        self.state.daily_pnl += pnl

        if pnl < 0:
            self.state.daily_losses += 1
            self.state.last_loss_time = datetime.utcnow()
            self.state.in_cooldown = True
            logger.warning(f"Loss recorded: ${pnl:.2f}, entering cooldown")

        self._trade_history.append({
            "pnl": pnl,
            "position_size": position_size,
            "timestamp": datetime.utcnow().isoformat(),
            "daily_pnl": self.state.daily_pnl,
            "daily_trades": self.state.daily_trades
        })

    def get_status(self) -> Dict:
        """Get current risk status."""
        can_trade, reason = self.can_trade()

        return {
            "can_trade": can_trade,
            "reason": reason,
            "daily_pnl": self.state.daily_pnl,
            "daily_trades": self.state.daily_trades,
            "daily_losses": self.state.daily_losses,
            "positions_count": self.state.positions_count,
            "current_exposure": self.state.current_exposure_usd,
            "in_cooldown": self.state.in_cooldown,
            "limits": {
                "max_position_size": self.limits.max_position_size_usd,
                "max_daily_loss": self.limits.max_daily_loss_usd,
                "max_positions": self.limits.max_concurrent_positions
            }
        }

    def get_trade_history(self, limit: int = 20) -> List[Dict]:
        """Get recent trade history."""
        return self._trade_history[-limit:]
