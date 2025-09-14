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
                portfolio_earn = {symbol: strategies[symbol].avg_earn for symbol in strategies if strategies[symbol].num_trade > 0}
                total_earn = sum(portfolio_earn.values()) / len(portfolio_earn) if portfolio_earn else 0.0
                logging.info(f"Avg Earn per Symbol: {portfolio_earn}")
                logging.info(f"{now} - Total Earn: {total_earn}")
                last_print_time = now
        except KeyError as e:
            logging.warning(f"Incomplete data in message: {raw_data}")


if __name__ == "__main__":
    consume_kafka_messages()
