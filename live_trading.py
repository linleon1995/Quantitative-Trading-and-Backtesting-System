"""
Live trading script that connects to Binance testnet/production
and executes trades based on strategy signals from Kafka stream.

Architecture:
- Strategy: Pure signal generation (exchange-agnostic)
- Trader: Exchange-specific API operations
- Orchestrator: Coordinates all components, handles logging, tracking, notifications
"""
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict
from pathlib import Path

from dotenv import load_dotenv
from kafka import KafkaConsumer

from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader, TradingSignal
from src.trader.binance_trader import BinanceTrader
from src.orchestrator.live_trading_orchestrator import LiveTradingOrchestrator
from src.config.trading_config import load_config_from_env
from src.event import telegram_bot

# Load environment variables
load_dotenv()


def setup_logging(config) -> logging.Logger:
    """Setup logging with file and console handlers."""
    # Ensure log directory exists
    log_file = Path(config.logging.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('live_trading')
    logger.setLevel(getattr(logging, config.logging.log_level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(config.logging.log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


def parse_kafka_message(message_value):
    """Parse Kafka message from bytes to dict."""
    try:
        msg_str = message_value.decode('utf-8')
        data = json.loads(msg_str)
        return data
    except Exception as e:
        logging.error(f"Error parsing message: {e}")
        return None


def run_live_trading():
    """Main function to run live trading with new architecture."""
    
    # Load configuration
    config = load_config_from_env()
    
    # Setup logging
    logger = setup_logging(config)
    logger.info("=" * 80)
    logger.info("Starting Live Trading System")
    logger.info("=" * 80)
    logger.info(config.get_summary())
    
    # Get API credentials
    if config.trading.use_testnet:
        api_key = os.getenv('BINANCE_TESTNET_API_KEY')
        api_secret = os.getenv('BINANCE_TESTNET_API_SECRET')
    else:
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
    
    # Validate API credentials
    if not api_key or not api_secret:
        logger.critical("API credentials not found in environment variables")
        raise ValueError(
            "API credentials not found. Please set BINANCE_TESTNET_API_KEY and "
            "BINANCE_TESTNET_API_SECRET in .env file"
        )
    
    # Initialize Binance trader
    logger.info(f"Initializing BinanceTrader (testnet={config.trading.use_testnet})")
    trader = BinanceTrader(
        api_key=api_key,
        api_secret=api_secret,
        use_testnet=config.trading.use_testnet
    )
    
    # Test connection
    try:
        balance = trader.get_balance(account_type='futures')
        logger.info(f"Connection successful. Account Balance: {balance}")
    except Exception as e:
        logger.critical(f"Failed to connect to Binance: {e}")
        raise
    
    # Initialize orchestrator
    orchestrator = LiveTradingOrchestrator(
        trader=trader,
        config=config,
        logger=logger
    )
    
    # Initialize Kafka consumer
    logger.info(f"Connecting to Kafka: {config.kafka.bootstrap_servers}")
    consumer = KafkaConsumer(
        config.kafka.topic,
        bootstrap_servers=config.kafka.bootstrap_servers,
        auto_offset_reset=config.kafka.auto_offset_reset,
        enable_auto_commit=True,
        value_deserializer=lambda v: v
    )
    logger.info(f"Subscribed to Kafka topic: {config.kafka.topic}")
    
    # Strategy instances per symbol
    strategies: Dict[str, DynamicBreakoutTrader] = {}
    
    # Online backtest reset: close all positions and re-baseline on startup
    if config.trading.reset_on_start:
        logger.info("=" * 80)
        logger.info("🔄 ONLINE BACKTEST MODE: Resetting positions and portfolio...")
        reset_result = orchestrator.reset_for_online_backtest(strategies)
        logger.info(
            f"Reset complete — closed {reset_result['positions_closed']} position(s), "
            f"new baseline: ${reset_result['new_baseline']:,.2f}"
        )
        if reset_result['positions_failed']:
            logger.warning(f"Failed to close: {reset_result['positions_failed']}")
        telegram_bot.send_msg(
            f"🔄 Online Backtest Reset\n"
            f"Closed {reset_result['positions_closed']} position(s)\n"
            f"New Baseline: ${reset_result['new_baseline']:,.2f}"
        )

    logger.info("=" * 80)
    logger.info("🚀 Live Trading Started!")
    logger.info("=" * 80)
    telegram_bot.send_msg(
        f"🚀 Live Trading Started\n"
        f"Environment: {'TESTNET' if config.trading.use_testnet else 'PRODUCTION'}\n"
        f"Initial Capital: ${orchestrator.portfolio.initial_capital:,.2f}\n"
        f"Max Loss Rate: {config.trading.max_loss_rate*100:.0f}%"
    )
    
    try:
        for msg in consumer:
            # Check if trading should stop
            if not orchestrator.is_trading_active:
                logger.warning("Trading is inactive, shutting down...")
                break
            
            # Parse message
            raw_data = parse_kafka_message(msg.value)
            if not raw_data:
                continue

            try:
                timestamp_str = raw_data['timestamp']
                symbol = raw_data['symbol']
                close_price = float(raw_data['close_price'])
                
                # Initialize strategy for new symbols
                if symbol not in strategies:
                    logger.info(f"Initializing strategy for {symbol}")

                    # Create signal handler that binds orchestrator
                    def make_signal_handler(orch, strat):
                        def handler(signal: TradingSignal):
                            orch.handle_signal(signal, strat)
                        return handler

                    # Create strategy instance (on_signal=None during warmup)
                    strategy = DynamicBreakoutTrader(
                        symbol=symbol,
                        lookback=config.strategy.lookback,
                        pr_x=config.strategy.pr_x,
                        pr_y=config.strategy.pr_y,
                        atr_period=config.strategy.atr_period,
                        adx_period=config.strategy.adx_period,
                        max_risk=config.strategy.max_risk,
                        leverage=config.strategy.leverage,
                        drawback=config.strategy.drawback,
                        hold_minutes=config.strategy.hold_minutes,
                        max_positions=config.trading.max_positions,
                        on_signal=None,
                    )

                    # --- B-5 fix: pre-warm indicators with historical klines ---
                    # Fetch enough bars so that self.high is a real rolling high
                    # (not just 1 price) and mean_atr / mean_vol are fully computed.
                    # Need at least lookback + atr_period bars; fetch 3× that for safety.
                    warmup_bars_needed = (
                        config.strategy.lookback + config.strategy.atr_period
                    ) * 3
                    try:
                        hist = trader.get_futures_klines(
                            symbol=symbol,
                            interval='1m',
                            limit=warmup_bars_needed,
                        )
                        if hist:
                            n = strategy.warmup_with_history(hist)
                            warmed = strategy.mean_atr is not None and strategy.mean_vol is not None
                            logger.info(
                                f"[{symbol}] Warmup complete: {n} bars processed, "
                                f"indicators ready={warmed}, "
                                f"high={strategy.high}, mean_atr={strategy.mean_atr}"
                            )
                        else:
                            logger.warning(
                                f"[{symbol}] Could not fetch warmup klines; "
                                "strategy will warm up from live data (first signals may be delayed)"
                            )
                    except Exception as warmup_err:
                        logger.warning(
                            f"[{symbol}] Warmup fetch failed ({warmup_err}); "
                            "continuing without pre-warmup"
                        )

                    # Attach live signal handler AFTER warmup so no premature signals
                    strategy.on_signal = make_signal_handler(orchestrator, strategy)
                    strategies[symbol] = strategy
                
                # Process tick
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                strategies[symbol].on_tick(timestamp, raw_data)
                
                # Periodic updates (portfolio tracking and Telegram)
                orchestrator.periodic_update()
                
            except KeyError as e:
                logger.warning(f"Incomplete data in message: {raw_data}, error: {e}")
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down gracefully...")
    except Exception as e:
        logger.critical(f"Fatal error in main loop: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info("Closing Kafka consumer...")
        consumer.close()
        
        # Final portfolio summary
        logger.info("=" * 80)
        logger.info("Final Portfolio Summary")
        logger.info("=" * 80)
        logger.info(orchestrator.portfolio.get_summary())
        
        telegram_bot.send_msg(
            f"🛑 Trading Stopped\n"
            f"{orchestrator.portfolio.get_summary()}"
        )
        
        logger.info("Live trading system shutdown complete")


if __name__ == "__main__":
    run_live_trading()
