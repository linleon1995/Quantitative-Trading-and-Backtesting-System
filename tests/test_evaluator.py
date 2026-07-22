import numpy as np

from src.backtset.wallet import TradeRequest
from src.eval.evaluator import Evaluator, Metrics


def test_eval():
    evaluator = Evaluator()
    trade_metrics = None
    trade_metrics = evaluator.calculate_aggregated_metrics(cost=1000, trades=[], metrics=trade_metrics)
    assert isinstance(trade_metrics, Metrics)

    trades = [
        TradeRequest(action='sell', symbol='ETH', number=0.5, price=2000),
        TradeRequest(action='sell', symbol='ETH', number=0.5, price=3000),
    ]
    trade_metrics = evaluator.calculate_aggregated_metrics(cost=1000, trades=trades, metrics=trade_metrics)
    assert trade_metrics.returns == [1.0, 2.0]
    assert trade_metrics.average_return == 1.5
    assert trade_metrics.return_std_dev == np.std([(2000-1000)/1000, 
                                                   (3000-1000)/1000])
    # assert trade_metrics.total_cost is None
    assert trade_metrics.total_revenue == 2500
    assert trade_metrics.total_profit == 1500
    assert trade_metrics.sell_count == 2
    assert trade_metrics.win_count == 2
    assert trade_metrics.win_rate == 1.0
    assert trade_metrics.peak == 3000
    # assert trade_metrics.max_drawdown == 0
    # assert trade_metrics.max_drawdown_rate == 0
