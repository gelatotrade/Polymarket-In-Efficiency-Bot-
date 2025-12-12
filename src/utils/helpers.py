"""
Helper utility functions.
"""

from datetime import datetime
from typing import Optional


def format_price(price: float, decimals: int = 2) -> str:
    """Format price with commas and decimals."""
    if price >= 1000:
        return f"${price:,.{decimals}f}"
    elif price >= 1:
        return f"${price:.{decimals}f}"
    else:
        return f"${price:.4f}"


def format_percentage(value: float, include_sign: bool = True) -> str:
    """Format percentage with sign."""
    if include_sign:
        return f"{value:+.2f}%"
    return f"{value:.2f}%"


def format_timestamp(dt: datetime, include_date: bool = False) -> str:
    """Format timestamp for display."""
    if include_date:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt.strftime("%H:%M:%S")


def format_duration(seconds: float) -> str:
    """Format duration in human readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def truncate_string(s: str, max_length: int = 50, suffix: str = "...") -> str:
    """Truncate string to max length."""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def mask_private_key(key: str) -> str:
    """Mask private key for display."""
    if not key or len(key) < 10:
        return "***"
    return key[:6] + "..." + key[-4:]


def mask_address(address: str) -> str:
    """Mask wallet address for display."""
    if not address or len(address) < 10:
        return "***"
    return address[:6] + "..." + address[-4:]


def calculate_pnl_percentage(entry_price: float, current_price: float, side: str) -> float:
    """Calculate PnL percentage."""
    if entry_price == 0:
        return 0.0

    if side.upper() == "BUY":
        return ((current_price - entry_price) / entry_price) * 100
    else:
        return ((entry_price - current_price) / entry_price) * 100


def validate_private_key(key: str) -> bool:
    """Validate private key format."""
    if not key:
        return False
    if not key.startswith("0x"):
        return False
    if len(key) != 66:
        return False
    try:
        int(key, 16)
        return True
    except ValueError:
        return False


def validate_address(address: str) -> bool:
    """Validate Ethereum address format."""
    if not address:
        return False
    if not address.startswith("0x"):
        return False
    if len(address) != 42:
        return False
    try:
        int(address, 16)
        return True
    except ValueError:
        return False
