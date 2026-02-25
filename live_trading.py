"""
Live trading script that connects to Binance testnet/production
and executes trades based on strategy signals from Kafka stream.
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional

from dotenv import load_dotenv
from kafka import KafkaConsumer

from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader
from src.trader.binance_trader import BinanceTrader
from src.event import telegram_bot

# Load environment variables
load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = ['localhost:29092']
KAFKA_TOPIC = 'binance_kline'

# Trading configuration
USE_TESTNET = os.getenv('USE_TESTNET', 'True').lower() == 'true'
INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', '100000'))
MAX_POSITIONS = int(os.getenv('MAX_POSITIONS', '1'))
LEVERAGE = int(os.getenv('LEVERAGE', '1'))

# API credentials
if USE_TESTNET:
    API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
    API_SECRET = os.getenv('BINANCE_TESTNET_API_SECRET')
else:
    API_KEY = os.getenv('BINANCE_API_KEY')
    API_SECRET = os.getenv('BINANCE_API_SECRET')

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/live_trading.log"),
        logging.StreamHandler()
    ]
)


class LiveTradingStrategy(DynamicBreakoutTrader):
    """Extended strategy class that executes real trades via BinanceTrader."""
    
    def __init__(self, symbol: str, trader: BinanceTrader, **kwargs):
        # Extract max_positions before passing to parent
        max_positions = kwargs.pop('max_positions', 1)
        
        super().__init__(symbol=symbol, **kwargs)
        self.trader = trader
        self.active_orders: Dict[str, Dict] = {}  # Track active exchange orders
        
        # Set max_positions after initialization
        self.max_positions = max_positions
        
    def _execute_buy(self, timestamp, price, position_size):
        """Execute real buy order on Binance testnet."""
        try:
            logging.info(f"[{self.symbol}] Attempting to BUY {position_size} at market price ~{price}")
            
            # For futures market order
            result = self.trader.open_futures_position(
                symbol=self.symbol,
                side='BUY',
                quantity=position_size,
                order_type='MARKET'
            )
            
            if result.get('success'):
                order_data = result['data']
                order_id = order_data.get('orderId')
                executed_qty = float(order_data.get('executedQty', position_size))
                executed_price = float(order_data.get('avgPrice', price))
                
                # Calculate trade value in USDT
                trade_value = executed_qty * executed_price
                
                logging.info("=" * 80)
                logging.info(f"📈 LONG POSITION OPENED - {self.symbol}")
                logging.info(f"   Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                logging.info(f"   Order ID: {order_id}")
                logging.info(f"   Entry Price: ${executed_price:,.2f}")
                logging.info(f"   Quantity: {executed_qty} BTC")
                logging.info(f"   Trade Value: ${trade_value:,.2f}")
                logging.info(f"   Strategy Signal: Breakout (Price >= Dynamic High)")
                logging.info("=" * 80)
                
                # Create position record
                position = {
                    'entry': executed_price,
                    'size': executed_qty,
                    'entry_time': timestamp,
                    'order_id': order_id,
                    'trade_value': trade_value
                }
                self.positions.append(position)
                self.active_orders[str(order_id)] = order_data
                
                # Send notification
                telegram_bot.send_msg(f"🟢 BUY {self.symbol}\nQty: {executed_qty}\nPrice: ${executed_price:,.2f}\nValue: ${trade_value:,.2f}")
                
                return position
            else:
                logging.error(f"[{self.symbol}] BUY ORDER FAILED: {result.get('message')}")
                return None
                
        except Exception as e:
            logging.error(f"[{self.symbol}] Exception in _execute_buy: {e}")
            return None
    
    def _execute_sell(self, timestamp, position, exit_price, reason):
        """Execute real sell order to close position on Binance testnet."""
        try:
            logging.info(f"[{self.symbol}] Attempting to SELL {position['size']} at market price ~{exit_price}, Reason: {reason}")
            
            # For futures, close position with opposite side
            result = self.trader.close_futures_position(
                symbol=self.symbol,
                side='SELL',
                quantity=position['size'],
                order_type='MARKET'
            )
            
            if result.get('success'):
                order_data = result['data']
                order_id = order_data.get('orderId')
                executed_qty = float(order_data.get('executedQty', position['size']))
                executed_price = float(order_data.get('avgPrice', exit_price))
                
                earn = (executed_price - position['entry']) / position['entry'] * executed_qty
                earn_pct = earn * 100
                
                # Calculate additional metrics
                holding_time = (timestamp - position['entry_time']).total_seconds() / 60  # minutes
                entry_value = position['size'] * position['entry']
                exit_value = executed_qty * executed_price
                pnl_usdt = exit_value - entry_value
                
                logging.info("=" * 80)
                logging.info(f"📉 POSITION CLOSED - {self.symbol}")
                logging.info(f"   Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                logging.info(f"   Order ID: {order_id}")
                logging.info(f"   Exit Reason: {reason}")
                logging.info(f"   Entry Price: ${position['entry']:,.2f} (at {position['entry_time'].strftime('%H:%M:%S')})")
                logging.info(f"   Exit Price: ${executed_price:,.2f}")
                logging.info(f"   Quantity: {executed_qty} BTC")
                logging.info(f"   Holding Time: {holding_time:.1f} minutes")
                logging.info(f"   P&L: {earn_pct:+.2f}% (${pnl_usdt:+,.2f})")
                logging.info(f"   Total Trades: {self.num_trade + 1}")
                logging.info(f"   Average Return: {(self.total_earn + earn) / (self.num_trade + 1) * 100:.2f}%")
                logging.info("=" * 80)
                
                # Record trade
                self.trade_records.append({
                    'earn': earn,
                    'entry': position['entry'],
                    'exit': executed_price,
                    'size': executed_qty,
                    'entry_time': position['entry_time'],
                    'exit_time': timestamp,
                    'reason': reason,
                    'holding_time': holding_time,
                    'pnl_usdt': pnl_usdt,
                    'pnl_pct': earn_pct
                })
                
                self.num_trade += 1
                self.total_earn += earn
                self.avg_earn = self.total_earn / self.num_trade if self.num_trade else 0.0
                
                # Remove position
                self.positions.remove(position)
                self.active_orders[str(order_id)] = order_data
                
                # Send notification
                telegram_bot.send_msg(f"🔴 SELL {self.symbol}\nQty: {executed_qty}\nPrice: ${executed_price:,.2f}\nP&L: {earn_pct:+.2f}% (${pnl_usdt:+.2f})\nHolding: {holding_time:.1f}min")
                
                return True
            else:
                logging.error(f"[{self.symbol}] SELL ORDER FAILED: {result.get('message')}")
                return False
                
        except Exception as e:
            logging.error(f"[{self.symbol}] Exception in _execute_sell: {e}")
            return False
    
    def on_tick(self, timestamp, data):
        """Override to execute real trades instead of simulated ones."""
        price = float(data['close_price'])
        volume = float(data['volume'])

        self.prices.append(price)

        # Update indicators
        if self.high is None:
            self.high = max(self.prices)
        if self.low is None:
            self.low = min(self.prices)

        self._update_atr(price)
        self._update_adx(price)
        self._update_volume_stats(volume)

        if len(self.prices) < self.lookback:
            return

        # Calculate dynamic breakout entry thresholds
        dynamic_x = self.high - self.pr_x * self.mean_atr if self.mean_atr else self.high
        dynamic_y = self.low + self.pr_y * self.mean_atr if self.mean_atr else self.low

        # Entry condition - EXECUTE REAL BUY ORDER
        if (price >= dynamic_x and volume > self.mean_vol and 
            len(self.positions) < self.max_positions):

            # Minimum 100 USDT notional value required
            position_size = 0.002  # 0.002 BTC (~200 USDT at BTC=100k)
            self._execute_buy(timestamp, price, position_size)

        # Short-term high/low tracking
        if len(self.prices) >= self.short_time_len:
            self.short_high = max(self.short_high, price)
            self.short_low = min(self.short_low, price)

        # Exit condition - EXECUTE REAL SELL ORDER
        drawback = 0.05
        hold_minutes = 60

        for pos in self.positions[:]:
            holding_time = (timestamp - pos['entry_time']).total_seconds() / 60
            unrealized_gain = (price - pos['entry']) / pos['entry']

            if (price < self.short_high * (1 - drawback) and 
                holding_time > hold_minutes and 
                price > pos['entry']):
                self._execute_sell(timestamp, pos, price, "PROFIT_TAKE")

            elif price < self.short_low * (1 - drawback):
                self._execute_sell(timestamp, pos, price, "STOP_LOSS")


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
    """Main function to run live trading with Binance testnet."""
    
    # Validate API credentials
    if not API_KEY or not API_SECRET:
        raise ValueError(
            "API credentials not found. Please set BINANCE_TESTNET_API_KEY and "
            "BINANCE_TESTNET_API_SECRET in .env file"
        )
    
    # Initialize Binance trader
    logging.info(f"Initializing BinanceTrader (testnet={USE_TESTNET})")
    trader = BinanceTrader(
        api_key=API_KEY,
        api_secret=API_SECRET,
        use_testnet=USE_TESTNET
    )
    
    # Test connection by getting account balance
    try:
        balance = trader.get_balance(account_type='futures')
        logging.info(f"Account Balance: {balance}")
    except Exception as e:
        logging.error(f"Failed to connect to Binance: {e}")
        raise
    
    # Initialize Kafka consumer
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda v: v
    )
    logging.info(f"Subscribed to Kafka topic: {KAFKA_TOPIC}")
    
    # Strategy instances per symbol
    strategies: Dict[str, LiveTradingStrategy] = {}
    last_print_time = datetime.now()
    
    logging.info("🚀 Live trading started!")
    telegram_bot.send_msg(f"🚀 Live Trading Started (Testnet={USE_TESTNET})")
    
    for msg in consumer:
        raw_data = parse_kafka_message(msg.value)
        if not raw_data:
            continue

        try:
            timestamp = raw_data['timestamp']
            symbol = raw_data['symbol']
            close_price = raw_data['close_price']

            # Initialize strategy for new symbols
            if symbol not in strategies:
                strategies[symbol] = LiveTradingStrategy(
                    symbol=symbol,
                    trader=trader,
                    max_positions=MAX_POSITIONS,
                    leverage=LEVERAGE
                )
                logging.info(f"Initialized strategy for {symbol}")
            
            # Process tick
            timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            strategies[symbol].on_tick(timestamp, raw_data)

            # Print portfolio summary every 5 minutes
            now = datetime.now()
            if (now - last_print_time).total_seconds() >= 300:  # 5 minutes
                portfolio_earn = {
                    symbol: round(strategies[symbol].avg_earn * 100, 4) 
                    for symbol in strategies 
                    if strategies[symbol].num_trade > 0
                }
                
                if portfolio_earn:
                    max_earn = max(portfolio_earn.values())
                    min_earn = min(portfolio_earn.values())
                    mean_earn = sum(portfolio_earn.values()) / len(portfolio_earn)
                    
                    # Calculate total trades and active positions
                    total_trades = sum(s.num_trade for s in strategies.values())
                    active_positions = sum(len(s.positions) for s in strategies.values())
                    
                    # Top and worst performers
                    sorted_earn = sorted(portfolio_earn.items(), key=lambda x: x[1], reverse=True)
                    top_3 = sorted_earn[:3]
                    worst_3 = sorted_earn[-3:]
                    
                    logging.info("\n" + "=" * 80)
                    logging.info("📊 PORTFOLIO SUMMARY")
                    logging.info("=" * 80)
                    logging.info(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                    logging.info(f"Total Symbols Traded: {len(portfolio_earn)}")
                    logging.info(f"Total Trades Executed: {total_trades}")
                    logging.info(f"Active Positions: {active_positions}")
                    logging.info(f"Average Return: {mean_earn:.2f}%")
                    logging.info(f"Best Return: {max_earn:.2f}%")
                    logging.info(f"Worst Return: {min_earn:.2f}%")
                    logging.info("\nTop 3 Performers:")
                    for sym, ret in top_3:
                        logging.info(f"   {sym}: {ret:+.2f}%")
                    logging.info("\nWorst 3 Performers:")
                    for sym, ret in worst_3:
                        logging.info(f"   {sym}: {ret:+.2f}%")
                    logging.info("=" * 80 + "\n")
                    
                    # Send telegram summary
                    telegram_bot.send_msg(
                        f"📊 Portfolio Update\n"
                        f"Time: {now.strftime('%H:%M')}\n"
                        f"Symbols: {len(portfolio_earn)} | Trades: {total_trades}\n"
                        f"Active: {active_positions} positions\n"
                        f"Avg Return: {mean_earn:.2f}%\n"
                        f"Range: {min_earn:.2f}% ~ {max_earn:.2f}%"
                    )
                
                last_print_time = now
                
        except KeyError as e:
            logging.warning(f"Incomplete data in message: {raw_data}, error: {e}")
        except Exception as e:
            logging.error(f"Error processing message: {e}", exc_info=True)


if __name__ == "__main__":
    run_live_trading()
