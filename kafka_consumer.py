import json
import logging
from datetime import datetime

from kafka import KafkaConsumer

from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader

KAFKA_BOOTSTRAP_SERVERS = ['localhost:29092']
KAFKA_TOPIC = 'binance_kline'

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/kafka_consumer.log"),
        logging.StreamHandler()
    ]
)

def parse_kafka_message(message_value):
    try:
        # Kafka message is in bytes -> decode -> json.loads
        msg_str = message_value.decode('utf-8')
        data = json.loads(msg_str)
        return data
    except Exception as e:
        logging.error(f"Error parsing message: {e}")
        return None

def consume_kafka_messages():
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda v: v  # we decode manually
    )
    logging.info(f"Subscribed to Kafka topic: {KAFKA_TOPIC}")
    
    strategies = {}
    for msg in consumer:
        raw_data = parse_kafka_message(msg.value)
        if not raw_data:
            continue

        try:
            timestamp = raw_data['timestamp']
            symbol = raw_data['symbol']
            close_price = raw_data['close_price']
            # logging.info(f"{timestamp} - {symbol} Close Price: {close_price}")

            if symbol not in strategies:
                strategies[symbol] = DynamicBreakoutTrader(symbol=symbol)
            
            timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            strategies[symbol].on_tick(timestamp, raw_data)

            # Print every 1 minute based on a global last_print_time
            if 'last_print_time' not in globals():
                global last_print_time
                last_print_time = datetime.now()

            now = datetime.now()
            if (now - last_print_time).total_seconds() >= 60:
                portfolio_earn = {symbol: round(strategies[symbol].avg_earn, 4) for symbol in strategies if strategies[symbol].num_trade > 0}
                max_earn = max(portfolio_earn.values()) if portfolio_earn else 0.0
                min_earn = min(portfolio_earn.values()) if portfolio_earn else 0.0
                mean_earn = sum(portfolio_earn.values()) / len(portfolio_earn) if portfolio_earn else 0.0
                holding_coins = sum(1 for s in strategies.values() if getattr(s, "position", 0) != 0)
                total_earn = mean_earn * len(portfolio_earn)
                portfolio_earn = sorted(portfolio_earn.items(), key=lambda x: x[1], reverse=True)
                portfolio_earn = dict(portfolio_earn)
                logging.info("-" * 60)
                logging.info(f"Time: {now}")
                logging.info(f"Holding Coins: {holding_coins}")
                logging.info(f"Max Earn: {max_earn*100:.2f}%, Min Earn: {min_earn*100:.2f}%")
                logging.info(f"Simple Average Return: {mean_earn*100:.2f}%")
                logging.info(f"Weighted Average Return: {mean_earn*100:.2f}%")
                logging.info(f"Avg Earn per Symbol: {portfolio_earn}")
                logging.info(f"Number of Traded Symbols: {len(portfolio_earn)}")
                logging.info(f"Total Earn: {total_earn*100:.2f}%")

                last_print_time = now
        except KeyError as e:
            logging.warning(f"Incomplete data in message: {raw_data}")


if __name__ == "__main__":
    consume_kafka_messages()
