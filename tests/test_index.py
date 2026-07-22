import pandas as pd

from src.fin_index.index import bollinger_band, once_bollinger_band
from src.fin_index.mock_data import mock_stock_price


def test_mock_stock_price():
    prices = mock_stock_price(num_steps=20)
    assert prices.size == 20
    

def test_bollinger_band():
    prices = mock_stock_price()

    bollinger_band_res = bollinger_band(prices)
    assert isinstance(bollinger_band_res, dict)
    assert isinstance(bollinger_band_res['moving_average'], pd.Series)
    

def test_once_bollinger_band():
    prices = mock_stock_price(num_steps=20)
    
    bollinger_band_res = once_bollinger_band(prices)
    assert isinstance(bollinger_band_res['moving_average'], float)