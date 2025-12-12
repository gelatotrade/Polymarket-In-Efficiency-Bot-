"""
Polymarket CLOB client wrapper for market interaction and trading.
"""

import re
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Optional, List, Any
from loguru import logger

from .models import (
    Market, MarketOutcome, MarketType, OrderBook, OrderBookLevel,
    Order, OrderSide, OrderType, OrderStatus, Position, Trade
)


class PolymarketClient:
    """
    Client for interacting with Polymarket CLOB and Gamma APIs.

    Provides functionality for:
    - Fetching market data and order books
    - Placing and managing orders
    - Tracking positions and trades
    """

    CLOB_HOST = "https://clob.polymarket.com"
    GAMMA_HOST = "https://gamma-api.polymarket.com"
    CHAIN_ID = 137  # Polygon

    # Crypto keywords for identifying relevant markets
    CRYPTO_KEYWORDS = {
        "BTC": ["bitcoin", "btc"],
        "ETH": ["ethereum", "eth"],
        "SOL": ["solana", "sol"],
        "XRP": ["xrp", "ripple"]
    }

    def __init__(
        self,
        private_key: Optional[str] = None,
        funder_address: Optional[str] = None,
        signature_type: int = 1
    ):
        """
        Initialize the Polymarket client.

        Args:
            private_key: Wallet private key for trading
            funder_address: Funder address for proxy wallets
            signature_type: Signature type (0=EOA, 1=Email, 2=Browser)
        """
        self.private_key = private_key
        self.funder_address = funder_address
        self.signature_type = signature_type

        self._clob_client = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._initialized = False

        # Cache for markets
        self._markets_cache: Dict[str, Market] = {}
        self._crypto_markets: Dict[str, List[Market]] = {
            "BTC": [], "ETH": [], "SOL": [], "XRP": []
        }

    async def initialize(self) -> None:
        """Initialize the client and API credentials."""
        logger.info("Initializing Polymarket client...")

        # Create aiohttp session for async requests
        self._session = aiohttp.ClientSession()

        # Initialize py-clob-client if credentials provided
        if self.private_key:
            try:
                from py_clob_client.client import ClobClient
                from py_clob_client.clob_types import ApiCreds

                self._clob_client = ClobClient(
                    host=self.CLOB_HOST,
                    key=self.private_key,
                    chain_id=self.CHAIN_ID,
                    signature_type=self.signature_type,
                    funder=self.funder_address
                )

                # Create or derive API credentials
                creds = self._clob_client.create_or_derive_api_creds()
                self._clob_client.set_api_creds(creds)

                logger.info("CLOB client initialized with trading credentials")
            except Exception as e:
                logger.error(f"Failed to initialize CLOB client: {e}")
                self._clob_client = None
        else:
            logger.info("No private key provided - read-only mode")

        self._initialized = True
        logger.info("Polymarket client initialized")

    async def close(self) -> None:
        """Close the client and cleanup resources."""
        if self._session:
            await self._session.close()
        self._initialized = False
        logger.info("Polymarket client closed")

    async def _get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request."""
        if not self._session:
            return None

        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"GET {url} returned {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    # ==================== Market Data ====================

    async def fetch_markets(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Market]:
        """
        Fetch markets from Gamma API.

        Args:
            active_only: Only fetch active markets
            limit: Maximum number of markets
            offset: Pagination offset

        Returns:
            List of Market objects
        """
        url = f"{self.GAMMA_HOST}/markets"
        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active_only).lower()
        }

        data = await self._get(url, params)
        if not data:
            return []

        markets = []
        for item in data:
            try:
                market = self._parse_market(item)
                if market:
                    markets.append(market)
                    self._markets_cache[market.market_id] = market
            except Exception as e:
                logger.warning(f"Error parsing market: {e}")

        return markets

    async def fetch_crypto_markets(self) -> Dict[str, List[Market]]:
        """
        Fetch crypto-related prediction markets.

        Returns:
            Dict mapping crypto symbols to their markets
        """
        logger.info("Fetching crypto markets...")

        # Fetch all active markets
        all_markets = await self.fetch_markets(active_only=True, limit=500)

        # Filter and categorize crypto markets
        self._crypto_markets = {"BTC": [], "ETH": [], "SOL": [], "XRP": []}

        for market in all_markets:
            if market.crypto_symbol:
                self._crypto_markets[market.crypto_symbol].append(market)

        for symbol, markets in self._crypto_markets.items():
            logger.info(f"Found {len(markets)} {symbol} markets")

        return self._crypto_markets

    async def fetch_15m_crypto_markets(self) -> Dict[str, List[Market]]:
        """
        Fetch 15-minute crypto price prediction markets.

        Returns:
            Dict mapping crypto symbols to their 15M markets
        """
        all_crypto = await self.fetch_crypto_markets()

        result = {}
        for symbol, markets in all_crypto.items():
            result[symbol] = [
                m for m in markets
                if m.market_type == MarketType.CRYPTO_PRICE_15M
            ]

        return result

    def _parse_market(self, data: Dict) -> Optional[Market]:
        """Parse market data from API response."""
        try:
            question = data.get("question", "").lower()
            description = data.get("description", "").lower()
            combined_text = f"{question} {description}"

            # Identify crypto symbol
            crypto_symbol = None
            for symbol, keywords in self.CRYPTO_KEYWORDS.items():
                if any(kw in combined_text for kw in keywords):
                    crypto_symbol = symbol
                    break

            # Determine market type
            market_type = MarketType.OTHER
            if crypto_symbol:
                if "15" in question and ("minute" in question or "min" in question):
                    market_type = MarketType.CRYPTO_PRICE_15M
                elif "daily" in question or "today" in question:
                    market_type = MarketType.CRYPTO_PRICE_DAILY
                elif "week" in question:
                    market_type = MarketType.CRYPTO_PRICE_WEEKLY

            # Extract price threshold
            price_threshold = None
            threshold_type = None

            # Look for price patterns like "$100,000" or "100000"
            price_match = re.search(r'\$?([\d,]+)', data.get("question", ""))
            if price_match:
                price_str = price_match.group(1).replace(",", "")
                try:
                    price_threshold = float(price_str)
                except:
                    pass

            if "above" in question:
                threshold_type = "above"
            elif "below" in question:
                threshold_type = "below"
            elif "between" in question:
                threshold_type = "between"

            # Parse outcomes
            outcomes = []
            tokens = data.get("tokens", [])
            for token in tokens:
                outcome = MarketOutcome(
                    outcome_id=token.get("outcome", ""),
                    token_id=token.get("token_id", ""),
                    outcome=token.get("outcome", "Unknown"),
                    price=float(token.get("price", 0))
                )
                outcomes.append(outcome)

            # Parse end date
            end_date = None
            if data.get("end_date_iso"):
                try:
                    end_date = datetime.fromisoformat(
                        data["end_date_iso"].replace("Z", "+00:00")
                    )
                except:
                    pass

            return Market(
                market_id=data.get("id", ""),
                condition_id=data.get("condition_id", ""),
                question=data.get("question", ""),
                description=data.get("description", ""),
                market_type=market_type,
                crypto_symbol=crypto_symbol,
                outcomes=outcomes,
                volume=float(data.get("volume", 0)),
                liquidity=float(data.get("liquidity", 0)),
                end_date=end_date,
                resolution_source=data.get("resolution_source"),
                is_active=data.get("active", True),
                price_threshold=price_threshold,
                threshold_type=threshold_type
            )

        except Exception as e:
            logger.error(f"Error parsing market: {e}")
            return None

    # ==================== Order Book ====================

    async def fetch_order_book(self, token_id: str) -> Optional[OrderBook]:
        """
        Fetch order book for a token.

        Args:
            token_id: The token ID

        Returns:
            OrderBook object or None
        """
        url = f"{self.CLOB_HOST}/book"
        params = {"token_id": token_id}

        data = await self._get(url, params)
        if not data:
            return None

        try:
            bids = [
                OrderBookLevel(price=float(b["price"]), size=float(b["size"]))
                for b in data.get("bids", [])
            ]
            asks = [
                OrderBookLevel(price=float(a["price"]), size=float(a["size"]))
                for a in data.get("asks", [])
            ]

            # Sort: bids descending, asks ascending
            bids.sort(key=lambda x: x.price, reverse=True)
            asks.sort(key=lambda x: x.price)

            return OrderBook(
                token_id=token_id,
                bids=bids,
                asks=asks,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Error parsing order book: {e}")
            return None

    async def fetch_market_order_books(self, market: Market) -> Market:
        """
        Fetch order books for all outcomes of a market.

        Args:
            market: Market object

        Returns:
            Market with updated order books
        """
        for outcome in market.outcomes:
            if outcome.token_id:
                order_book = await self.fetch_order_book(outcome.token_id)
                if order_book:
                    outcome.order_book = order_book

        return market

    # ==================== Trading ====================

    async def place_limit_order(
        self,
        token_id: str,
        side: OrderSide,
        price: float,
        size: float,
        order_type: OrderType = OrderType.GTC
    ) -> Optional[Order]:
        """
        Place a limit order.

        Args:
            token_id: Token to trade
            side: BUY or SELL
            price: Limit price (0-1)
            size: Order size
            order_type: GTC, GTD, or FOK

        Returns:
            Order object or None
        """
        if not self._clob_client:
            logger.error("Trading not enabled - no credentials")
            return None

        try:
            from py_clob_client.clob_types import OrderArgs
            from py_clob_client.constants import BUY, SELL

            clob_side = BUY if side == OrderSide.BUY else SELL

            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=clob_side
            )

            signed_order = self._clob_client.create_order(order_args)
            response = self._clob_client.post_order(signed_order, order_type.value)

            if response and response.get("orderID"):
                return Order(
                    order_id=response["orderID"],
                    market_id="",  # Not returned by API
                    token_id=token_id,
                    side=side,
                    order_type=order_type,
                    price=price,
                    size=size,
                    status=OrderStatus.OPEN
                )
            return None

        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None

    async def place_market_order(
        self,
        token_id: str,
        side: OrderSide,
        amount_usd: float
    ) -> Optional[Order]:
        """
        Place a market order (Fill or Kill).

        Args:
            token_id: Token to trade
            side: BUY or SELL
            amount_usd: Dollar amount to trade

        Returns:
            Order object or None
        """
        if not self._clob_client:
            logger.error("Trading not enabled - no credentials")
            return None

        try:
            from py_clob_client.clob_types import MarketOrderArgs
            from py_clob_client.constants import BUY, SELL

            clob_side = BUY if side == OrderSide.BUY else SELL

            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount_usd,
                side=clob_side
            )

            signed_order = self._clob_client.create_market_order(order_args)
            response = self._clob_client.post_order(signed_order, "FOK")

            if response and response.get("orderID"):
                return Order(
                    order_id=response["orderID"],
                    market_id="",
                    token_id=token_id,
                    side=side,
                    order_type=OrderType.FOK,
                    price=0,  # Market order
                    size=amount_usd,
                    status=OrderStatus.FILLED  # FOK is immediate
                )
            return None

        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully
        """
        if not self._clob_client:
            return False

        try:
            self._clob_client.cancel(order_id)
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    async def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        if not self._clob_client:
            return False

        try:
            self._clob_client.cancel_all()
            return True
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return False

    # ==================== Account Info ====================

    async def get_balance(self) -> Optional[float]:
        """Get USDC balance."""
        if not self._clob_client:
            return None

        try:
            # This requires additional setup for balance queries
            # The CLOB client doesn't directly expose this
            return None
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return None

    async def get_open_orders(self) -> List[Order]:
        """Get all open orders."""
        if not self._clob_client:
            return []

        try:
            response = self._clob_client.get_orders()
            orders = []

            for o in response:
                order = Order(
                    order_id=o.get("id", ""),
                    market_id=o.get("market", ""),
                    token_id=o.get("asset_id", ""),
                    side=OrderSide.BUY if o.get("side") == "BUY" else OrderSide.SELL,
                    order_type=OrderType.GTC,
                    price=float(o.get("price", 0)),
                    size=float(o.get("original_size", 0)),
                    filled_size=float(o.get("size_matched", 0)),
                    status=OrderStatus.OPEN
                )
                orders.append(order)

            return orders
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []

    async def get_trades(self, limit: int = 100) -> List[Trade]:
        """Get recent trades."""
        if not self._clob_client:
            return []

        try:
            response = self._clob_client.get_trades()
            trades = []

            for t in response[:limit]:
                trade = Trade(
                    trade_id=t.get("id", ""),
                    order_id=t.get("order_id", ""),
                    market_id=t.get("market", ""),
                    token_id=t.get("asset_id", ""),
                    side=OrderSide.BUY if t.get("side") == "BUY" else OrderSide.SELL,
                    price=float(t.get("price", 0)),
                    size=float(t.get("size", 0)),
                    fee=float(t.get("fee", 0)),
                    executed_at=datetime.fromisoformat(t.get("created_at", "").replace("Z", "+00:00"))
                )
                trades.append(trade)

            return trades
        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            return []

    # ==================== Utilities ====================

    def get_cached_market(self, market_id: str) -> Optional[Market]:
        """Get a market from cache."""
        return self._markets_cache.get(market_id)

    def get_crypto_markets(self, symbol: str) -> List[Market]:
        """Get cached crypto markets for a symbol."""
        return self._crypto_markets.get(symbol, [])

    @property
    def is_trading_enabled(self) -> bool:
        """Check if trading is enabled."""
        return self._clob_client is not None
