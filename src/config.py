"""
Configuration management for the Polymarket In-Efficiency Bot.
"""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Configuration
    telegram_bot_token: str = Field(default="", description="Telegram bot token from @BotFather")
    telegram_admin_ids: str = Field(default="", description="Comma-separated admin user IDs")

    # Polymarket Configuration
    polymarket_private_key: str = Field(default="", description="Polymarket wallet private key")
    polymarket_funder_address: str = Field(default="", description="Funder address for proxy wallets")
    polymarket_signature_type: int = Field(default=1, description="Signature type (0=EOA, 1=Email, 2=Browser)")
    polymarket_clob_host: str = Field(default="https://clob.polymarket.com", description="CLOB API host")
    polymarket_gamma_host: str = Field(default="https://gamma-api.polymarket.com", description="Gamma API host")
    polygon_chain_id: int = Field(default=137, description="Polygon chain ID")

    # Chainlink Configuration
    chainlink_api_key: str = Field(default="", description="Chainlink Data Streams API key")
    chainlink_api_secret: str = Field(default="", description="Chainlink Data Streams API secret")

    # Trading Configuration
    trading_enabled: bool = Field(default=False, description="Enable live trading")
    max_position_size_usd: float = Field(default=100.0, description="Maximum position size in USD")
    min_profit_threshold_pct: float = Field(default=0.5, description="Minimum profit threshold percentage")
    max_slippage_pct: float = Field(default=0.3, description="Maximum allowed slippage percentage")
    lag_threshold_seconds: float = Field(default=10.0, description="Minimum lag to consider for trading")

    # Risk Management
    max_daily_loss_usd: float = Field(default=50.0, description="Maximum daily loss in USD")
    max_concurrent_positions: int = Field(default=3, description="Maximum concurrent open positions")
    stop_loss_pct: float = Field(default=2.0, description="Stop loss percentage")

    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./data/bot.db", description="Database connection URL")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="./logs/bot.log", description="Log file path")

    # Price Feed Intervals (seconds)
    price_scrape_interval: float = Field(default=1.0, description="Price scraping interval")
    orderbook_scan_interval: float = Field(default=2.0, description="Order book scanning interval")

    # Chainlink Price Feed URLs for scraping
    chainlink_btc_url: str = Field(
        default="https://data.chain.link/streams/btc-usd-cexprice-streams",
        description="Chainlink BTC/USD price feed URL"
    )
    chainlink_eth_url: str = Field(
        default="https://data.chain.link/streams/eth-usd-cexprice-streams",
        description="Chainlink ETH/USD price feed URL"
    )
    chainlink_sol_url: str = Field(
        default="https://data.chain.link/streams/sol-usd-cexprice-streams",
        description="Chainlink SOL/USD price feed URL"
    )
    chainlink_xrp_url: str = Field(
        default="https://data.chain.link/streams/xrp-usd-cexprice-streams",
        description="Chainlink XRP/USD price feed URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def admin_ids(self) -> List[int]:
        """Parse admin IDs from comma-separated string."""
        if not self.telegram_admin_ids:
            return []
        return [int(id.strip()) for id in self.telegram_admin_ids.split(",") if id.strip()]

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin."""
        return user_id in self.admin_ids


# Supported cryptocurrencies and their Polymarket market identifiers
SUPPORTED_CRYPTOS = {
    "BTC": {
        "name": "Bitcoin",
        "chainlink_feed": "btc-usd-cexprice-streams",
        "decimals": 8,
        "polymarket_slug": "bitcoin"
    },
    "ETH": {
        "name": "Ethereum",
        "chainlink_feed": "eth-usd-cexprice-streams",
        "decimals": 8,
        "polymarket_slug": "ethereum"
    },
    "SOL": {
        "name": "Solana",
        "chainlink_feed": "sol-usd-cexprice-streams",
        "decimals": 8,
        "polymarket_slug": "solana"
    },
    "XRP": {
        "name": "XRP",
        "chainlink_feed": "xrp-usd-cexprice-streams",
        "decimals": 8,
        "polymarket_slug": "xrp"
    }
}


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
