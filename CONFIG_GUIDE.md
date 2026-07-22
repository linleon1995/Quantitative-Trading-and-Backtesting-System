# Trading Configuration Guide

This document explains the configuration system for the live trading platform.

## Architecture Overview

The system follows a clean separation of concerns:

1. **Strategy** (`DynamicBreakoutTrader`): Pure signal generation logic, exchange-agnostic
2. **Trader** (`BinanceTrader`): Exchange-specific API operations
3. **Orchestrator** (`LiveTradingOrchestrator`): Coordinates components, handles logging, tracking, and notifications

## Configuration System

Configuration uses **Pydantic** for type-safe validation and is loaded from environment variables.

### Configuration Structure

#### Strategy Configuration
Controls the trading strategy parameters:

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `STRATEGY_LOOKBACK` | int | 14 | ≥1 | Lookback period for price analysis |
| `STRATEGY_PR_X` | float | 0.8 | 0.0-1.0 | Upper breakout threshold multiplier |
| `STRATEGY_PR_Y` | float | 0.7 | 0.0-1.0 | Lower breakout threshold multiplier |
| `STRATEGY_ATR_PERIOD` | int | 14 | ≥1 | ATR calculation period |
| `STRATEGY_ADX_PERIOD` | int | 14 | ≥1 | ADX calculation period |
| `STRATEGY_MAX_RISK` | float | 0.02 | 0.0-1.0 | Max risk per trade (fraction of capital) |
| `STRATEGY_LEVERAGE` | int | 1 | 1-125 | Trading leverage multiplier |
| `STRATEGY_DRAWBACK` | float | 0.05 | 0.0-1.0 | Drawback percentage for exit condition |
| `STRATEGY_HOLD_MINUTES` | int | 60 | ≥0 | Minimum holding time before exit (minutes) |

#### Trading Configuration
Controls overall trading behavior:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `INITIAL_CAPITAL` | float | 100000 | Starting capital in USDT |
| `MAX_POSITIONS` | int | 1 | Maximum concurrent positions |
| `TRADE_VALUE_USDT` | float | 100 | Target value per trade in USDT |
| `TRADING_FEE_RATE` | float | 0.0004 | Trading fee rate (0.0004 = 0.04%) |
| `MAX_DRAWDOWN` | float | 0.2 | **Critical**: Max allowed drawdown before auto-stop (0.2 = 20%) |
| `USE_TESTNET` | bool | True | Use Binance testnet (True) or production (False) |

**Important**: When `MAX_DRAWDOWN` is reached, the system will:
- Stop all trading operations immediately
- Send critical log messages
- Send Telegram alert
- Refuse to execute new trades

#### Kafka Configuration
Controls Kafka consumer settings:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | string | localhost:29092 | Comma-separated list of Kafka servers |
| `KAFKA_TOPIC` | string | binance_kline | Kafka topic to consume from |

#### Logging Configuration
Controls logging and notification intervals:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `LOG_LEVEL` | string | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FILE` | string | logs/live_trading.log | Path to log file |
| `TELEGRAM_UPDATE_INTERVAL` | int | 600 | Interval for Telegram updates (seconds) - default 10 min |
| `PORTFOLIO_TRACKING_INTERVAL` | int | 300 | Interval for portfolio tracking (seconds) - default 5 min |

## Environment Variables

Create a `.env` file in the project root with your configuration:

```bash
# API Credentials (Required)
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_API_SECRET=your_testnet_api_secret
BINANCE_API_KEY=your_production_api_key
BINANCE_API_SECRET=your_production_api_secret

# Trading Configuration
USE_TESTNET=True
INITIAL_CAPITAL=100000
MAX_POSITIONS=1
TRADE_VALUE_USDT=100
TRADING_FEE_RATE=0.0004
MAX_DRAWDOWN=0.2  # 20% max drawdown - CRITICAL SAFETY PARAMETER

# Strategy Parameters
STRATEGY_LOOKBACK=14
STRATEGY_PR_X=0.8
STRATEGY_PR_Y=0.7
STRATEGY_ATR_PERIOD=14
STRATEGY_ADX_PERIOD=14
STRATEGY_MAX_RISK=0.02
STRATEGY_LEVERAGE=1
STRATEGY_DRAWBACK=0.05
STRATEGY_HOLD_MINUTES=60

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:29092
KAFKA_TOPIC=binance_kline

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/live_trading.log
TELEGRAM_UPDATE_INTERVAL=600  # 10 minutes
PORTFOLIO_TRACKING_INTERVAL=300  # 5 minutes
```

## Trading Fees

The system accounts for trading fees in profit/loss calculations:
- Default fee rate: 0.04% (0.0004)
- Fees applied twice per trade: entry + exit
- Total fee per round trip: 0.08%

You can adjust `TRADING_FEE_RATE` based on your:
- VIP level
- Fee discount (BNB, referral, etc.)
- Maker vs taker orders

Common Binance futures fee rates:
- Regular: 0.0004 (0.04%)
- VIP 1: 0.00036 (0.036%)
- VIP 2: 0.00032 (0.032%)

## Risk Management

### Max Drawdown Protection

The `MAX_DRAWDOWN` parameter is your primary circuit breaker:

- Measures drawdown from peak capital
- When exceeded, system immediately:
  - Stops accepting new trades
  - Logs critical alert
  - Sends Telegram emergency notification
  - Keeps existing positions (doesn't force close)

Example:
```
Initial capital: $100,000
Peak capital reached: $120,000
Current capital: $96,000
Drawdown: (120,000 - 96,000) / 120,000 = 20%

If MAX_DRAWDOWN=0.2 → System stops trading
If MAX_DRAWDOWN=0.3 → System continues
```

### Position Sizing

Position size is automatically calculated based on:
- `TRADE_VALUE_USDT`: Target notional value per trade
- Current price: Determines quantity precision
- Fee rate: Factored into P/L calculations

## Monitoring

### Logging

Logs are written to both:
1. **File**: `logs/live_trading.log` (persistent, detailed)
2. **Console**: Real-time monitoring

Log entries include:
- All trade executions (entry/exit)
- Portfolio updates
- Signal generation
- Errors and warnings
- Periodic performance summaries

### Telegram Notifications

Automatic notifications for:
- **Trade Events**: Buy/sell executions with P/L
- **Periodic Updates**: Portfolio status every 10 minutes (configurable)
- **Critical Alerts**: Max drawdown breach, system errors

### Portfolio Tracking

Syncs with exchange every 5 minutes (configurable):
- Current capital
- Return rate
- Drawdown from peak
- Win rate
- Active positions
- Total fees paid

## Example Usage

```python
from src.config.trading_config import load_config_from_env

# Load configuration from environment
config = load_config_from_env()

# Access configuration
print(f"Max Drawdown: {config.trading.max_drawdown}")
print(f"Strategy Lookback: {config.strategy.lookback}")

# Get full summary
print(config.get_summary())
```

## Validation

Pydantic automatically validates:
- Type correctness
- Range constraints
- Required fields

Invalid configuration will raise `ValidationError` at startup with clear error messages.

## Best Practices

1. **Start with conservative settings**:
   - Small `TRADE_VALUE_USDT` (e.g., 100 USDT)
   - Low `MAX_POSITIONS` (e.g., 1-3)
   - Moderate `MAX_DRAWDOWN` (e.g., 0.1-0.2)

2. **Use testnet first**:
   - Set `USE_TESTNET=True`
   - Test all parameters
   - Verify behavior under different market conditions

3. **Monitor regularly**:
   - Check logs for errors
   - Review Telegram updates
   - Analyze portfolio performance

4. **Adjust gradually**:
   - Change one parameter at a time
   - Document changes
   - Monitor impact before further adjustments

## Troubleshooting

### Configuration not loading
- Check `.env` file exists in project root
- Verify environment variable names match exactly
- Check for typos in boolean values (True/False, not true/false)

### Validation errors
- Check parameter ranges in tables above
- Ensure numeric values are within bounds
- Verify types (int vs float)

### Logging not working
- Check `LOG_FILE` path exists or can be created
- Verify write permissions
- Check disk space

### Telegram not sending
- Verify Telegram bot token in `.env`
- Check bot permissions
- Ensure network connectivity
