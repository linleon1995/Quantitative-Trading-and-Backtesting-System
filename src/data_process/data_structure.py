
import datetime
from collections import deque
from dataclasses import dataclass


@dataclass
class BinanceTick:
    open_time: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    close_time: int
    quote_asset_volume: float
    number_of_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float
    unused_field: str


@dataclass
class BaseCoinMeta:
    pass


@dataclass
class MACoinMeta:
    pass



@dataclass
class CoinData:
    raw_data: deque
    data_pool: dict


class BinanceTickProcessor:
    def __init__(self, symbol, maxlen, moving_average_spans):
        max_time_span = max(moving_average_spans)
        if maxlen < max_time_span:
            maxlen = max(maxlen, max_time_span)
            print(f'Change the queue max length from {maxlen} to {max_time_span} to prevent caculation error.')
        self.maxlen = maxlen
        self.symbol = symbol
        self.ticks = deque(maxlen=self.maxlen)
        self.prices = deque(maxlen=self.maxlen)
        self.moving_average_data_pool = {}
        self.signal_count = 0
        self.moving_average_spans = moving_average_spans
        for moving_average_span in moving_average_spans:
            self.moving_average_data_pool[moving_average_span] = deque(maxlen=self.maxlen)

    def put_tick(self, tick: list):
        binance_tick = BinanceTick(*tick)
        self.ticks.append(binance_tick)
        self.prices.append(float(binance_tick.close_price))
        self.put_moving_average()
        
    def put_moving_average(self):
        cur_ticks_len = len(self.prices)
        for ma_range in self.moving_average_spans:
            if cur_ticks_len >= ma_range and cur_ticks_len > 1:
                start = cur_ticks_len - ma_range
                ma_range_data = list(self.prices)[start:]
                moving_average = sum(ma_range_data) / len(ma_range_data)
                self.moving_average_data_pool[ma_range].append(moving_average)


class GeneralTickData:
    def __init__(self, symbol, maxlen, moving_average_spans):
        max_time_span = max(moving_average_spans)
        if maxlen < max_time_span:
            maxlen = max(maxlen, max_time_span)
            print(f'Change the queue max length from {maxlen} to {max_time_span} to prevent caculation error.')
        self.maxlen = maxlen
        self.symbol = symbol
        self.ticks = deque(maxlen=self.maxlen)
        self.time = deque(maxlen=self.maxlen)
        self.moving_average_data_pool = {}
        self.signal_count = 0
        self.moving_average_spans = moving_average_spans
        for moving_average_span in moving_average_spans:
            self.moving_average_data_pool[moving_average_span] = deque(maxlen=self.maxlen)

    def put_tick(self, tick: float, unix_time):
        # TODO: if no time send in, use datetime.now() directly
        # TODO: complete the testing for different time format
        # TODO: consider get a complex tick (dataframe, class, numpy.array) or simple price (float)
        self.ticks.append(tick)
        if isinstance(unix_time, int):
            self.time.append(datetime.datetime.fromtimestamp(unix_time/1000))
        elif isinstance(unix_time, datetime.datetime):
            self.time.append(unix_time)

        # TODO:
        self.put_ma_data()
        
    def put_ma_data(self):
        cur_ticks_len = len(self.ticks)
        for ma_range in self.moving_average_spans:
            if cur_ticks_len >= ma_range and cur_ticks_len > 1:
                start = cur_ticks_len - ma_range
                ma_range_data = list(self.ticks)[start:]
                moving_average = sum(ma_range_data) / len(ma_range_data)
                self.moving_average_data_pool[ma_range].append(moving_average)

    # @property
    # def isValid(self):
    #     return len(self.ticks) >= max(self.moving_average_spans)