"""
Chainlink price feed scraper using Selenium for real-time price data.
Scrapes prices from data.chain.link website.
"""

import asyncio
import re
from datetime import datetime
from typing import Dict, Optional, List
from loguru import logger

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from .models import PriceData, PriceSource


class ChainlinkPriceScraper:
    """
    Scrapes real-time price data from Chainlink data streams website.

    This scraper monitors:
    - BTC/USD: https://data.chain.link/streams/btc-usd-cexprice-streams
    - ETH/USD: https://data.chain.link/streams/eth-usd-cexprice-streams
    - SOL/USD: https://data.chain.link/streams/sol-usd-cexprice-streams
    - XRP/USD: https://data.chain.link/streams/xrp-usd-cexprice-streams
    """

    FEED_URLS = {
        "BTC": "https://data.chain.link/streams/btc-usd-cexprice-streams",
        "ETH": "https://data.chain.link/streams/eth-usd-cexprice-streams",
        "SOL": "https://data.chain.link/streams/sol-usd-cexprice-streams",
        "XRP": "https://data.chain.link/streams/xrp-usd-cexprice-streams"
    }

    def __init__(self, headless: bool = True):
        """
        Initialize the scraper.

        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self.drivers: Dict[str, webdriver.Chrome] = {}
        self.last_prices: Dict[str, PriceData] = {}
        self._running = False
        self._callbacks: List[callable] = []

    def _create_driver(self) -> webdriver.Chrome:
        """Create a Chrome WebDriver instance."""
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # Suppress logging
        options.add_argument("--log-level=3")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)

        return driver

    async def initialize(self) -> None:
        """Initialize browser instances for each price feed."""
        logger.info("Initializing Chainlink price scrapers...")

        for symbol, url in self.FEED_URLS.items():
            try:
                driver = self._create_driver()
                driver.get(url)
                await asyncio.sleep(3)  # Wait for page to load
                self.drivers[symbol] = driver
                logger.info(f"Initialized scraper for {symbol}")
            except Exception as e:
                logger.error(f"Failed to initialize scraper for {symbol}: {e}")

    async def close(self) -> None:
        """Close all browser instances."""
        self._running = False
        for symbol, driver in self.drivers.items():
            try:
                driver.quit()
                logger.info(f"Closed scraper for {symbol}")
            except Exception as e:
                logger.error(f"Error closing scraper for {symbol}: {e}")
        self.drivers.clear()

    def add_callback(self, callback: callable) -> None:
        """Add a callback to be called when new price data is available."""
        self._callbacks.append(callback)

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from text, handling various formats."""
        if not price_text:
            return None

        # Remove currency symbols and commas
        cleaned = re.sub(r'[$,\s]', '', price_text)

        try:
            return float(cleaned)
        except ValueError:
            logger.warning(f"Could not parse price: {price_text}")
            return None

    async def scrape_price(self, symbol: str) -> Optional[PriceData]:
        """
        Scrape the current price for a symbol.

        Args:
            symbol: The cryptocurrency symbol (BTC, ETH, SOL, XRP)

        Returns:
            PriceData object or None if scraping failed
        """
        if symbol not in self.drivers:
            logger.error(f"No driver initialized for {symbol}")
            return None

        driver = self.drivers[symbol]

        try:
            # Try multiple selectors to find the price
            selectors = [
                # Main price display
                "[data-testid='price-value']",
                ".price-value",
                ".stream-price",
                "h1[class*='price']",
                "span[class*='price']",
                "div[class*='price'] span",
                # Generic large text that might be price
                "h1", "h2",
                # Data streams specific
                "[class*='StreamPrice']",
                "[class*='current-price']"
            ]

            price_text = None
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        # Check if text looks like a price
                        if text and re.match(r'^\$?[\d,]+\.?\d*$', text.replace(',', '').replace('$', '')):
                            price_text = text
                            break
                    if price_text:
                        break
                except:
                    continue

            # Try JavaScript extraction as fallback
            if not price_text:
                try:
                    price_text = driver.execute_script("""
                        // Try to find price in page
                        const pricePatterns = [
                            /\$[\d,]+\.?\d*/,
                            /[\d,]+\.?\d*\s*USD/i
                        ];
                        const bodyText = document.body.innerText;
                        for (const pattern of pricePatterns) {
                            const match = bodyText.match(pattern);
                            if (match) return match[0];
                        }
                        return null;
                    """)
                except:
                    pass

            if price_text:
                price = self._parse_price(price_text)
                if price:
                    price_data = PriceData(
                        symbol=symbol,
                        price=price,
                        timestamp=datetime.utcnow(),
                        source=PriceSource.CHAINLINK_SCRAPE,
                        confidence=0.95
                    )
                    self.last_prices[symbol] = price_data
                    return price_data

            logger.warning(f"Could not find price for {symbol}")
            return None

        except Exception as e:
            logger.error(f"Error scraping price for {symbol}: {e}")
            return None

    async def scrape_all_prices(self) -> Dict[str, PriceData]:
        """Scrape prices for all symbols."""
        results = {}

        tasks = [self.scrape_price(symbol) for symbol in self.FEED_URLS.keys()]
        prices = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, price in zip(self.FEED_URLS.keys(), prices):
            if isinstance(price, PriceData):
                results[symbol] = price
            elif isinstance(price, Exception):
                logger.error(f"Error scraping {symbol}: {price}")

        return results

    async def refresh_pages(self) -> None:
        """Refresh all browser pages to get fresh data."""
        for symbol, driver in self.drivers.items():
            try:
                driver.refresh()
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error refreshing page for {symbol}: {e}")

    async def start_continuous_scraping(self, interval_seconds: float = 1.0) -> None:
        """
        Start continuous price scraping.

        Args:
            interval_seconds: Time between scrapes
        """
        self._running = True
        refresh_counter = 0

        logger.info(f"Starting continuous scraping with {interval_seconds}s interval")

        while self._running:
            try:
                prices = await self.scrape_all_prices()

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(prices)
                        else:
                            callback(prices)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

                # Refresh pages periodically (every 60 scrapes)
                refresh_counter += 1
                if refresh_counter >= 60:
                    await self.refresh_pages()
                    refresh_counter = 0

                await asyncio.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Error in continuous scraping: {e}")
                await asyncio.sleep(5)  # Wait longer on error

    def stop(self) -> None:
        """Stop continuous scraping."""
        self._running = False

    def get_last_price(self, symbol: str) -> Optional[PriceData]:
        """Get the last scraped price for a symbol."""
        return self.last_prices.get(symbol)

    def get_all_last_prices(self) -> Dict[str, PriceData]:
        """Get all last scraped prices."""
        return self.last_prices.copy()


class ChainlinkOnChainReader:
    """
    Alternative: Read Chainlink prices directly from blockchain.
    This is a backup option if scraping fails.
    """

    # Chainlink Price Feed Addresses on Polygon
    PRICE_FEEDS = {
        "BTC": "0xc907E116054Ad103354f2D350FD2514433D57F6f",  # BTC/USD on Polygon
        "ETH": "0xF9680D99D6C9589e2a93a78A04A279e509205945",  # ETH/USD on Polygon
        "SOL": "0x10C8264C0935b3B9870013e057f330Ff3e9C56dC",  # SOL/USD on Polygon
        "XRP": "0x785ba89291f676b5386652eB12b30cF361020694"   # XRP/USD on Polygon
    }

    # ABI for Chainlink Price Feed
    PRICE_FEED_ABI = [
        {
            "inputs": [],
            "name": "latestRoundData",
            "outputs": [
                {"name": "roundId", "type": "uint80"},
                {"name": "answer", "type": "int256"},
                {"name": "startedAt", "type": "uint256"},
                {"name": "updatedAt", "type": "uint256"},
                {"name": "answeredInRound", "type": "uint80"}
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]

    def __init__(self, rpc_url: str = "https://polygon-rpc.com"):
        """
        Initialize the on-chain reader.

        Args:
            rpc_url: Polygon RPC URL
        """
        self.rpc_url = rpc_url
        self.web3 = None
        self.contracts: Dict[str, any] = {}

    async def initialize(self) -> None:
        """Initialize Web3 connection and contracts."""
        from web3 import Web3

        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))

        if not self.web3.is_connected():
            raise ConnectionError(f"Failed to connect to {self.rpc_url}")

        logger.info(f"Connected to Polygon: {self.rpc_url}")

        # Initialize contracts
        for symbol, address in self.PRICE_FEEDS.items():
            self.contracts[symbol] = self.web3.eth.contract(
                address=Web3.to_checksum_address(address),
                abi=self.PRICE_FEED_ABI
            )
            logger.info(f"Initialized price feed contract for {symbol}")

    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """
        Get the current price from on-chain feed.

        Args:
            symbol: The cryptocurrency symbol

        Returns:
            PriceData object or None
        """
        if symbol not in self.contracts:
            logger.error(f"No contract for {symbol}")
            return None

        try:
            contract = self.contracts[symbol]

            # Get decimals
            decimals = contract.functions.decimals().call()

            # Get latest price data
            round_data = contract.functions.latestRoundData().call()
            _, answer, _, updated_at, _ = round_data

            price = answer / (10 ** decimals)
            timestamp = datetime.utcfromtimestamp(updated_at)

            return PriceData(
                symbol=symbol,
                price=price,
                timestamp=timestamp,
                source=PriceSource.CHAINLINK_ONCHAIN,
                confidence=1.0
            )

        except Exception as e:
            logger.error(f"Error getting on-chain price for {symbol}: {e}")
            return None

    async def get_all_prices(self) -> Dict[str, PriceData]:
        """Get prices for all symbols."""
        results = {}

        for symbol in self.PRICE_FEEDS.keys():
            price = await self.get_price(symbol)
            if price:
                results[symbol] = price

        return results
