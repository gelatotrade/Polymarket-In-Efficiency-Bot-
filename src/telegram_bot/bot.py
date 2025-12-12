"""
Main Telegram Bot implementation using aiogram.
"""

import asyncio
from typing import Optional, List, Callable
from datetime import datetime
from loguru import logger

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

from .handlers import BotHandlers
from .keyboard import get_main_keyboard, get_settings_keyboard, get_confirm_keyboard


class SetupStates(StatesGroup):
    """States for bot setup wizard."""
    waiting_private_key = State()
    waiting_funder_address = State()
    confirm_setup = State()


class TelegramBot:
    """
    Telegram Bot for controlling and monitoring the trading bot.

    Features:
    - Real-time dashboard with prices and positions
    - Trading controls (enable/disable)
    - Configuration management
    - Alert notifications
    - Performance statistics
    """

    def __init__(
        self,
        token: str,
        admin_ids: List[int],
        handlers: Optional[BotHandlers] = None
    ):
        """
        Initialize the Telegram bot.

        Args:
            token: Telegram bot token
            admin_ids: List of admin user IDs
            handlers: Bot handlers instance
        """
        self.token = token
        self.admin_ids = admin_ids
        self.handlers = handlers or BotHandlers()

        # Bot and dispatcher
        self.bot = Bot(token=token, parse_mode=ParseMode.HTML)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)

        # Setup flag
        self._setup_complete = False

        # Register handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register message and callback handlers."""

        # Start command
        @self.dp.message(CommandStart())
        async def start_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                await message.answer("Unauthorized. This bot is private.")
                return

            await message.answer(
                "Welcome to Polymarket In-Efficiency Bot!\n\n"
                "This bot exploits the lag between Chainlink oracle prices "
                "and Polymarket order book updates.\n\n"
                "Use /help to see available commands.",
                reply_markup=get_main_keyboard()
            )

        # Help command
        @self.dp.message(Command("help"))
        async def help_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            help_text = """
<b>Available Commands:</b>

<b>Dashboard:</b>
/dashboard - Show live dashboard
/prices - Show current prices
/positions - Show open positions
/stats - Show performance statistics

<b>Trading:</b>
/start_trading - Enable trading
/stop_trading - Disable trading
/signals - Show recent signals

<b>Configuration:</b>
/setup - Configure wallet and API keys
/settings - View/edit settings
/limits - View/edit risk limits

<b>System:</b>
/status - Bot status
/logs - Recent logs
/restart - Restart components
            """
            await message.answer(help_text)

        # Dashboard command
        @self.dp.message(Command("dashboard"))
        async def dashboard_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            dashboard = await self.handlers.get_dashboard()
            await message.answer(dashboard, reply_markup=get_main_keyboard())

        # Prices command
        @self.dp.message(Command("prices"))
        async def prices_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            prices = await self.handlers.get_prices()
            await message.answer(prices)

        # Positions command
        @self.dp.message(Command("positions"))
        async def positions_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            positions = await self.handlers.get_positions()
            await message.answer(positions)

        # Stats command
        @self.dp.message(Command("stats"))
        async def stats_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            stats = await self.handlers.get_statistics()
            await message.answer(stats)

        # Signals command
        @self.dp.message(Command("signals"))
        async def signals_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            signals = await self.handlers.get_recent_signals()
            await message.answer(signals)

        # Start trading command
        @self.dp.message(Command("start_trading"))
        async def start_trading_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            await message.answer(
                "Are you sure you want to enable live trading?",
                reply_markup=get_confirm_keyboard("enable_trading")
            )

        # Stop trading command
        @self.dp.message(Command("stop_trading"))
        async def stop_trading_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            result = await self.handlers.stop_trading()
            await message.answer(result)

        # Status command
        @self.dp.message(Command("status"))
        async def status_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            status = await self.handlers.get_status()
            await message.answer(status)

        # Settings command
        @self.dp.message(Command("settings"))
        async def settings_handler(message: Message):
            if not self._is_admin(message.from_user.id):
                return

            settings = await self.handlers.get_settings()
            await message.answer(settings, reply_markup=get_settings_keyboard())

        # Setup command
        @self.dp.message(Command("setup"))
        async def setup_handler(message: Message, state: FSMContext):
            if not self._is_admin(message.from_user.id):
                return

            await message.answer(
                "<b>Wallet Setup</b>\n\n"
                "Please enter your Polymarket wallet private key.\n"
                "You can export this from Polymarket.com:\n"
                "Cash -> (...) -> Export Private Key\n\n"
                "<i>Your key will be stored securely.</i>"
            )
            await state.set_state(SetupStates.waiting_private_key)

        # Handle private key input
        @self.dp.message(SetupStates.waiting_private_key)
        async def handle_private_key(message: Message, state: FSMContext):
            if not self._is_admin(message.from_user.id):
                return

            private_key = message.text.strip()

            # Delete message with key for security
            await message.delete()

            # Validate key format
            if not private_key.startswith("0x") or len(private_key) != 66:
                await message.answer(
                    "Invalid private key format. Please enter a valid key starting with 0x."
                )
                return

            await state.update_data(private_key=private_key)

            await message.answer(
                "Private key saved.\n\n"
                "Now enter your funder address (the wallet that holds your funds).\n"
                "This is your Polygon wallet address."
            )
            await state.set_state(SetupStates.waiting_funder_address)

        # Handle funder address input
        @self.dp.message(SetupStates.waiting_funder_address)
        async def handle_funder_address(message: Message, state: FSMContext):
            if not self._is_admin(message.from_user.id):
                return

            funder_address = message.text.strip()

            # Validate address format
            if not funder_address.startswith("0x") or len(funder_address) != 42:
                await message.answer(
                    "Invalid address format. Please enter a valid Ethereum address."
                )
                return

            await state.update_data(funder_address=funder_address)

            data = await state.get_data()
            masked_key = data["private_key"][:6] + "..." + data["private_key"][-4:]

            await message.answer(
                f"<b>Confirm Setup</b>\n\n"
                f"Private Key: {masked_key}\n"
                f"Funder Address: {funder_address}\n\n"
                f"Confirm this configuration?",
                reply_markup=get_confirm_keyboard("confirm_setup")
            )
            await state.set_state(SetupStates.confirm_setup)

        # Callback query handlers
        @self.dp.callback_query(F.data.startswith("confirm_"))
        async def handle_confirm(callback: CallbackQuery, state: FSMContext):
            if not self._is_admin(callback.from_user.id):
                await callback.answer("Unauthorized")
                return

            action = callback.data.replace("confirm_", "")

            if action == "setup_yes":
                data = await state.get_data()
                result = await self.handlers.save_wallet_config(
                    data.get("private_key", ""),
                    data.get("funder_address", "")
                )
                await callback.message.edit_text(result)
                await state.clear()

            elif action == "setup_no":
                await callback.message.edit_text("Setup cancelled.")
                await state.clear()

            elif action == "enable_trading_yes":
                result = await self.handlers.start_trading()
                await callback.message.edit_text(result)

            elif action.endswith("_no"):
                await callback.message.edit_text("Action cancelled.")

            await callback.answer()

        # Dashboard refresh callback
        @self.dp.callback_query(F.data == "refresh_dashboard")
        async def refresh_dashboard(callback: CallbackQuery):
            if not self._is_admin(callback.from_user.id):
                await callback.answer("Unauthorized")
                return

            dashboard = await self.handlers.get_dashboard()
            await callback.message.edit_text(dashboard, reply_markup=get_main_keyboard())
            await callback.answer("Dashboard refreshed")

        # Button handlers
        @self.dp.callback_query(F.data == "btn_prices")
        async def btn_prices(callback: CallbackQuery):
            if not self._is_admin(callback.from_user.id):
                return
            prices = await self.handlers.get_prices()
            await callback.message.answer(prices)
            await callback.answer()

        @self.dp.callback_query(F.data == "btn_positions")
        async def btn_positions(callback: CallbackQuery):
            if not self._is_admin(callback.from_user.id):
                return
            positions = await self.handlers.get_positions()
            await callback.message.answer(positions)
            await callback.answer()

        @self.dp.callback_query(F.data == "btn_signals")
        async def btn_signals(callback: CallbackQuery):
            if not self._is_admin(callback.from_user.id):
                return
            signals = await self.handlers.get_recent_signals()
            await callback.message.answer(signals)
            await callback.answer()

        @self.dp.callback_query(F.data == "btn_stats")
        async def btn_stats(callback: CallbackQuery):
            if not self._is_admin(callback.from_user.id):
                return
            stats = await self.handlers.get_statistics()
            await callback.message.answer(stats)
            await callback.answer()

    def _is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in self.admin_ids

    async def send_alert(self, message: str) -> None:
        """Send alert to all admins."""
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, f"ALERT\n\n{message}")
            except Exception as e:
                logger.error(f"Failed to send alert to {admin_id}: {e}")

    async def send_signal_notification(self, signal_data: dict) -> None:
        """Send signal notification to admins."""
        text = (
            f"<b>New Signal</b>\n\n"
            f"Symbol: {signal_data.get('symbol')}\n"
            f"Type: {signal_data.get('signal_type')}\n"
            f"Strength: {signal_data.get('strength')}\n"
            f"Oracle Price: ${signal_data.get('oracle_price', 0):,.2f}\n"
            f"Market Price: ${signal_data.get('market_price', 0):,.2f}\n"
            f"Lag: {signal_data.get('lag_seconds', 0):.1f}s\n"
            f"Confidence: {signal_data.get('confidence', 0):.1%}\n"
            f"Expected Profit: {signal_data.get('expected_profit_pct', 0):.1f}%"
        )

        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, text)
            except Exception as e:
                logger.error(f"Failed to send signal to {admin_id}: {e}")

    async def send_trade_notification(self, trade_data: dict) -> None:
        """Send trade notification to admins."""
        text = (
            f"<b>Trade Executed</b>\n\n"
            f"Symbol: {trade_data.get('symbol')}\n"
            f"Side: {trade_data.get('side')}\n"
            f"Size: ${trade_data.get('size', 0):.2f}\n"
            f"Price: {trade_data.get('price', 0):.4f}"
        )

        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, text)
            except Exception as e:
                logger.error(f"Failed to send trade notification to {admin_id}: {e}")

    async def start(self) -> None:
        """Start the bot."""
        logger.info("Starting Telegram bot...")

        try:
            # Start polling
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Bot error: {e}")
            raise

    async def stop(self) -> None:
        """Stop the bot."""
        logger.info("Stopping Telegram bot...")
        await self.dp.stop_polling()
        await self.bot.session.close()
