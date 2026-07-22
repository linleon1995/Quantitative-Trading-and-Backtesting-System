from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class OneStock:
    symbol: str
    # number: list
    # prices: list
    trade_history: list = field(default_factory=list)

    @property
    def avg_cost(self):
        return sum([trade_data.price for trade_data in self.trade_history]) / len(self.trade_history)
    
    @property
    def number(self):
        return sum([trade_data.number for trade_data in self.trade_history])

@dataclass
class EvalResult:
    avg_roi: float
    max_roi: float
    min_roi: float
    trade_times: int
    win_rate: float
    start_timestamp: str = None
    end_timestamp: str = None


@dataclass
class Metrics:
    average_return: float = 0.0
    return_std_dev: float = 0.0
    total_cost: float = 0.0
    total_revenue: float = 0.0
    total_profit: float = 0.0
    returns: List[float] = field(default_factory=list)
    buy_count: int = 0
    sell_count: int = 0
    trade_count: int = 0
    win_count: int = 0
    win_rate: float = 0.0
    peak: float = -np.inf
    max_drawdown: float = 0.0
    max_drawdown_rate: float = 0.0
    # TODO: buy_count need to be added in the future.


class Evaluator:
    def calculate_aggregated_metrics(self, cost, trades: List, metrics: Optional[Metrics] = None) -> Metrics:
        if metrics is None:
            metrics = self._init_metrics()

        # update trade metrics for every new trade
        for trade in trades:
            trade_metrics = self.calculate_trade_metrics(cost, trade.price, trade.number)
            self.update_metrics(trade_metrics, metrics)
        return metrics

    def _init_metrics(self) -> Metrics:
        return Metrics()
        
    def calculate_trade_metrics(self, cost, sell_price, amount):
        revenue = amount * sell_price
        profit = revenue - cost * amount
        return_rate = (sell_price-cost) / cost
        return {
            # "cost": cost,
            "revenue": revenue,
            "profit": profit,
            "return_rate": return_rate,
            "sell_price": sell_price,
        }
    
    def update_metrics(self, trade_metrics, metrics: Metrics):
        # metrics.total_cost += trade_metrics["cost"]
        metrics.total_revenue += trade_metrics["revenue"]
        metrics.total_profit += trade_metrics["profit"]
        metrics.returns.append(trade_metrics["return_rate"])
        metrics.sell_count += 1

        # update win count
        if trade_metrics["return_rate"] > 0:
            metrics.win_count += 1

        # update max drawdown
        if trade_metrics["sell_price"] > metrics.peak:
            metrics.peak = trade_metrics["sell_price"]
        drawdown = metrics.peak - trade_metrics["sell_price"]
        if drawdown > metrics.max_drawdown:
            metrics.max_drawdown = drawdown
            metrics.max_drawdown_rate = drawdown / metrics.peak

        # calculate new aggregated metrics
        metrics.average_return = np.mean(metrics.returns) if metrics.returns else 0
        metrics.win_rate = (metrics.win_count / metrics.sell_count) if metrics.sell_count > 0 else 0
        metrics.return_std_dev = np.std(metrics.returns) if metrics.returns else 0