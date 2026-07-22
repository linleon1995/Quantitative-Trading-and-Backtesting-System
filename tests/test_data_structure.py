from datetime import datetime

import pytest

from src.data_process.data_structure import (
    BinanceTick,
    BinanceTickProcessor,
    GeneralTickData,
)


@pytest.fixture
def mock_general_tick_data():
    return GeneralTickData(symbol='BTCUSDT', maxlen=5, moving_average_spans=[1, 4])


def test_general_tick_data(mock_general_tick_data):
    now = datetime.now()
    mock_general_tick_data.put_tick(tick=0, unix_time=now)

    # test basic ticks and time function
    assert mock_general_tick_data.ticks[0] == 0
    assert mock_general_tick_data.time[0] == now

    # test mean average calculation
    mock_general_tick_data.put_tick(tick=100, unix_time=now)
    mock_general_tick_data.put_tick(tick=200, unix_time=now)
    mock_general_tick_data.put_tick(tick=300, unix_time=now)
    mock_general_tick_data.put_tick(tick=400, unix_time=now)
    mock_general_tick_data.put_tick(tick=500, unix_time=now)
    assert mock_general_tick_data.ticks[0] == 100
    assert mock_general_tick_data.ticks[-1] == 500
    assert mock_general_tick_data.moving_average_data_pool[1][-1] == 500
    assert mock_general_tick_data.moving_average_data_pool[4][-1] == 1400 / 4

    # test queue max length adjustment
    test_tick = GeneralTickData(symbol='BTCUSDT', maxlen=3, moving_average_spans=[100])
    assert test_tick.maxlen == 100


@pytest.fixture
def mock_binanace_tick_processor():
    # TODO: Bollinger Band setup
    return BinanceTickProcessor(symbol='BTCUSDT', maxlen=5, moving_average_spans=[1, 4])


@pytest.fixture
def mock_raw_binance_tick():
    raw_binance_tick = [1623045600000, '0.04139000', '4.50000000', '0.04139000', '2.48012000', 
                 '6729560.00000000', 1623045659999, '16550755.04451000', 41491, 
                 '3506204.00000000', '9156654.57239000', '0']
    return raw_binance_tick

def test_binanace_tick_processor(mock_binanace_tick_processor: BinanceTickProcessor, mock_raw_binance_tick: list):
    mock_binanace_tick_processor.put_tick(mock_raw_binance_tick)
    assert mock_binanace_tick_processor.ticks[0] == BinanceTick(*mock_raw_binance_tick)
    assert mock_binanace_tick_processor.prices[0] == float(mock_raw_binance_tick[4])

    # assert mock_binanace_tick_processor.bollinger_band # {'upper_band': 0.74, 'lower_band': 0.65, 'moving_average': 0.7}
