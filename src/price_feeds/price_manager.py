"""
Price Manager - Central hub for managing all price feeds.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional, List, Callable
from loguru import logger

from .models import PriceData, PriceFeed, PriceLag, PriceSource
from .chainlink_scraper import ChainlinkPriceScraper, ChainlinkOnChainReader


class PriceManager:
    """
    Central manager for all price feeds.

    Aggregates data from:
    - Chainlink web scraper (primary, low latency)
    - Chainlink on-chain reader (backup)
    - Polymarket implied prices

    Detects lag between oracle and market prices.
    """

    def __init__(self, use_scraper: bool = True, use_onchain: bool = True):
        """
        Initialize the price manager.

        Args:
            use_scraper: Use web scraper for Chainlink prices
            use_onchain: Use on-chain reader as backup
        """
        self.use_scraper = use_scraper
        self.use_onchain = use_onchain

        # Price sources
        self.scraper: Optional[ChainlinkPriceScraper] = None
        self.onchain_reader: Optional[ChainlinkOnChainReader] = None

        # Price feeds by symbol
        self.oracle_feeds: Dict[str, PriceFeed] = {}
        self.polymarket_feeds: Dict[str, PriceFeed] = {}

        # Callbacks for price updates
        self._price_callbacks: List[Callable] = []
        self._lag_callbacks: List[Callable] = []

        # Running state
        self._running = False

    async def initialize(self) -> None:
        """Initialize all price sources."""
        logger.info("Initializing Price Manager...")

        # Initialize feeds
        for symbol in ["BTC", "ETH", "SOL", "XRP"]:
            self.oracle_feeds[symbol] = PriceFeed(symbol=symbol)
            self.polymarket_feeds[symbol] = PriceFeed(symbol=symbol)

        # Initialize scraper
        if self.use_scraper:
            try:
                self.scraper = ChainlinkPriceScraper(headless=True)
                await self.scraper.initialize()
                self.scraper.add_callback(self._on_scraped_prices)
                logger.info("Chainlink scraper initialized")
            except Exception as e:
                logger.error(f"Failed to initialize scraper: {e}")
                self.scraper = None

        # Initialize on-chain reader
        if self.use_onchain:
            try:
                self.onchain_reader = ChainlinkOnChainReader()
                await self.onchain_reader.initialize()
                logger.info("On-chain reader initialized")
            except Exception as e:
                logger.error(f"Failed to initialize on-chain reader: {e}")
                self.onchain_reader = None

        logger.info("Price Manager initialized")

    async def close(self) -> None:
        """Close all price sources."""
        self._running = False

        if self.scraper:
            await self.scraper.close()

        logger.info("Price Manager closed")

    def add_price_callback(self, callback: Callable) -> None:
        """Add callback for price updates."""
        self._price_callbacks.append(callback)

    def add_lag_callback(self, callback: Callable) -> None:
        """Add callback for lag detection."""
        self._lag_callbacks.append(callback)

    async def _on_scraped_prices(self, prices: Dict[str, PriceData]) -> None:
        """Handle new scraped prices."""
        for symbol, price_data in prices.items():
            self.oracle_feeds[symbol].update(price_data)

            # Notify price callbacks
            for callback in self._price_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(symbol, price_data)
                    else:
                        callback(symbol, price_data)
                except Exception as e:
                    logger.error(f"Price callback error: {e}")

            # Check for lag opportunities
            await self._check_lag(symbol)

    async def _check_lag(self, symbol: str) -> None:
        """Check for lag between oracle and Polymarket prices."""
        oracle_feed = self.oracle_feeds.get(symbol)
        polymarket_feed = self.polymarket_feeds.get(symbol)

        if not oracle_feed or not oracle_feed.current_price:
            return
        if not polymarket_feed or not polymarket_feed.current_price:
            return

        oracle_price = oracle_feed.current_price
        pm_price = polymarket_feed.current_price

        # Calculate lag
        lag_seconds = (oracle_price.timestamp - pm_price.timestamp).total_seconds()
        price_diff_pct = ((oracle_price.price - pm_price.price) / pm_price.price) * 100

        lag = PriceLag(
            symbol=symbol,
            oracle_price=oracle_price.price,
            polymarket_price=pm_price.price,
            oracle_timestamp=oracle_price.timestamp,
            polymarket_timestamp=pm_price.timestamp,
            lag_seconds=abs(lag_seconds),
            price_difference_pct=price_diff_pct
        )

        # Notify lag callbacks if opportunity detected
        if lag.is_profitable:
            logger.info(f"Profitable lag detected for {symbol}: {lag.price_difference_pct:.2f}% diff, {lag.lag_seconds:.1f}s lag")

            for callback in self._lag_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(lag)
                    else:
                        callback(lag)
                except Exception as e:
                    logger.error(f"Lag callback error: {e}")

    def update_polymarket_price(self, symbol: str, price: float, timestamp: datetime) -> None:
        """
        Update Polymarket implied price.

        Args:
            symbol: Cryptocurrency symbol
            price: Implied price from market odds
            timestamp: Time of price observation
        """
        if symbol not in self.polymarket_feeds:
            self.polymarket_feeds[symbol] = PriceFeed(symbol=symbol)

        price_data = PriceData(
            symbol=symbol,
            price=price,
            timestamp=timestamp,
            source=PriceSource.POLYMARKET,
            confidence=0.9
        )
        self.polymarket_feeds[symbol].update(price_data)

    def get_oracle_price(self, symbol: str) -> Optional[PriceData]:
        """Get the current oracle price for a symbol."""
        feed = self.oracle_feeds.get(symbol)
        return feed.current_price if feed else None

    def get_polymarket_price(self, symbol: str) -> Optional[PriceData]:
        """Get the current Polymarket implied price for a symbol."""
        feed = self.polymarket_feeds.get(symbol)
        return feed.current_price if feed else None

    def get_all_oracle_prices(self) -> Dict[str, PriceData]:
        """Get all current oracle prices."""
        return {
            symbol: feed.current_price
            for symbol, feed in self.oracle_feeds.items()
            if feed.current_price
        }

    def get_price_lag(self, symbol: str) -> Optional[PriceLag]:
        """
        Get the current price lag for a symbol.

        Returns:
            PriceLag object or None
        """
        oracle = self.get_oracle_price(symbol)
        polymarket = self.get_polymarket_price(symbol)

        if not oracle or not polymarket:
            return None

        lag_seconds = (oracle.timestamp - polymarket.timestamp).total_seconds()
        price_diff_pct = ((oracle.price - polymarket.price) / polymarket.price) * 100

        return PriceLag(
            symbol=symbol,
            oracle_price=oracle.price,
            polymarket_price=polymarket.price,
            oracle_timestamp=oracle.timestamp,
            polymarket_timestamp=polymarket.timestamp,
            lag_seconds=abs(lag_seconds),
            price_difference_pct=price_diff_pct
        )

    async def start(self, scrape_interval: float = 1.0) -> None:
        """
        Start price monitoring.

        Args:
            scrape_interval: Interval between scrapes in seconds
        """
        self._running = True

        if self.scraper:
            asyncio.create_task(
                self.scraper.start_continuous_scraping(scrape_interval)
            )

        logger.info("Price monitoring started")

    def stop(self) -> None:
        """Stop price monitoring."""
        self._running = False

        if self.scraper:
            self.scraper.stop()

        logger.info("Price monitoring stopped")

    async def get_backup_prices(self) -> Dict[str, PriceData]:
        """Get prices from on-chain reader (backup)."""
        if not self.onchain_reader:
            return {}

        return await self.onchain_reader.get_all_prices()

    def get_feed_status(self) -> Dict:
        """Get status of all price feeds."""
        status = {
            "oracle_feeds": {},
            "polymarket_feeds": {},
            "scraper_active": self.scraper is not None and self.scraper._running if self.scraper else False,
            "onchain_active": self.onchain_reader is not None
        }

        for symbol in ["BTC", "ETH", "SOL", "XRP"]:
            oracle_feed = self.oracle_feeds.get(symbol)
            pm_feed = self.polymarket_feeds.get(symbol)

            status["oracle_feeds"][symbol] = {
                "has_price": oracle_feed.current_price is not None if oracle_feed else False,
                "price": oracle_feed.current_price.price if oracle_feed and oracle_feed.current_price else None,
                "age_seconds": oracle_feed.current_price.age_seconds if oracle_feed and oracle_feed.current_price else None,
                "history_count": len(oracle_feed.price_history) if oracle_feed else 0
            }

            status["polymarket_feeds"][symbol] = {
                "has_price": pm_feed.current_price is not None if pm_feed else False,
                "price": pm_feed.current_price.price if pm_feed and pm_feed.current_price else None,
                "age_seconds": pm_feed.current_price.age_seconds if pm_feed and pm_feed.current_price else None,
                "history_count": len(pm_feed.price_history) if pm_feed else 0
            }

        return status
