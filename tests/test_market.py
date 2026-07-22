import pytest

from src.data_source.create_backtest_database import ArcticDBOperator

# from src.market import Market


@pytest.fixture
def mock_market():
    db_operator = ArcticDBOperator(url="lmdb://arctic_database", lib_name='Binance')
    symbols = ['SOLUSDT', 'BTCUSDT', 'ETHUSDT']
    broker = None
    mock_market = Market(symbols, broker, db_operator)
    return mock_market

# def test_market_singleton(mock_market):
#     wallet = mock_market.get_wallet()
#     market = Market()
#     assert market is mock_market

pytest.skip("Skipping all tests in test_market.py for now.", allow_module_level=True)
def test_market_ticker(mock_market):
    sol_ticker = mock_market.get_ticker('SOLUSDT', start_time='2024-04-05', end_time='2024-04-06')
    pass


def test_market_data_not_exist_in_db():
    pass


def test_multi_tickers():
    multi_ticker = mock_market.get_ticker(['BTCUSDT', 'ETHUSDT'], start_time='2024-04-05', end_time='2024-04-06')

def test_invalid_symbol():
    with pytest.raises(ValueError):
        mock_market.get_ticker('INVALID_SYMBOL', start_time='2024-04-05', end_time='2024-04-06')

def test_invalid_time():
    with pytest.raises(ValueError):
        mock_market.get_ticker('BTCUSDT', start_time='2024-04-05', end_time='2024-04-04')