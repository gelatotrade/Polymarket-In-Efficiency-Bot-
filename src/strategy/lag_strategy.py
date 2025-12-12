"""
Lag Trading Strategy - Exploits the delay between oracle prices and Polymarket order book updates.

The strategy works as follows:
1. Monitor real-time prices from Chainlink oracle (BTC, ETH, SOL, XRP)
2. Monitor Polymarket 15-minute crypto prediction markets
3. Detect when oracle price moves significantly but market hasn't adjusted
4. Trade the market in the direction of the oracle price movement
5. Exit when market catches up to oracle price
"""

import uuid
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Callable
from loguru import logger

from .models import (
    Signal, SignalType, SignalStrength, TradeAction, StrategyState, LagOpportunity
)
from ..price_feeds.models import PriceData, PriceLag
from ..polymarket.models import Market, OrderSide, OrderType


class LagTradingStrategy:
    """
    Main trading strategy that exploits the lag between Chainlink oracle
    prices and Polymarket order book reactions.

    Key Parameters:
    - lag_threshold: Minimum lag in seconds to consider (default: 10s)
    - price_diff_threshold: Minimum price difference % to trade (default: 0.3%)
    - max_position_size: Maximum position size in USD
    - confidence_threshold: Minimum confidence to execute (default: 0.6)
    """

    def __init__(
        self,
        lag_threshold: float = 10.0,
        price_diff_threshold: float = 0.3,
        max_position_size: float = 100.0,
        confidence_threshold: float = 0.6,
        max_concurrent_positions: int = 3
    ):
        """
        Initialize the strategy.

        Args:
            lag_threshold: Minimum lag in seconds to trade
            price_diff_threshold: Minimum price difference percentage
            max_position_size: Maximum position size in USD
            confidence_threshold: Minimum signal confidence
            max_concurrent_positions: Maximum concurrent open positions
        """
        self.lag_threshold = lag_threshold
        self.price_diff_threshold = price_diff_threshold
        self.max_position_size = max_position_size
        self.confidence_threshold = confidence_threshold
        self.max_concurrent_positions = max_concurrent_positions

        # State
        self.state = StrategyState()
        self.active_opportunities: Dict[str, LagOpportunity] = {}
        self.pending_actions: List[TradeAction] = []

        # Signal history
        self.signal_history: List[Signal] = []
        self.max_signal_history = 1000

        # Callbacks
        self._signal_callbacks: List[Callable] = []
        self._action_callbacks: List[Callable] = []

    def add_signal_callback(self, callback: Callable) -> None:
        """Add callback for new signals."""
        self._signal_callbacks.append(callback)

    def add_action_callback(self, callback: Callable) -> None:
        """Add callback for trade actions."""
        self._action_callbacks.append(callback)

    async def _notify_signal(self, signal: Signal) -> None:
        """Notify callbacks of new signal."""
        for callback in self._signal_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                logger.error(f"Signal callback error: {e}")

    async def _notify_action(self, action: TradeAction) -> None:
        """Notify callbacks of trade action."""
        for callback in self._action_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(action)
                else:
                    callback(action)
            except Exception as e:
                logger.error(f"Action callback error: {e}")

    def analyze_lag(
        self,
        symbol: str,
        oracle_price: PriceData,
        market: Market
    ) -> Optional[Signal]:
        """
        Analyze lag between oracle and market prices to generate trading signal.

        Args:
            symbol: Cryptocurrency symbol
            oracle_price: Current oracle price data
            market: Polymarket market

        Returns:
            Signal if opportunity detected, None otherwise
        """
        if not oracle_price or not market:
            return None

        # Get market implied price
        market_implied = market.get_implied_price()
        if not market_implied:
            return None

        # Get market threshold price
        threshold_price = market.price_threshold
        if not threshold_price:
            return None

        # Calculate price difference
        price_diff_pct = ((oracle_price.price - market_implied) / market_implied) * 100

        # Get Yes outcome for trading
        yes_outcome = market.get_yes_outcome()
        if not yes_outcome:
            return None

        # Calculate implied lag (time since market last updated)
        if yes_outcome.order_book:
            market_time = yes_outcome.order_book.timestamp
            lag_seconds = (oracle_price.timestamp - market_time).total_seconds()
        else:
            lag_seconds = 15.0  # Assume some lag if no order book

        # Determine signal based on oracle vs threshold
        oracle_above_threshold = oracle_price.price > threshold_price

        # Current market probability (Yes price)
        market_prob = yes_outcome.price

        # Calculate expected probability based on oracle price
        # Simple model: if oracle is X% above threshold, probability should be higher
        price_distance_pct = ((oracle_price.price - threshold_price) / threshold_price) * 100

        # Estimate expected probability
        # If price is 1% above threshold, expect ~55-65% Yes probability
        # If price is 2% above, expect ~65-75% Yes probability
        expected_prob = 0.5 + (price_distance_pct * 0.1)  # Simple linear model
        expected_prob = max(0.1, min(0.9, expected_prob))  # Clamp

        # Calculate mispricing
        prob_diff = expected_prob - market_prob

        # Generate signal
        signal_type = SignalType.NO_ACTION
        strength = SignalStrength.WEAK
        reason = ""

        # Check if lag and price difference meet thresholds
        if abs(lag_seconds) >= self.lag_threshold:
            if abs(prob_diff) >= 0.05:  # 5% probability difference
                if prob_diff > 0:
                    # Market underpriced Yes (oracle suggests higher)
                    signal_type = SignalType.BUY_YES
                    reason = f"Oracle ${oracle_price.price:.2f} above threshold ${threshold_price:.0f}, market lagging"
                else:
                    # Market overpriced Yes (oracle suggests lower)
                    signal_type = SignalType.BUY_NO
                    reason = f"Oracle ${oracle_price.price:.2f} suggests lower prob, market lagging"

                # Determine strength
                if abs(prob_diff) >= 0.15:
                    strength = SignalStrength.VERY_STRONG
                elif abs(prob_diff) >= 0.10:
                    strength = SignalStrength.STRONG
                elif abs(prob_diff) >= 0.05:
                    strength = SignalStrength.MODERATE

        # Calculate confidence based on multiple factors
        confidence = self._calculate_confidence(
            lag_seconds=abs(lag_seconds),
            prob_diff=abs(prob_diff),
            oracle_confidence=oracle_price.confidence,
            market_liquidity=market.liquidity
        )

        # Calculate recommended size
        recommended_size = self._calculate_position_size(
            confidence=confidence,
            strength=strength,
            market_liquidity=market.liquidity
        )

        # Calculate expected profit
        expected_profit = self._calculate_expected_profit(
            prob_diff=prob_diff,
            market_prob=market_prob,
            recommended_size=recommended_size
        )

        signal = Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            oracle_price=oracle_price.price,
            market_price=market_implied,
            price_threshold=threshold_price,
            lag_seconds=abs(lag_seconds),
            price_diff_pct=price_diff_pct,
            confidence=confidence,
            reason=reason,
            market_id=market.market_id,
            token_id=yes_outcome.token_id,
            recommended_size=recommended_size,
            expected_profit_pct=expected_profit
        )

        # Update state
        self.state.total_signals_generated += 1
        self.state.last_signal_time = signal.timestamp

        if signal.is_actionable:
            self.state.actionable_signals += 1

        # Store in history
        self.signal_history.append(signal)
        if len(self.signal_history) > self.max_signal_history:
            self.signal_history = self.signal_history[-self.max_signal_history:]

        return signal

    def _calculate_confidence(
        self,
        lag_seconds: float,
        prob_diff: float,
        oracle_confidence: float,
        market_liquidity: float
    ) -> float:
        """Calculate signal confidence score (0-1)."""
        # Base confidence from lag
        lag_factor = min(1.0, lag_seconds / 30.0)  # Max at 30s lag

        # Confidence from probability difference
        prob_factor = min(1.0, prob_diff / 0.2)  # Max at 20% diff

        # Oracle confidence factor
        oracle_factor = oracle_confidence

        # Liquidity factor (higher liquidity = higher confidence)
        liquidity_factor = min(1.0, market_liquidity / 10000)  # Max at $10k

        # Weighted average
        confidence = (
            lag_factor * 0.3 +
            prob_factor * 0.35 +
            oracle_factor * 0.2 +
            liquidity_factor * 0.15
        )

        return round(confidence, 3)

    def _calculate_position_size(
        self,
        confidence: float,
        strength: SignalStrength,
        market_liquidity: float
    ) -> float:
        """Calculate recommended position size."""
        # Base size
        base_size = self.max_position_size

        # Scale by confidence
        size = base_size * confidence

        # Scale by strength
        strength_multipliers = {
            SignalStrength.WEAK: 0.25,
            SignalStrength.MODERATE: 0.5,
            SignalStrength.STRONG: 0.75,
            SignalStrength.VERY_STRONG: 1.0
        }
        size *= strength_multipliers.get(strength, 0.5)

        # Don't exceed 10% of market liquidity
        max_from_liquidity = market_liquidity * 0.1
        size = min(size, max_from_liquidity)

        # Round to 2 decimal places
        return round(size, 2)

    def _calculate_expected_profit(
        self,
        prob_diff: float,
        market_prob: float,
        recommended_size: float
    ) -> float:
        """Calculate expected profit percentage."""
        # Simple model: expected profit is the probability edge
        # If we buy Yes at 0.50 and expect 0.55, expected profit is 5%
        expected_profit_pct = abs(prob_diff) * 100

        # Adjust for slippage and fees (~2%)
        expected_profit_pct -= 2.0

        return max(0, round(expected_profit_pct, 2))

    def generate_trade_action(
        self,
        signal: Signal,
        current_positions: int = 0
    ) -> Optional[TradeAction]:
        """
        Generate trade action from signal.

        Args:
            signal: Trading signal
            current_positions: Current number of open positions

        Returns:
            TradeAction if trade should be executed, None otherwise
        """
        if not signal.is_actionable:
            return None

        if current_positions >= self.max_concurrent_positions:
            logger.warning("Max concurrent positions reached, skipping signal")
            return None

        if signal.confidence < self.confidence_threshold:
            return None

        # Determine trade side
        if signal.signal_type == SignalType.BUY_YES:
            side = "BUY"
            token_id = signal.token_id
        elif signal.signal_type == SignalType.BUY_NO:
            side = "BUY"
            # For BUY_NO, we need the No token ID
            # This would need to be passed through the signal
            token_id = signal.token_id  # Placeholder
        else:
            return None

        action = TradeAction(
            action_id=str(uuid.uuid4()),
            signal=signal,
            token_id=token_id,
            side=side,
            price=0.0,  # Market order
            size=signal.recommended_size,
            order_type="FOK",  # Fill or Kill for fast execution
            stop_loss=self._calculate_stop_loss(signal),
            take_profit=self._calculate_take_profit(signal),
            max_slippage=0.02
        )

        self.pending_actions.append(action)

        return action

    def _calculate_stop_loss(self, signal: Signal) -> float:
        """Calculate stop loss price."""
        # Stop loss at 5% below entry price
        if signal.signal_type == SignalType.BUY_YES:
            return max(0.01, signal.market_price * 0.95)
        else:
            return min(0.99, signal.market_price * 1.05)

    def _calculate_take_profit(self, signal: Signal) -> float:
        """Calculate take profit price."""
        # Take profit at expected edge
        expected_move = signal.expected_profit_pct / 100

        if signal.signal_type == SignalType.BUY_YES:
            return min(0.99, signal.market_price * (1 + expected_move))
        else:
            return max(0.01, signal.market_price * (1 - expected_move))

    async def process_price_update(
        self,
        symbol: str,
        oracle_price: PriceData,
        market: Market
    ) -> Optional[Signal]:
        """
        Process a price update and potentially generate a signal.

        Args:
            symbol: Cryptocurrency symbol
            oracle_price: New oracle price
            market: Current market state

        Returns:
            Generated signal if any
        """
        signal = self.analyze_lag(symbol, oracle_price, market)

        if signal:
            await self._notify_signal(signal)

            if signal.is_actionable and self.state.is_trading_enabled:
                action = self.generate_trade_action(
                    signal,
                    self.state.current_positions
                )

                if action:
                    await self._notify_action(action)

        return signal

    def start(self, trading_enabled: bool = False) -> None:
        """Start the strategy."""
        self.state.is_active = True
        self.state.is_trading_enabled = trading_enabled
        self.state.started_at = datetime.utcnow()
        logger.info(f"Strategy started (trading enabled: {trading_enabled})")

    def stop(self) -> None:
        """Stop the strategy."""
        self.state.is_active = False
        logger.info("Strategy stopped")

    def enable_trading(self) -> None:
        """Enable live trading."""
        self.state.is_trading_enabled = True
        logger.info("Trading enabled")

    def disable_trading(self) -> None:
        """Disable live trading."""
        self.state.is_trading_enabled = False
        logger.info("Trading disabled")

    def get_state(self) -> Dict:
        """Get current strategy state."""
        return self.state.to_dict()

    def get_recent_signals(self, count: int = 10) -> List[Dict]:
        """Get recent signals."""
        return [s.to_dict() for s in self.signal_history[-count:]]

    def get_pending_actions(self) -> List[Dict]:
        """Get pending trade actions."""
        return [a.to_dict() for a in self.pending_actions]
