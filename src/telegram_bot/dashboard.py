"""
Real-time dashboard updates for Telegram.
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict
from loguru import logger


class Dashboard:
    """
    Manages real-time dashboard updates in Telegram.

    Features:
    - Auto-updating dashboard message
    - Live price updates
    - Position monitoring
    - Signal alerts
    """

    def __init__(self, bot, chat_id: int, update_interval: float = 10.0):
        """
        Initialize dashboard.

        Args:
            bot: TelegramBot instance
            chat_id: Chat ID to update
            update_interval: Seconds between updates
        """
        self.bot = bot
        self.chat_id = chat_id
        self.update_interval = update_interval

        self._message_id: Optional[int] = None
        self._running = False

    async def start(self) -> None:
        """Start dashboard updates."""
        self._running = True

        # Send initial dashboard
        try:
            dashboard_text = await self.bot.handlers.get_dashboard()
            from .keyboard import get_main_keyboard
            message = await self.bot.bot.send_message(
                self.chat_id,
                dashboard_text,
                reply_markup=get_main_keyboard()
            )
            self._message_id = message.message_id
        except Exception as e:
            logger.error(f"Failed to send initial dashboard: {e}")
            return

        # Start update loop
        asyncio.create_task(self._update_loop())

    async def stop(self) -> None:
        """Stop dashboard updates."""
        self._running = False

    async def _update_loop(self) -> None:
        """Update dashboard periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.update_interval)

                if not self._running:
                    break

                # Get updated dashboard
                dashboard_text = await self.bot.handlers.get_dashboard()

                # Update message
                if self._message_id:
                    from .keyboard import get_main_keyboard
                    await self.bot.bot.edit_message_text(
                        chat_id=self.chat_id,
                        message_id=self._message_id,
                        text=dashboard_text,
                        reply_markup=get_main_keyboard()
                    )

            except Exception as e:
                # Message edit fails if content hasn't changed
                if "message is not modified" not in str(e).lower():
                    logger.error(f"Dashboard update error: {e}")

    async def force_update(self) -> None:
        """Force an immediate dashboard update."""
        if self._message_id:
            try:
                dashboard_text = await self.bot.handlers.get_dashboard()
                from .keyboard import get_main_keyboard
                await self.bot.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self._message_id,
                    text=dashboard_text,
                    reply_markup=get_main_keyboard()
                )
            except Exception as e:
                if "message is not modified" not in str(e).lower():
                    logger.error(f"Force update error: {e}")
