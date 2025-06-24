import pytest

from src.strategies.rl_strategy import RLStrategy
from src.strategies.strategy_executor import StrategyExecutor


@pytest.fixture
def strategy_executor_with_rl_strategy():
    executor = StrategyExecutor()
    rl_strategy = RLStrategy()

    executor.register_strategy(rl_strategy, ["BTCUSD", "ETHUSD"])
    return executor, rl_strategy


def test_on_market_data(strategy_executor_with_rl_strategy):
    executor, rl_strategy = strategy_executor_with_rl_strategy
    executor.on_market_data("BTCUSD", {"price": 50000, "volume": 100})