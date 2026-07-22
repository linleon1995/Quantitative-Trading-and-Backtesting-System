import logging
from datetime import datetime
from pathlib import Path

import requests
from tqdm import tqdm

from src.binance_api import BinanceAPI

# 設定 log 檔
logging.basicConfig(filename='binance_download.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def download_binance_klines(symbol: str, interval: str, year: int, month: int, save_dir: str = "data"):
    url = f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{year}-{month:02d}.zip"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            file_path = Path(save_dir) / f"{symbol}-{interval}-{year}-{month:02d}.zip"
            with open(file_path, "wb") as f:
                f.write(response.content)
            print(f"✅ Downloaded: {file_path}")
        else:
            raise Exception(f"HTTP {response.status_code}")
    except Exception as e:
        logging.error(f"Failed to download {symbol} {interval} {year}-{month:02d}: {e}")
        print(f"❌ Failed: {symbol} {interval} {year}-{month:02d}")


def download_range(symbols, interval, start_year, start_month, end_year, end_month, save_dir="data"):
    start = datetime(start_year, start_month, 1)
    end = datetime(end_year, end_month, 1)

    current = start
    while current <= end:
        year = current.year
        month = current.month
        for symbol in symbols:
            download_binance_klines(symbol, interval, year, month, save_dir=Path(save_dir) / symbol)
        if month == 12:
            current = datetime(year + 1, 1, 1)
        else:
            current = datetime(year, month + 1, 1)

# 使用方式
binance_api = BinanceAPI()
coin_list = binance_api.get_symbols()  # e.g., ["BTCUSDT", "ETHUSDT", ...]
coin_list = [symbol for symbol in coin_list if symbol.endswith('USDT') and 'UP' not in symbol and 'DOWN' not in symbol]
coin_list = coin_list[320:]
now = datetime.now()
for symbol in tqdm(coin_list):
    start_date = binance_api.get_earliest_kline_timestamp(symbol, "1d")
    if start_date is None:
        logging.error(f"Failed to get earliest kline timestamp for {symbol}")
        continue
    download_range([symbol], interval="1m", 
                start_year=start_date.year, start_month=start_date.month, 
                end_year=now.year, end_month=now.month)
