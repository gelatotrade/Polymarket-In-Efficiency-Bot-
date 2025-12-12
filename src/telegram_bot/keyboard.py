"""
Telegram keyboard layouts.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Get main dashboard keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Prices", callback_data="btn_prices"),
            InlineKeyboardButton(text="Positions", callback_data="btn_positions")
        ],
        [
            InlineKeyboardButton(text="Signals", callback_data="btn_signals"),
            InlineKeyboardButton(text="Stats", callback_data="btn_stats")
        ],
        [
            InlineKeyboardButton(text="Refresh", callback_data="refresh_dashboard")
        ]
    ])
    return keyboard


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Get settings keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Edit Wallet", callback_data="settings_wallet"),
            InlineKeyboardButton(text="Edit Limits", callback_data="settings_limits")
        ],
        [
            InlineKeyboardButton(text="Enable Trading", callback_data="settings_enable"),
            InlineKeyboardButton(text="Disable Trading", callback_data="settings_disable")
        ],
        [
            InlineKeyboardButton(text="Back", callback_data="refresh_dashboard")
        ]
    ])
    return keyboard


def get_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Get confirmation keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Yes", callback_data=f"confirm_{action}_yes"),
            InlineKeyboardButton(text="No", callback_data=f"confirm_{action}_no")
        ]
    ])
    return keyboard


def get_position_keyboard(position_id: str) -> InlineKeyboardMarkup:
    """Get position management keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Close Position", callback_data=f"close_position_{position_id}")
        ],
        [
            InlineKeyboardButton(text="Back", callback_data="btn_positions")
        ]
    ])
    return keyboard


def get_trading_keyboard(is_enabled: bool) -> InlineKeyboardMarkup:
    """Get trading control keyboard."""
    if is_enabled:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Stop Trading", callback_data="trading_stop")
            ],
            [
                InlineKeyboardButton(text="Close All Positions", callback_data="trading_close_all")
            ]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Start Trading", callback_data="trading_start")
            ]
        ])
    return keyboard


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Get simple back keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Back to Dashboard", callback_data="refresh_dashboard")
        ]
    ])
    return keyboard
