import json
import logging
from datetime import datetime

from kafka import KafkaConsumer

from src.event import telegram_bot
from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader

KAFKA_BOOTSTRAP_SERVERS = ['localhost:29092']
KAFKA_TOPIC = 'binance_kline'

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/mock_trading.log"),
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

# TRADERS = {}
def mock_trade(timestamp, symbol, close_price, volume, traders):

    # traders[symbol].on_tick(tick=close_price, unix_time=timestamp)
    tick = (timestamp, {'close_price': close_price, 'volume': volume})
    traders[symbol].on_tick(*tick)

    # if timestamp.minute % 10 == 0:
    #     print(33)
    #     avg_earn = 0
    #     for symbol, strategy in traders.items():
    #         total_earn = sum(trade['earn'] for trade in strategy.trade_records)
    #         avg_earn += total_earn
    #     telegram_bot.send_msg(f"{datetime.now()} {avg_earn/len(traders)} %")

def consume_kafka_messages():
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda v: v  # we decode manually
    )
    logging.info(f"Subscribed to Kafka topic: {KAFKA_TOPIC}")

    trading_count = 0
    last_timestamp = None
    traders = {}
    for msg in consumer:
        raw_data = parse_kafka_message(msg.value)
        if not raw_data:
            continue

        try:
            timestamp = raw_data['timestamp']
            symbol = raw_data['symbol']
            close_price = raw_data['close_price']
            volume = raw_data['volume']

            if symbol not in traders:
                traders[symbol] = DynamicBreakoutTrader(symbol=symbol)

            timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            mock_trade(timestamp, symbol, close_price, volume, traders)

            if last_timestamp is None:
                last_timestamp = timestamp
            else:
                if last_timestamp != timestamp:
                    if timestamp.minute % 10 == 0:
                        total_earn = 0
                        non_zeros = 0
                        for symbol, strategy in traders.items():
                            earn = sum(trade['earn'] for trade in strategy.trade_records)
                            if earn != 0:
                                total_earn += earn
                                non_zeros += 1
                                logging.info(f'{symbol} {100*earn:.3f} %')
                        avg_earn = total_earn / non_zeros if non_zeros > 0 else total_earn
                        logging.info(f"{datetime.now()} total {100*total_earn:.3f} % avg {100*avg_earn:.3f} %")
                        telegram_bot.send_msg(f"{datetime.now()} total {100*total_earn:.3f} % avg {100*avg_earn:.3f} %")
                    last_timestamp = timestamp


            # readable_time = datetime.fromtimestamp(timestamp / 1000)
            # logging.info(f"{timestamp} - {symbol} Close Price: {close_price}")
        except KeyError as e:
            logging.warning(f"Incomplete data in message: {raw_data}")


if __name__ == "__main__":
    consume_kafka_messages()
