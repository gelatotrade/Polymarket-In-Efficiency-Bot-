"""
Main Orchestrator - Coordinates all system components.
"""

import asyncio
from datetime import datetime
from typing import Optional
from loguru import logger

from .config import Settings, get_settings
from .price_feeds import PriceManager
from .polymarket import PolymarketClient, MarketMonitor
from .strategy import LagTradingStrategy, RiskManager, PositionManager
from .telegram_bot import TelegramBot, BotHandlers
from .database import Database
from .utils import setup_logging


class Orchestrator:
    """
    Main orchestrator that coordinates all system components.

    Responsibilities:
    - Initialize and manage all components
    - Connect component callbacks
    - Handle system lifecycle
    - Coordinate price updates and trading decisions
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the orchestrator.

        Args:
            settings: Application settings
        """
        self.settings = settings or get_settings()

        # Components
        self.price_manager: Optional[PriceManager] = None
        self.polymarket_client: Optional[PolymarketClient] = None
        self.market_monitor: Optional[MarketMonitor] = None
        self.strategy: Optional[LagTradingStrategy] = None
        self.risk_manager: Optional[RiskManager] = None
        self.position_manager: Optional[PositionManager] = None
        self.telegram_bot: Optional[TelegramBot] = None
        self.database: Optional[Database] = None

        # State
        self._running = False
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing Polymarket In-Efficiency Bot...")

        # Setup logging
        setup_logging(
            log_level=self.settings.log_level,
            log_file=self.settings.log_file
        )

        # Initialize database
        self.database = Database(self.settings.database_url)
        await self.database.initialize()

        # Initialize price manager
        self.price_manager = PriceManager(
            use_scraper=True,
            use_onchain=True
        )
        await self.price_manager.initialize()

        # Initialize Polymarket client
        self.polymarket_client = PolymarketClient(
            private_key=self.settings.polymarket_private_key or None,
            funder_address=self.settings.polymarket_funder_address or None,
            signature_type=self.settings.polymarket_signature_type
        )
        await self.polymarket_client.initialize()

        # Initialize market monitor
        self.market_monitor = MarketMonitor(self.polymarket_client)
        await self.market_monitor.initialize()

        # Initialize strategy components
        self.risk_manager = RiskManager()
        self.position_manager = PositionManager()
        self.strategy = LagTradingStrategy(
            lag_threshold=self.settings.lag_threshold_seconds,
            price_diff_threshold=self.settings.min_profit_threshold_pct,
            max_position_size=self.settings.max_position_size_usd,
            max_concurrent_positions=self.settings.max_concurrent_positions
        )

        # Initialize Telegram bot
        if self.settings.telegram_bot_token:
            handlers = BotHandlers()
            handlers.set_components(
                price_manager=self.price_manager,
                market_monitor=self.market_monitor,
                strategy=self.strategy,
                risk_manager=self.risk_manager,
                position_manager=self.position_manager,
                config=self.settings
            )

            self.telegram_bot = TelegramBot(
                token=self.settings.telegram_bot_token,
                admin_ids=self.settings.admin_ids,
                handlers=handlers
            )

        # Connect callbacks
        self._connect_callbacks()

        self._initialized = True
        logger.info("All components initialized")

    def _connect_callbacks(self) -> None:
        """Connect component callbacks."""
        # Price manager -> Strategy
        self.price_manager.add_lag_callback(self._on_lag_detected)

        # Market monitor -> Update polymarket prices
        self.market_monitor.add_orderbook_callback(self._on_orderbook_update)

        # Strategy -> Execute trades
        self.strategy.add_signal_callback(self._on_signal)
        self.strategy.add_action_callback(self._on_trade_action)

    async def _on_lag_detected(self, lag) -> None:
        """Handle detected price lag."""
        if lag.is_profitable:
            logger.info(f"Profitable lag detected: {lag.symbol} - {lag.price_difference_pct:.2f}%")

            # Save to database
            if self.database:
                await self.database.save_signal({
                    "symbol": lag.symbol,
                    "signal_type": "lag_detected",
                    "strength": "strong" if abs(lag.price_difference_pct) > 1 else "moderate",
                    "oracle_price": lag.oracle_price,
                    "market_price": lag.polymarket_price,
                    "lag_seconds": lag.lag_seconds,
                    "price_diff_pct": lag.price_difference_pct,
                    "confidence": 0.8,
                    "is_actionable": True,
                    "timestamp": datetime.utcnow()
                })

    async def _on_orderbook_update(self, market) -> None:
        """Handle order book update."""
        if not market.crypto_symbol:
            return

        # Update Polymarket price in price manager
        implied_price = market.get_implied_price()
        if implied_price:
            self.price_manager.update_polymarket_price(
                symbol=market.crypto_symbol,
                price=implied_price,
                timestamp=datetime.utcnow()
            )

            # Process through strategy
            oracle_price = self.price_manager.get_oracle_price(market.crypto_symbol)
            if oracle_price:
                await self.strategy.process_price_update(
                    symbol=market.crypto_symbol,
                    oracle_price=oracle_price,
                    market=market
                )

    async def _on_signal(self, signal) -> None:
        """Handle new trading signal."""
        logger.info(f"Signal generated: {signal.symbol} - {signal.signal_type.value} ({signal.strength.value})")

        # Save to database
        if self.database:
            await self.database.save_signal(signal.to_dict())

        # Send Telegram notification
        if self.telegram_bot and signal.is_actionable:
            await self.telegram_bot.send_signal_notification(signal.to_dict())

    async def _on_trade_action(self, action) -> None:
        """Handle trade action from strategy."""
        logger.info(f"Trade action: {action.side} {action.token_id} @ {action.price}")

        # Validate with risk manager
        is_valid, reason = self.risk_manager.validate_trade(action)
        if not is_valid:
            logger.warning(f"Trade rejected by risk manager: {reason}")
            return

        # Execute trade
        if self.strategy.state.is_trading_enabled and self.polymarket_client.is_trading_enabled:
            await self._execute_trade(action)

    async def _execute_trade(self, action) -> None:
        """Execute a trade."""
        try:
            from .polymarket.models import OrderSide

            side = OrderSide.BUY if action.side == "BUY" else OrderSide.SELL

            # Place market order
            order = await self.polymarket_client.place_market_order(
                token_id=action.token_id,
                side=side,
                amount_usd=action.size
            )

            if order:
                logger.info(f"Trade executed: {order.order_id}")

                # Update action
                action.executed = True
                action.executed_at = datetime.utcnow()
                action.order_id = order.order_id
                action.execution_price = order.price

                # Open position
                position = self.position_manager.open_position(action, order.price)

                # Update risk manager
                self.risk_manager.on_trade_opened(action.size)

                # Save to database
                if self.database:
                    await self.database.save_trade({
                        "trade_id": order.order_id,
                        "symbol": action.signal.symbol,
                        "token_id": action.token_id,
                        "side": action.side,
                        "order_type": action.order_type,
                        "executed_price": order.price,
                        "size": action.size,
                        "status": "filled",
                        "executed_at": datetime.utcnow()
                    })

                # Send notification
                if self.telegram_bot:
                    await self.telegram_bot.send_trade_notification({
                        "symbol": action.signal.symbol,
                        "side": action.side,
                        "size": action.size,
                        "price": order.price
                    })

            else:
                logger.error("Trade execution failed")

        except Exception as e:
            logger.error(f"Trade execution error: {e}")

    async def start(self) -> None:
        """Start all components."""
        if not self._initialized:
            await self.initialize()

        self._running = True
        logger.info("Starting Polymarket In-Efficiency Bot...")

        # Start components
        tasks = []

        # Start price monitoring
        tasks.append(
            asyncio.create_task(
                self.price_manager.start(self.settings.price_scrape_interval)
            )
        )

        # Start market monitoring
        tasks.append(
            asyncio.create_task(
                self.market_monitor.start(self.settings.orderbook_scan_interval)
            )
        )

        # Start strategy
        self.strategy.start(trading_enabled=self.settings.trading_enabled)

        # Start Telegram bot
        if self.telegram_bot:
            tasks.append(
                asyncio.create_task(self.telegram_bot.start())
            )

        logger.info("All components started")

        # Wait for tasks
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")

    async def stop(self) -> None:
        """Stop all components."""
        logger.info("Stopping Polymarket In-Efficiency Bot...")
        self._running = False

        # Stop components
        if self.strategy:
            self.strategy.stop()

        if self.market_monitor:
            self.market_monitor.stop()

        if self.price_manager:
            self.price_manager.stop()
            await self.price_manager.close()

        if self.polymarket_client:
            await self.polymarket_client.close()

        if self.telegram_bot:
            await self.telegram_bot.stop()

        if self.database:
            await self.database.close()

        logger.info("Bot stopped")

    async def run(self) -> None:
        """Run the bot (blocking)."""
        try:
            await self.start()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
        finally:
            await self.stop()
