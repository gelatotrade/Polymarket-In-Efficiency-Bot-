# Polymarket In-Efficiency Bot

A sophisticated trading bot that exploits the 10-20 second lag between real-time Chainlink oracle price feeds and Polymarket's CLOB (Central Limit Order Book) updates for crypto prediction markets.

## Overview

This bot monitors real-time cryptocurrency prices from Chainlink oracles (BTC, ETH, SOL, XRP) and compares them to Polymarket's 15-minute crypto prediction markets. When the oracle price moves significantly before the Polymarket order book adjusts, the bot identifies profitable trading opportunities.

### How It Works

1. **Price Monitoring**: Continuously scrapes real-time prices from [Chainlink Data Streams](https://data.chain.link/streams/)
2. **Market Monitoring**: Monitors Polymarket crypto prediction markets via the [CLOB API](https://docs.polymarket.com/)
3. **Lag Detection**: Identifies when oracle prices move but market probabilities haven't adjusted
4. **Signal Generation**: Generates trading signals when profitable opportunities are detected
5. **Trade Execution**: Automatically executes trades when enabled (with risk management)
6. **Telegram Dashboard**: Real-time monitoring and control via Telegram bot

## Features

- **Multi-Asset Support**: BTC, ETH, SOL, XRP price tracking
- **Real-time Price Feeds**: Chainlink oracle scraping + on-chain backup
- **Market Analysis**: Polymarket CLOB monitoring and order book analysis
- **Lag Strategy**: Sophisticated algorithm to detect and exploit price lag
- **Risk Management**: Position limits, stop-loss, daily loss limits, cooldown periods
- **Telegram Bot**: Full dashboard with real-time updates and trading controls
- **Database Storage**: Historical data for backtesting and analysis
- **Configurable**: Extensive configuration options via environment variables

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Orchestrator                             │
│                    (Coordinates all components)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Price Manager │  │ Market Monitor  │  │ Telegram Bot    │
│               │  │                 │  │                 │
│ - Chainlink   │  │ - Polymarket    │  │ - Dashboard     │
│   Scraper     │  │   CLOB Client   │  │ - Commands      │
│ - On-chain    │  │ - Order Books   │  │ - Alerts        │
│   Reader      │  │ - Market Data   │  │                 │
└───────┬───────┘  └────────┬────────┘  └─────────────────┘
        │                   │
        └─────────┬─────────┘
                  │
                  ▼
        ┌─────────────────┐
        │ Trading Strategy │
        │                 │
        │ - Lag Detection │
        │ - Signal Gen    │
        │ - Risk Manager  │
        │ - Position Mgr  │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │    Database     │
        │                 │
        │ - Prices        │
        │ - Signals       │
        │ - Trades        │
        │ - Positions     │
        └─────────────────┘
```

## Installation

### Prerequisites

- Python 3.9+
- Chrome/Chromium (for Selenium web scraping)
- Polymarket account with funds
- Telegram bot token (from [@BotFather](https://t.me/botfather))

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/Polymarket-In-Efficiency-Bot-.git
cd Polymarket-In-Efficiency-Bot-
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp config/.env.example .env
# Edit .env with your settings
```

5. **Create data directories**
```bash
mkdir -p data logs
```

## Configuration

Edit `.env` file with your settings:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_ADMIN_IDS=123456789  # Your Telegram user ID

# Polymarket Configuration
POLYMARKET_PRIVATE_KEY=your_polymarket_wallet_private_key
POLYMARKET_FUNDER_ADDRESS=your_polygon_wallet_address
POLYMARKET_SIGNATURE_TYPE=1  # 1 for email wallets

# Trading Configuration
TRADING_ENABLED=false  # Set to true to enable live trading
MAX_POSITION_SIZE_USD=100
MIN_PROFIT_THRESHOLD_PCT=0.5
LAG_THRESHOLD_SECONDS=10

# Risk Management
MAX_DAILY_LOSS_USD=50
MAX_CONCURRENT_POSITIONS=3
STOP_LOSS_PCT=2.0
```

### Getting Your Polymarket Private Key

1. Go to [Polymarket.com](https://polymarket.com)
2. Log in to your account
3. Click on "Cash" button
4. Click the three dots (...)
5. Select "Export Private Key"
6. Copy the key to your `.env` file

### Getting Your Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the prompts
3. Copy the token to your `.env` file
4. Get your user ID by messaging [@userinfobot](https://t.me/userinfobot)

## Usage

### Running the Bot

```bash
# Run full bot (monitoring + trading if enabled)
python main.py

# Run in monitor-only mode (no trading)
python main.py --monitor-only

# Enable live trading
python main.py --enable-trading

# Set log level
python main.py --log-level DEBUG
```

### Telegram Commands

Once the bot is running, use these commands in Telegram:

| Command | Description |
|---------|-------------|
| `/start` | Start bot and show welcome message |
| `/help` | Show all available commands |
| `/dashboard` | Show live dashboard with prices, positions, stats |
| `/prices` | Show current oracle and market prices |
| `/positions` | Show open positions |
| `/signals` | Show recent trading signals |
| `/stats` | Show performance statistics |
| `/start_trading` | Enable live trading |
| `/stop_trading` | Disable live trading |
| `/setup` | Configure wallet and API keys |
| `/settings` | View/edit settings |
| `/status` | Show system status |

## Trading Strategy

### Lag Detection Algorithm

The bot identifies opportunities when:

1. **Significant Price Movement**: Oracle price moves significantly (configurable threshold)
2. **Market Hasn't Adjusted**: Polymarket order book still reflects old prices
3. **Sufficient Lag**: Time delay exceeds threshold (default: 10 seconds)
4. **Confidence Score**: Multiple factors combine to create confidence score

### Signal Types

- **BUY_YES**: Oracle price above threshold, market underpricing "Yes"
- **BUY_NO**: Oracle price below threshold, market overpricing "Yes"
- **NO_ACTION**: Insufficient opportunity

### Signal Strength

- **WEAK**: Minor opportunity, not actionable
- **MODERATE**: Consider trading, moderate confidence
- **STRONG**: Good opportunity, higher confidence
- **VERY_STRONG**: Excellent opportunity, highest confidence

### Risk Management

- **Position Sizing**: Based on confidence and liquidity
- **Stop Loss**: Automatic exit at configurable loss threshold
- **Daily Loss Limit**: Stop trading if daily loss exceeds limit
- **Cooldown Period**: Pause after losing trades
- **Max Positions**: Limit concurrent open positions

## Data Sources

### Chainlink Price Feeds

The bot scrapes real-time prices from:

- [BTC/USD](https://data.chain.link/streams/btc-usd-cexprice-streams)
- [ETH/USD](https://data.chain.link/streams/eth-usd-cexprice-streams)
- [SOL/USD](https://data.chain.link/streams/sol-usd-cexprice-streams)
- [XRP/USD](https://data.chain.link/streams/xrp-usd-cexprice-streams)

### Polymarket APIs

- **CLOB API**: `https://clob.polymarket.com` - Order book and trading
- **Gamma API**: `https://gamma-api.polymarket.com` - Market metadata

## Project Structure

```
Polymarket-In-Efficiency-Bot-/
├── main.py                 # Entry point
├── requirements.txt        # Python dependencies
├── config/
│   └── .env.example       # Example configuration
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── orchestrator.py    # Main coordinator
│   ├── price_feeds/       # Price feed integrations
│   │   ├── __init__.py
│   │   ├── models.py      # Price data models
│   │   ├── chainlink_scraper.py  # Web scraper
│   │   └── price_manager.py      # Price aggregation
│   ├── polymarket/        # Polymarket integration
│   │   ├── __init__.py
│   │   ├── models.py      # Market models
│   │   ├── client.py      # CLOB client
│   │   └── market_monitor.py  # Market monitoring
│   ├── strategy/          # Trading strategy
│   │   ├── __init__.py
│   │   ├── models.py      # Strategy models
│   │   ├── lag_strategy.py     # Main strategy
│   │   ├── risk_manager.py     # Risk management
│   │   └── position_manager.py # Position tracking
│   ├── telegram_bot/      # Telegram interface
│   │   ├── __init__.py
│   │   ├── bot.py         # Bot implementation
│   │   ├── handlers.py    # Command handlers
│   │   ├── keyboard.py    # Inline keyboards
│   │   └── dashboard.py   # Live dashboard
│   ├── database/          # Data persistence
│   │   ├── __init__.py
│   │   ├── models.py      # SQLAlchemy models
│   │   └── database.py    # Database operations
│   └── utils/             # Utilities
│       ├── __init__.py
│       ├── logger.py      # Logging setup
│       └── helpers.py     # Helper functions
├── data/                  # Database files
├── logs/                  # Log files
└── tests/                 # Test files
```

## API Documentation

### Key Classes

#### `PriceManager`
Central hub for price data aggregation.

```python
from src.price_feeds import PriceManager

manager = PriceManager()
await manager.initialize()

# Get oracle price
price = manager.get_oracle_price("BTC")
print(f"BTC: ${price.price:,.2f}")

# Get lag between oracle and market
lag = manager.get_price_lag("BTC")
if lag.is_profitable:
    print(f"Opportunity! {lag.price_difference_pct:.2f}% diff")
```

#### `PolymarketClient`
Interface for Polymarket CLOB API.

```python
from src.polymarket import PolymarketClient

client = PolymarketClient(
    private_key="0x...",
    funder_address="0x..."
)
await client.initialize()

# Fetch markets
markets = await client.fetch_crypto_markets()

# Place order (if trading enabled)
order = await client.place_market_order(
    token_id="...",
    side=OrderSide.BUY,
    amount_usd=50.0
)
```

#### `LagTradingStrategy`
Main trading strategy implementation.

```python
from src.strategy import LagTradingStrategy

strategy = LagTradingStrategy(
    lag_threshold=10.0,
    price_diff_threshold=0.3,
    max_position_size=100.0
)

# Analyze opportunity
signal = strategy.analyze_lag(
    symbol="BTC",
    oracle_price=oracle_data,
    market=market_data
)

if signal.is_actionable:
    action = strategy.generate_trade_action(signal)
```

## Disclaimer

**USE AT YOUR OWN RISK**

This bot is provided for educational and research purposes only. Trading cryptocurrency prediction markets carries significant risk:

- You may lose some or all of your invested capital
- Past performance does not guarantee future results
- The bot's strategy may not be profitable in all market conditions
- Technical issues may result in missed opportunities or losses

**Never invest more than you can afford to lose.**

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Chainlink](https://chain.link/) for decentralized price feeds
- [Polymarket](https://polymarket.com/) for the prediction market platform
- [py-clob-client](https://github.com/Polymarket/py-clob-client) for the official Python client
- [aiogram](https://github.com/aiogram/aiogram) for the Telegram bot framework

## Support

For issues and feature requests, please use the GitHub Issues page.

---

**Happy Trading!**
