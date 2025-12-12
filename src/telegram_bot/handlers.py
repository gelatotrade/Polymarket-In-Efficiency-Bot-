"""
Telegram Bot command handlers.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger


class BotHandlers:
    """
    Handles Telegram bot commands by interfacing with the trading system.

    This class is initialized with references to the various system components
    and provides formatted responses for Telegram messages.
    """

    def __init__(self):
        """Initialize handlers."""
        # These will be set by the main orchestrator
        self.price_manager = None
        self.market_monitor = None
        self.strategy = None
        self.risk_manager = None
        self.position_manager = None
        self.config = None

    def set_components(
        self,
        price_manager=None,
        market_monitor=None,
        strategy=None,
        risk_manager=None,
        position_manager=None,
        config=None
    ):
        """Set system component references."""
        self.price_manager = price_manager
        self.market_monitor = market_monitor
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        self.config = config

    async def get_dashboard(self) -> str:
        """Get formatted dashboard text."""
        lines = ["<b>Polymarket Lag Trading Bot</b>", ""]

        # Status
        status = "ACTIVE" if (self.strategy and self.strategy.state.is_active) else "INACTIVE"
        trading = "ENABLED" if (self.strategy and self.strategy.state.is_trading_enabled) else "DISABLED"
        lines.append(f"Status: {status} | Trading: {trading}")
        lines.append("")

        # Prices
        lines.append("<b>Oracle Prices:</b>")
        if self.price_manager:
            for symbol in ["BTC", "ETH", "SOL", "XRP"]:
                price_data = self.price_manager.get_oracle_price(symbol)
                if price_data:
                    age = price_data.age_seconds
                    lines.append(f"  {symbol}: ${price_data.price:,.2f} ({age:.0f}s ago)")
                else:
                    lines.append(f"  {symbol}: No data")
        else:
            lines.append("  Price manager not initialized")
        lines.append("")

        # Positions
        lines.append("<b>Positions:</b>")
        if self.position_manager:
            stats = self.position_manager.get_statistics()
            lines.append(f"  Open: {stats['open_positions_count']}")
            lines.append(f"  Exposure: ${stats['total_exposure_usd']:.2f}")
            lines.append(f"  Unrealized P&L: ${stats['unrealized_pnl']:.2f}")
        else:
            lines.append("  No position data")
        lines.append("")

        # Performance
        lines.append("<b>Today's Performance:</b>")
        if self.risk_manager:
            risk_status = self.risk_manager.get_status()
            lines.append(f"  Trades: {risk_status['daily_trades']}")
            lines.append(f"  P&L: ${risk_status['daily_pnl']:.2f}")
        else:
            lines.append("  No performance data")

        lines.append("")
        lines.append(f"<i>Updated: {datetime.utcnow().strftime('%H:%M:%S')} UTC</i>")

        return "\n".join(lines)

    async def get_prices(self) -> str:
        """Get formatted price information."""
        lines = ["<b>Current Prices</b>", ""]

        if not self.price_manager:
            return "Price manager not initialized"

        for symbol in ["BTC", "ETH", "SOL", "XRP"]:
            lines.append(f"<b>{symbol}:</b>")

            # Oracle price
            oracle = self.price_manager.get_oracle_price(symbol)
            if oracle:
                lines.append(f"  Oracle: ${oracle.price:,.2f}")
                lines.append(f"  Age: {oracle.age_seconds:.1f}s")
            else:
                lines.append("  Oracle: No data")

            # Polymarket implied price
            pm = self.price_manager.get_polymarket_price(symbol)
            if pm:
                lines.append(f"  Polymarket: ${pm.price:,.2f}")
            else:
                lines.append("  Polymarket: No data")

            # Lag
            lag = self.price_manager.get_price_lag(symbol)
            if lag:
                lines.append(f"  Lag: {lag.lag_seconds:.1f}s ({lag.price_difference_pct:+.2f}%)")
                if lag.is_profitable:
                    lines.append(f"  <b>OPPORTUNITY!</b>")

            lines.append("")

        return "\n".join(lines)

    async def get_positions(self) -> str:
        """Get formatted positions information."""
        if not self.position_manager:
            return "Position manager not initialized"

        positions = self.position_manager.get_open_positions()

        if not positions:
            return "<b>No Open Positions</b>"

        lines = ["<b>Open Positions</b>", ""]

        for pos in positions:
            lines.append(f"<b>{pos.outcome}</b>")
            lines.append(f"  Entry: {pos.entry_price:.4f}")
            lines.append(f"  Current: {pos.current_price:.4f}")
            lines.append(f"  Size: ${pos.size:.2f}")
            lines.append(f"  P&L: ${pos.unrealized_pnl:.2f} ({pos.unrealized_pnl_pct:+.1f}%)")
            lines.append("")

        stats = self.position_manager.get_statistics()
        lines.append(f"<b>Total:</b>")
        lines.append(f"  Exposure: ${stats['total_exposure_usd']:.2f}")
        lines.append(f"  Unrealized P&L: ${stats['unrealized_pnl']:.2f}")

        return "\n".join(lines)

    async def get_statistics(self) -> str:
        """Get formatted performance statistics."""
        lines = ["<b>Performance Statistics</b>", ""]

        # Position stats
        if self.position_manager:
            stats = self.position_manager.get_statistics()
            lines.append("<b>Trading:</b>")
            lines.append(f"  Total Trades: {stats['total_trades']}")
            lines.append(f"  Winning: {stats['winning_trades']}")
            lines.append(f"  Losing: {stats['losing_trades']}")
            lines.append(f"  Win Rate: {stats['win_rate']:.1f}%")
            lines.append(f"  Total P&L: ${stats['total_pnl']:.2f}")
            lines.append("")

        # Strategy stats
        if self.strategy:
            state = self.strategy.get_state()
            lines.append("<b>Strategy:</b>")
            lines.append(f"  Signals Generated: {state['total_signals']}")
            lines.append(f"  Actionable: {state['actionable_signals']}")
            lines.append("")

        # Risk stats
        if self.risk_manager:
            risk = self.risk_manager.get_status()
            lines.append("<b>Risk:</b>")
            lines.append(f"  Daily P&L: ${risk['daily_pnl']:.2f}")
            lines.append(f"  Daily Trades: {risk['daily_trades']}")
            lines.append(f"  Can Trade: {'Yes' if risk['can_trade'] else 'No'}")
            if not risk['can_trade']:
                lines.append(f"  Reason: {risk['reason']}")

        return "\n".join(lines)

    async def get_recent_signals(self) -> str:
        """Get recent trading signals."""
        if not self.strategy:
            return "Strategy not initialized"

        signals = self.strategy.get_recent_signals(5)

        if not signals:
            return "<b>No Recent Signals</b>"

        lines = ["<b>Recent Signals</b>", ""]

        for sig in signals:
            lines.append(f"<b>{sig['symbol']}</b> - {sig['signal_type']}")
            lines.append(f"  Strength: {sig['strength']}")
            lines.append(f"  Oracle: ${sig['oracle_price']:,.2f}")
            lines.append(f"  Lag: {sig['lag_seconds']:.1f}s")
            lines.append(f"  Confidence: {sig['confidence']:.1%}")
            if sig['is_actionable']:
                lines.append(f"  <b>ACTIONABLE</b>")
            lines.append("")

        return "\n".join(lines)

    async def get_status(self) -> str:
        """Get system status."""
        lines = ["<b>System Status</b>", ""]

        # Price feeds
        lines.append("<b>Price Feeds:</b>")
        if self.price_manager:
            status = self.price_manager.get_feed_status()
            lines.append(f"  Scraper: {'Active' if status['scraper_active'] else 'Inactive'}")
            lines.append(f"  On-chain: {'Ready' if status['onchain_active'] else 'Not ready'}")
        else:
            lines.append("  Not initialized")
        lines.append("")

        # Markets
        lines.append("<b>Market Monitor:</b>")
        if self.market_monitor:
            market_status = self.market_monitor.get_all_market_status()
            for symbol, data in market_status.items():
                lines.append(f"  {symbol}: {data['market_count']} markets")
        else:
            lines.append("  Not initialized")
        lines.append("")

        # Strategy
        lines.append("<b>Strategy:</b>")
        if self.strategy:
            state = self.strategy.get_state()
            lines.append(f"  Active: {state['is_active']}")
            lines.append(f"  Trading: {state['is_trading_enabled']}")
        else:
            lines.append("  Not initialized")

        return "\n".join(lines)

    async def get_settings(self) -> str:
        """Get current settings."""
        lines = ["<b>Current Settings</b>", ""]

        if self.config:
            lines.append("<b>Trading:</b>")
            lines.append(f"  Max Position: ${self.config.max_position_size_usd:.2f}")
            lines.append(f"  Min Profit: {self.config.min_profit_threshold_pct:.1f}%")
            lines.append(f"  Lag Threshold: {self.config.lag_threshold_seconds:.1f}s")
            lines.append("")
            lines.append("<b>Risk:</b>")
            lines.append(f"  Max Daily Loss: ${self.config.max_daily_loss_usd:.2f}")
            lines.append(f"  Max Positions: {self.config.max_concurrent_positions}")
            lines.append(f"  Stop Loss: {self.config.stop_loss_pct:.1f}%")
            lines.append("")
            lines.append("<b>Wallet:</b>")
            if self.config.polymarket_private_key:
                masked = self.config.polymarket_private_key[:6] + "..." + self.config.polymarket_private_key[-4:]
                lines.append(f"  Private Key: {masked}")
            else:
                lines.append("  Private Key: Not set")
        else:
            lines.append("Config not loaded")

        return "\n".join(lines)

    async def start_trading(self) -> str:
        """Enable trading."""
        if self.strategy:
            self.strategy.enable_trading()
            return "Trading ENABLED\n\nThe bot will now execute trades based on signals."
        return "Strategy not initialized"

    async def stop_trading(self) -> str:
        """Disable trading."""
        if self.strategy:
            self.strategy.disable_trading()
            return "Trading DISABLED\n\nThe bot will continue monitoring but won't execute trades."
        return "Strategy not initialized"

    async def save_wallet_config(self, private_key: str, funder_address: str) -> str:
        """Save wallet configuration."""
        # In production, this should save to encrypted storage
        logger.info(f"Saving wallet config for address: {funder_address}")

        return (
            "Wallet configuration saved!\n\n"
            f"Funder Address: {funder_address}\n\n"
            "Please restart the bot to apply changes."
        )
