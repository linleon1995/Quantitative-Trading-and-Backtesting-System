
from src.strategies.naive_strategy import NaiveStrategy


def test_naive_strategy():
    naive_strategy = NaiveStrategy(buy_rate=0.0, sell_rate=0.05)
    trade_request = naive_strategy.add_tick(symbol='ETHUSDT', price=3000)
    trade_request = naive_strategy.add_tick(symbol='ETHUSDT', price=3001)
    assert trade_request.action == 'buy'

    trade_request = naive_strategy.add_tick(symbol='ETHUSDT', price=4000)
    assert trade_request is None
    trade_request = naive_strategy.add_tick(symbol='ETHUSDT', price=50000)
    assert trade_request is None

    trade_request = naive_strategy.add_tick(symbol='ETHUSDT', price=47400)
    assert trade_request.action == 'sell'
    
