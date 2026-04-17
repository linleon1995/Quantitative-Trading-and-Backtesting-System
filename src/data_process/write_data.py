import csv
import logging
import pathlib
import zipfile
from dataclasses import fields

# from write_binance_data import format_kline_data
import pandas as pd

from src.data_source.create_backtest_database import ArcticDBOperator

from src.data_process.data_structure import BinanceTick

# 假設你已經有 arctic_ops
# from your_module import arctic_ops

DATA_DIR = pathlib.Path("data")
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

BATCH_SIZE = 1000  # 一次最多 insert 1000 筆


def extract_zip(zip_path: pathlib.Path, extract_to: pathlib.Path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        logging.info(f"Extracted {zip_path} to {extract_to}")
    except Exception as e:
        logging.error(f"Failed to extract {zip_path}: {e}")
        raise

def parse_csv(csv_file: pathlib.Path):
    try:
        with open(csv_file, 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            logging.info(f"Parsed {len(rows)} rows from {csv_file}")
            return rows
    except Exception as e:
        logging.error(f"Failed to parse {csv_file}: {e}")
        raise

# def format_record(row):
#     try:
#         open_time = datetime.fromtimestamp(int(row[0]) / 1_000_000, tz=timezone.utc).astimezone(timezone(timedelta(hours=8)))
#         close_time = datetime.fromtimestamp(int(row[6]) / 1_000_000, tz=timezone.utc).astimezone(timezone(timedelta(hours=8)))
        
#         return {
#             "open_time": open_time,
#             "open_price": float(row[1]),
#             "high_price": float(row[2]),
#             "low_price": float(row[3]),
#             "close_price": float(row[4]),
#             "volume": float(row[5]),
#             "close_time": close_time,
#             "quote_asset_volume": float(row[7]),
#             "number_of_trades": int(row[8]),
#             "taker_buy_base_asset_volume": float(row[9]),
#             "taker_buy_quote_asset_volume": float(row[10]),
#             "ignore": row[11],
#         }
#     except Exception as e:
#         logging.error(f"Failed to format row {row}: {e}")
#         return None

# def batch_insert(symbol, records):
#     try:
#         for i in range(0, len(records), BATCH_SIZE):
#             batch = records[i:i+BATCH_SIZE]
#             arctic_ops.add(symbol, batch)
#             logging.info(f"Inserted batch {i//BATCH_SIZE+1} of {symbol}, {len(batch)} records")
#     except Exception as e:
#         logging.error(f"Failed to insert batch for {symbol}: {e}")
#         raise


def format_kline_data(data, tick_data):
    if data is not None or len(data) != 0:
        tick_fields = [field.name for field in fields(class_or_instance=tick_data)]
        data = pd.DataFrame(data=data, columns=tick_fields)
        # start_timestamp_ms = data.iloc[0]['open_time']
        # start_timestamp_sec = start_timestamp_ms / 1000
        # end_timestamp_ms= data.iloc[-1]['open_time']
        # end_timestamp_ms = end_timestamp_ms / 1000

        data['open_time'] = data['open_time'].apply(format_unix_time).astype('int64')
        data['close_time'] = data['close_time'].apply(format_unix_time).astype('int64')
        data['open_price'] = data['open_price'].astype('float64')
        data['high_price'] = data['high_price'].astype('float64')
        data['low_price'] = data['low_price'].astype('float64')
        data['close_price'] = data['close_price'].astype('float64')
        data['volume'] = data['volume'].astype('float64')
        data['num_of_trades'] = data['number_of_trades'].astype('int64')
        data['quote_asset_volume'] = data['quote_asset_volume'].astype('float64')
        data['taker_buy_base_asset_volume'] = data['taker_buy_base_asset_volume'].astype('float64')
        data['taker_buy_quote_asset_volume'] = data['taker_buy_quote_asset_volume'].astype('float64')
        data['unused_field'] = data['unused_field'].astype('str')

        data["open_datetime"] = pd.to_datetime(data["open_time"], unit="ms")
        data = data.set_index(keys="open_datetime")
    return data


def format_unix_time(ts: int | str) -> float:
    if isinstance(ts, str):
        ts = int(ts)

    ts_length = len(str(ts))

    if ts_length == 19:
        raise ValueError(f"ns timestamp not supported: {ts}")
    elif ts_length == 16:
        # 微秒
        ts_sec = ts // 1_000
    elif ts_length == 13:
        # 毫秒
        ts_sec = ts
    elif ts_length == 10:
        # 秒（目前Binance不會有）
        ts_sec = ts * 1_000
    else:
        raise ValueError(f"Unexpected timestamp length: {ts} (value: {ts})")
    return ts_sec


def process_symbol_folder(symbol_folder: pathlib.Path):
    symbol = symbol_folder.name
    arctic_ops = ArcticDBOperator(url="lmdb://arctic_database", lib_name='BinanceSpot')
    try:
        for zip_file in symbol_folder.glob("*.zip"):
            temp_extract_dir = symbol_folder / "temp"
            temp_extract_dir.mkdir(exist_ok=True)

            extract_zip(zip_file, temp_extract_dir)

            for csv_file in temp_extract_dir.glob("*.csv"):
                try:
                    raw_rows = parse_csv(csv_file)
                    # for row in raw_rows:
                        # row[0] = format_unix_time(row[0])
                        # row[6] = format_unix_time(row[6])
                        # row[8] = int(row[8])
                    formated_data = format_kline_data(raw_rows, tick_data=BinanceTick)
                    arctic_ops.add(symbol, formated_data)
                    # for row in tqdm(raw_rows, desc=f"Processing {csv_file.name}", unit="rows"):
                    #     formatted = format_record(row)
                    #     if formatted:
                    #         records.append(formatted)

                    # if records:
                    #     batch_insert(symbol, records)

                except Exception as e:
                    logging.error(f"Failed to process {csv_file}: {e}")
            
            # Clean up temp files
            for f in temp_extract_dir.iterdir():
                try:
                    f.unlink()
                except Exception as e:
                    logging.warning(f"Failed to delete temp file {f}: {e}")
            try:
                temp_extract_dir.rmdir()
            except Exception as e:
                logging.warning(f"Failed to remove temp folder {temp_extract_dir}: {e}")
            
    except Exception as e:
        logging.error(f"Failed to process folder {symbol_folder}: {e}")

def main():
    try:
        idx = 0
        for symbol_folder in DATA_DIR.iterdir():
            if symbol_folder.is_dir():
                logging.info(f"Starting processing for {symbol_folder.name} at index {idx}")
                process_symbol_folder(symbol_folder)
                idx += 1
    except Exception as e:
        logging.critical(f"Critical failure: {e}")


if __name__ == "__main__":
    main()
