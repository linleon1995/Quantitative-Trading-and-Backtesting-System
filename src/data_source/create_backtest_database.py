
from typing import Any

import arcticdb as adb
import pandas as pd


class ArcticDBOperator:
    def __init__(self, url="lmdb://arctic_database", lib_name="default"):
        self.url = url
        self.ac = adb.Arctic(url)
        lib_list = self.ac.list_libraries()
        self.lib_name = lib_name
        if self.lib_name not in lib_list:
            self.ac.create_library(lib_name)

    def write(self, data_name, data):
        lib = self.ac[self.lib_name]
        lib.write(data_name, data)

    def update(self, data_name, data):
        lib = self.ac[self.lib_name]
        lib.update(data_name, data)

    def add(self, data_name, data):
        lib = self.ac[self.lib_name]
        if lib.has_symbol(data_name):
            lib.update(symbol=data_name, data=data)
        else:
            lib.write(symbol=data_name, data=data)

    def read(self, data_name, start_time, end_time):
        date_range = (start_time, end_time)
        lib = self.ac[self.lib_name]
        data = lib.read(data_name, date_range=date_range)
        return data

    def has_symbol(self, data_name: str) -> bool:
        """Return True if the symbol exists in the library."""
        lib = self.ac[self.lib_name]
        return lib.has_symbol(data_name)

    def read_last(self, data_name: str) -> Any:
        """Return the last row of a symbol (tail=1)."""
        lib = self.ac[self.lib_name]
        return lib.read(data_name, row_range=(-1, None))


def get_data():
    df = pd.read_csv(r'C:\Users\l8432\Downloads\BTCUSDT-1m-2024-04-05\BTCUSDT-1m-2024-04-05.csv')
    return df


def format_data(data):
    start_timestamp_ms = data.iloc[0]['open_time']
    start_timestamp_sec = start_timestamp_ms / 1000
    start_time = pd.to_datetime(start_timestamp_sec, unit='s')
    end_timestamp_ms= data.iloc[-1]['open_time']
    end_timestamp_ms = end_timestamp_ms / 1000
    end_time = pd.to_datetime(end_timestamp_ms, unit='s')
    data = data.set_index(pd.date_range(start=start_time, end=end_time, freq='min'))
    return data


def write_database(formated_data, lib_name, data_name):
    ac = adb.Arctic("lmdb:///Leon/SideProject/quant")
    print(ac.list_libraries())

    lib = ac[lib_name]
    lib.write(data_name, formated_data)