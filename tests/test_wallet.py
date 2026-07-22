import numpy as np
import pytest

from src.backtset.wallet import Asset, BaseWallet, Coin, TradeRequest


@pytest.fixture
def mock_wallet():
    return BaseWallet()


@pytest.fixture
def mock_asset():
    return Asset()


def test_metrics(mock_wallet):
    mock_wallet.deposit(Coin('USDT', 10000))
    trade_request1 = TradeRequest(action='buy', number=1, symbol='ETH', price=3000)
    trade_request2 = TradeRequest(action='sell', number=1, symbol='ETH', price=3100)
    trade_request3 = TradeRequest(action='buy', number=1, symbol='ETH', price=2900)
    trade_request4 = TradeRequest(action='sell', number=1, symbol='ETH', price=3100)

    trade_response, trade_metrics1 = mock_wallet.add_trade(trade_request1)
    trade_response, trade_metrics2 = mock_wallet.add_trade(trade_request2)
    trade_response, trade_metrics3 = mock_wallet.add_trade(trade_request3)
    trade_response, trade_metrics4 = mock_wallet.add_trade(trade_request4)

    assert mock_wallet.metrics.returns == [100/3000, 200/2900]
    assert mock_wallet.metrics.average_return == np.mean([100/3000, 200/2900])
    assert mock_wallet.metrics.return_std_dev == np.std([100/3000, 200/2900])
    # assert trade_metrics.total_cost is None
    assert mock_wallet.metrics.total_revenue == 6200
    assert mock_wallet.metrics.total_profit == 300
    assert mock_wallet.metrics.sell_count == 2
    assert mock_wallet.metrics.win_count == 2
    assert mock_wallet.metrics.win_rate == 1.0
    assert mock_wallet.metrics.peak == 3100
    pass


# def test_get_cost(mock_wallet):
#     mock_wallet.deposit(Coin('USDT', 1000))
#     mock_wallet.update_price(symbol='USDT', price=1)
#     assert mock_wallet.get_cost(symbol='USDT') == 1000

#     mock_wallet.deposit(Coin('ETH', 1.5))
#     mock_wallet.update_price(symbol='ETH', price=3000)
#     assert mock_wallet.get_cost(symbol='ETH') == 4500

#     assert mock_wallet.get_cost(symbol='BTC') is None
#     mock_wallet.deposit(Coin('BTC', 1.5))
#     assert mock_wallet.get_cost(symbol='BTC') is None
#     mock_wallet.update_price(symbol='BTC', price=40000)
#     assert mock_wallet.get_cost(symbol='BTC') == 60000


def test_check_balance(mock_wallet):
    mock_wallet.deposit(Coin('USDT', 1000))
    assert mock_wallet.check_balance('USDT', 1000)
    assert not mock_wallet.check_balance('USDT', 1001)


def test_get_balance(mock_wallet):
    symbol = 'USDT'
    mock_wallet.deposit(Coin(symbol, 1000))
    assert mock_wallet.get_coin_balance(symbol) == 1000
    mock_wallet.deposit(Coin(symbol, 1000))
    assert mock_wallet.get_coin_balance(symbol) == 2000
    
    symbol = 'USDC'
    mock_wallet.deposit(Coin(symbol, 1000, 1))
    assert mock_wallet.get_coin_balance(symbol) == 1000
    mock_wallet.deposit(Coin(symbol, 1000))
    assert mock_wallet.get_coin_balance(symbol) == 2000


def test__add_trade(mock_wallet):
    mock_wallet.deposit(Coin('USDT', 10000))
    trade_signal = TradeRequest(symbol='ETH', price=3000, 
                             bridgecoin_name='USDT', bridgecoin_price=1, 
                             action='buy', number=1.0)
    mock_wallet._add_trade(trade_signal)
    assert mock_wallet.get_coin_balance('USDT') == 7000
    assert mock_wallet.get_coin_balance('ETH') == 1


def test_deposit(mock_wallet):
    usdt = Coin(symbol='USDT', number=10000)
    response = mock_wallet.deposit(usdt)
    assert mock_wallet.asset.coins['USDT'] == usdt
    assert response.status == 'success'
    
def test_trade(mock_wallet):
    usdt = Coin(symbol='USDT', number=100000)
    response = mock_wallet.deposit(usdt)
    eth = Coin(symbol='ETH', number=2)
    response = mock_wallet.deposit(eth)
    
    # success
    trade_signal = TradeRequest(symbol='ETH', price=3000, 
                             bridgecoin_name='USDT', bridgecoin_price=1, 
                             action='buy', number=1.0)
    trade_response = mock_wallet.add_trade(trade_signal)
    assert trade_response.status == 'success'
    assert mock_wallet.get_coin_balance('USDT') == 97000
    assert mock_wallet.get_coin_balance('ETH') == 3
    
    # fail, not enough money
    trade_signal = TradeRequest(symbol='BTC', price=70000, 
                             bridgecoin_name='USDT', bridgecoin_price=1, 
                             action='sell', number=1.0)
    trade_response = mock_wallet.add_trade(trade_signal)
    assert trade_response.status == 'fail'
    assert mock_wallet.get_coin_balance('USDT') == 97000
    assert mock_wallet.get_coin_balance('ETH') == 3

    # fail, no coin
    trade_signal = TradeRequest(symbol='BNB', price=3000, 
                             bridgecoin_name='USDT', bridgecoin_price=1, 
                             action='sell', number=4.0)
    trade_response = mock_wallet.add_trade(trade_signal)
    assert trade_response.status == 'fail'
    assert mock_wallet.get_coin_balance('USDT') == 97000
    assert mock_wallet.get_coin_balance('ETH') == 3
    assert mock_wallet.get_coin_balance('BNB') == 0

    # edge case
    trade_signal = TradeRequest(symbol='ETH', price=4000,
                             bridgecoin_name='USDT', bridgecoin_price=1, 
                             action='sell', number=3.0)
    trade_response = mock_wallet.add_trade(trade_signal)
    assert trade_response.status == 'success'
    assert mock_wallet.get_coin_balance('USDT') == 109000
    assert mock_wallet.get_coin_balance('ETH') == 0



# def test_trade(mock_wallet):
#     response = mock_wallet.deposit(100000, 'BTC')
#     assert mock_wallet.total_value == 100000
 
#     assert mock_wallet.amount('BTC') is None
#     mock_wallet.buy(1, 'BTC', 'USDT', 70000)
#     assert mock_wallet.amount('BTC') == 1
#     assert mock_wallet.value('BTC') == 70000
#     assert mock_wallet.amount('USDT') == 30000
#     assert mock_wallet.value('USDT') == 1

#     assert mock_wallet.total_value == 100000
#     assert isinstance(mock_wallet.portfolio, dict)
#     # assert mock_wallet.portfolio.
#     assert mock_wallet.profit == 0
    
#     assert mock_wallet.roi == 0
#     assert mock_wallet.profit == 0

#     mock_wallet.sell(0.5, 'BTC', 'USDT', 80000)
#     assert mock_wallet.amount('BTC') == 0.5
#     assert mock_wallet.price('BTC') == 80000
#     assert mock_wallet.value('BTC') == 40000
#     assert mock_wallet.amount('USDT') == 70000
#     assert mock_wallet.price('USDT') == 1
#     assert mock_wallet.value('USDT') == 70000
#     assert mock_wallet.roi == 0.1
#     assert mock_wallet.profit == 10000
#     assert mock_wallet.coin_profit('BTC') == 5000
#     assert mock_wallet.coin_roi('BTC') == 1/7

#     mock_wallet.update_price('BTCUSDT', 90000)
#     assert mock_wallet.roi == 0.15
#     assert mock_wallet.profit == 15000
#     assert mock_wallet.coin_profit('BTC') == 10000
#     assert mock_wallet.coin_roi('BTC') == 2/7

#     # cost?
#     # update_multi_price

