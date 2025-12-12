"""
Market Monitor - Continuous monitoring of Polymarket crypto markets.
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional, List, Callable
from loguru import logger

from .client import PolymarketClient
from .models import Market, MarketType, OrderBook


class MarketMonitor:
    """
    Monitors Polymarket crypto prediction markets for trading opportunities.

    Features:
    - Continuous order book monitoring
    - Price change detection
    - Implied price calculation from market odds
    - Integration with price feeds for lag detection
    """

    def __init__(self, client: PolymarketClient):
        """
        Initialize the market monitor.

        Args:
            client: PolymarketClient instance
        """
        self.client = client

        # Monitored markets by symbol
        self.active_markets: Dict[str, List[Market]] = {
            "BTC": [], "ETH": [], "SOL": [], "XRP": []
        }

        # Order book cache
        self.order_books: Dict[str, OrderBook] = {}

        # Callbacks
        self._market_callbacks: List[Callable] = []
        self._orderbook_callbacks: List[Callable] = []

        # State
        self._running = False
        self._last_refresh = None

    async def initialize(self) -> None:
        """Initialize the monitor and fetch initial market data."""
        logger.info("Initializing Market Monitor...")

        await self._refresh_markets()

        logger.info("Market Monitor initialized")

    async def _refresh_markets(self) -> None:
        """Refresh the list of active crypto markets."""
        logger.info("Refreshing crypto markets...")

        try:
            crypto_markets = await self.client.fetch_crypto_markets()

            for symbol, markets in crypto_markets.items():
                # Filter for active, liquid markets
                filtered = [
                    m for m in markets
                    if m.is_active and m.liquidity > 100
                ]
                # Sort by liquidity
                filtered.sort(key=lambda x: x.liquidity, reverse=True)
                self.active_markets[symbol] = filtered[:10]  # Top 10 per symbol

                logger.info(f"Monitoring {len(filtered)} {symbol} markets")

            self._last_refresh = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error refreshing markets: {e}")

    def add_market_callback(self, callback: Callable) -> None:
        """Add callback for market updates."""
        self._market_callbacks.append(callback)

    def add_orderbook_callback(self, callback: Callable) -> None:
        """Add callback for order book updates."""
        self._orderbook_callbacks.append(callback)

    async def _update_order_books(self) -> None:
        """Update order books for all monitored markets."""
        for symbol, markets in self.active_markets.items():
            for market in markets:
                try:
                    updated_market = await self.client.fetch_market_order_books(market)

                    # Cache order books
                    for outcome in updated_market.outcomes:
                        if outcome.order_book:
                            self.order_books[outcome.token_id] = outcome.order_book

                    # Notify callbacks
                    for callback in self._orderbook_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(updated_market)
                            else:
                                callback(updated_market)
                        except Exception as e:
                            logger.error(f"Order book callback error: {e}")

                except Exception as e:
                    logger.error(f"Error updating order book for {market.market_id}: {e}")

    async def _notify_market_update(self, market: Market) -> None:
        """Notify callbacks of market update."""
        for callback in self._market_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(market)
                else:
                    callback(market)
            except Exception as e:
                logger.error(f"Market callback error: {e}")

    async def start(
        self,
        orderbook_interval: float = 2.0,
        market_refresh_interval: float = 300.0
    ) -> None:
        """
        Start continuous market monitoring.

        Args:
            orderbook_interval: Seconds between order book updates
            market_refresh_interval: Seconds between market list refreshes
        """
        self._running = True
        refresh_counter = 0
        refresh_cycles = int(market_refresh_interval / orderbook_interval)

        logger.info(f"Starting market monitor (order books: {orderbook_interval}s, markets: {market_refresh_interval}s)")

        while self._running:
            try:
                # Update order books
                await self._update_order_books()

                # Refresh markets periodically
                refresh_counter += 1
                if refresh_counter >= refresh_cycles:
                    await self._refresh_markets()
                    refresh_counter = 0

                await asyncio.sleep(orderbook_interval)

            except Exception as e:
                logger.error(f"Error in market monitor: {e}")
                await asyncio.sleep(5)

    def stop(self) -> None:
        """Stop market monitoring."""
        self._running = False
        logger.info("Market monitor stopped")

    def get_market(self, symbol: str, market_type: MarketType = None) -> Optional[Market]:
        """
        Get the best market for a symbol.

        Args:
            symbol: Crypto symbol (BTC, ETH, SOL, XRP)
            market_type: Optional filter by market type

        Returns:
            Best market or None
        """
        markets = self.active_markets.get(symbol, [])

        if market_type:
            markets = [m for m in markets if m.market_type == market_type]

        if not markets:
            return None

        # Return highest liquidity market
        return max(markets, key=lambda m: m.liquidity)

    def get_15m_market(self, symbol: str) -> Optional[Market]:
        """Get the best 15-minute market for a symbol."""
        return self.get_market(symbol, MarketType.CRYPTO_PRICE_15M)

    def get_implied_price(self, symbol: str) -> Optional[float]:
        """
        Get the implied price from market odds.

        Args:
            symbol: Crypto symbol

        Returns:
            Implied price or None
        """
        market = self.get_market(symbol)
        if not market:
            return None

        return market.get_implied_price()

    def get_best_bid_ask(self, symbol: str) -> Optional[Dict]:
        """
        Get best bid/ask for a symbol's primary market.

        Returns:
            Dict with bid, ask, mid, spread info
        """
        market = self.get_market(symbol)
        if not market:
            return None

        yes_outcome = market.get_yes_outcome()
        if not yes_outcome or not yes_outcome.order_book:
            return None

        ob = yes_outcome.order_book
        return {
            "symbol": symbol,
            "market_id": market.market_id,
            "best_bid": ob.best_bid.price if ob.best_bid else None,
            "best_ask": ob.best_ask.price if ob.best_ask else None,
            "mid_price": ob.mid_price,
            "spread": ob.spread,
            "spread_pct": ob.spread_pct,
            "bid_liquidity": ob.get_total_bid_liquidity(5),
            "ask_liquidity": ob.get_total_ask_liquidity(5),
            "timestamp": ob.timestamp
        }

    def get_all_market_status(self) -> Dict:
        """Get status of all monitored markets."""
        status = {}

        for symbol, markets in self.active_markets.items():
            status[symbol] = {
                "market_count": len(markets),
                "total_volume": sum(m.volume for m in markets),
                "total_liquidity": sum(m.liquidity for m in markets),
                "markets": [
                    {
                        "question": m.question[:50] + "..." if len(m.question) > 50 else m.question,
                        "type": m.market_type.value,
                        "volume": m.volume,
                        "liquidity": m.liquidity,
                        "implied_price": m.get_implied_price()
                    }
                    for m in markets[:3]  # Top 3
                ]
            }

        return status

    def get_orderbook_age(self, token_id: str) -> Optional[float]:
        """Get the age of cached order book in seconds."""
        ob = self.order_books.get(token_id)
        if not ob:
            return None
        return (datetime.utcnow() - ob.timestamp).total_seconds()
