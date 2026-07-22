# src/data_source/data_collector_main.py
"""Entry point for the Data Collector process.

Runs independently of the trading process.
Configure symbols, interval, and Kafka settings via environment variables
or edit the constants below.

Usage:
    python -m src.data_source.data_collector_main
"""
import logging
import os

from src.client.binance_api import BinanceAPI
from src.data_process.kline_storage import KlineStorage
from src.data_source.create_backtest_database import ArcticDBOperator
from src.data_source.data_collector import DataCollector
from src.data_source.gap_filler import GapFiller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

KAFKA_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").split(",")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "binance_kline")
ARCTIC_URL = os.environ.get("ARCTIC_URL", "lmdb://arctic_database")
ARCTIC_LIB = os.environ.get("ARCTIC_LIB", "klines")
INTERVAL = os.environ.get("KLINE_INTERVAL", "1m")
# Comma-separated list of symbols; empty = fetch all USDT perpetuals
SYMBOLS_ENV = os.environ.get("SYMBOLS", "BTCUSDT,ETHUSDT")

def main():
    symbols = [s.strip() for s in SYMBOLS_ENV.split(",") if s.strip()]

    api = BinanceAPI()
    operator = ArcticDBOperator(url=ARCTIC_URL, lib_name=ARCTIC_LIB)
    storage = KlineStorage(operator)
    gap_filler = GapFiller(api=api, storage=storage)
    collector = DataCollector(
        gap_filler=gap_filler,
        storage=storage,
        symbols=symbols,
        interval=INTERVAL,
        kafka_topic=KAFKA_TOPIC,
        kafka_servers=KAFKA_SERVERS,
    )

    collector.startup_fill()
    collector.run()


if __name__ == "__main__":
    main()
