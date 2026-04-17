import asyncio
import json
import logging
import logging.handlers
import time
from datetime import datetime
from pathlib import Path

import requests
import websockets
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic

# Ensure log directory exists
log_dir = Path('logs')
log_dir.mkdir(parents=True, exist_ok=True)

# Daily-rotating log: rotates at UTC midnight, keeps 30 days (S-3)
_log_handler = logging.handlers.TimedRotatingFileHandler(
    filename='logs/binanace_producer.log',
    when='midnight',
    interval=1,
    backupCount=30,
    encoding='utf-8',
    utc=True,
)
_log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[_log_handler])

KAFKA_BOOTSTRAP_SERVERS = ['kafka:9092']
KAFKA_TOPIC = 'binance_kline'
BINANCE_WS_URI = "wss://fstream.binance.com/ws"  # Futures WebSocket
STREAMS_PER_WS = 100


def create_kafka_topic(topic_name, bootstrap_servers):
    admin_client = KafkaAdminClient(bootstrap_servers=bootstrap_servers)
    topic_list = admin_client.list_topics()
    if topic_name not in topic_list:
        topic = NewTopic(name=topic_name, num_partitions=1, replication_factor=1)
        try:
            admin_client.create_topics([topic])
            logging.info(f"Created Kafka topic: {topic_name}")
        except Exception as e:
            logging.warning(f"Could not create topic {topic_name}: {e}")
    admin_client.close()


class BinanceKafkaProducerWorker:
    def __init__(self, symbols: list[str], producer: KafkaProducer):
        self.symbols = symbols
        self.producer = producer

    async def run(self):
        while True:  # 外層 loop: 若連線中斷則重試
            async with websockets.connect(BINANCE_WS_URI) as ws:
                subscribe_msg = {
                    "method": "SUBSCRIBE",
                    "params": self.symbols,
                    "id": 1
                }
                await ws.send(json.dumps(subscribe_msg))
                logging.info(f"Subscribed: {self.symbols}")

                while True:  # 內層 loop: 接收資料
                    try:
                        msg = await ws.recv()
                        data = json.loads(msg)

                        if 'k' not in data:
                            continue

                        kline = data['k']

                        # Only emit when the candle is closed (final value)
                        if not kline.get('x', False):
                            continue

                        symbol = data['s']
                        tick = {
                            'symbol': symbol,
                            'interval': kline['i'],
                            'open_time': int(kline['t']),    # ms
                            'open':      float(kline['o']),
                            'high':      float(kline['h']),
                            'low':       float(kline['l']),
                            'close':     float(kline['c']),
                            'volume':    float(kline['v']),
                            'close_time': int(kline['T']),   # ms
                        }

                        self.producer.send(KAFKA_TOPIC, key=symbol, value=tick)
                        logging.debug(f"Closed candle sent: {symbol} {kline['i']} @ {kline['t']}")

                    except Exception as e:
                        logging.error(f"WebSocket error: {e}")
                        await asyncio.sleep(5)
                        break


class BinanceKafkaProducerManager:
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            key_serializer=lambda k: k.encode('utf-8'),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def chunk_symbols(self, chunk_size):
        for i in range(0, len(self.symbols), chunk_size):
            yield self.symbols[i:i + chunk_size]

    async def start_all(self):
        tasks = []
        for idx, chunk in enumerate(self.chunk_symbols(STREAMS_PER_WS)):
            worker = BinanceKafkaProducerWorker(chunk, self.producer)
            tasks.append(worker.run())
        await asyncio.gather(*tasks)


def main():
    create_kafka_topic(KAFKA_TOPIC, KAFKA_BOOTSTRAP_SERVERS)

    # Use Futures exchangeInfo so symbols are consistent with where we place orders
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    response = requests.get(url)
    data = response.json()
    symbols = [
        f"{symbol_info['symbol'].lower()}@kline_1m"
        for symbol_info in data['symbols']
        if symbol_info['symbol'].endswith('USDT')
        and symbol_info['status'] == 'TRADING'
        and symbol_info.get('contractType') == 'PERPETUAL'
    ]

    logging.info(f"Total symbols: {len(symbols)}")

    manager = BinanceKafkaProducerManager(symbols)
    asyncio.run(manager.start_all())


if __name__ == "__main__":
    main()
