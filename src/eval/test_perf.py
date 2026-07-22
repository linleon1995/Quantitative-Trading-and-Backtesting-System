import numpy as np

# 交易记录
trades = [
    {"amount": 1.0, "sell_price": 40000, "cost_price": 50000},
    {"amount": 1.0, "sell_price": 60000, "cost_price": 50000},
    {"amount": 1.0, "sell_price": 30000, "cost_price": 50000},
    {"amount": 1.0, "sell_price": 30000, "cost_price": 50000},
    {"amount": 1.0, "sell_price": 30000, "cost_price": 50000},
]

def calculate_trade_metrics(trade):
    cost = trade["amount"] * trade["cost_price"]
    revenue = trade["amount"] * trade["sell_price"]
    profit = revenue - cost
    return_rate = profit / cost
    return {
        "cost": cost,
        "revenue": revenue,
        "profit": profit,
        "return_rate": return_rate,
        "sell_price": trade["sell_price"],
    }

def update_metrics(metrics, trade_metrics):
    metrics["total_cost"] += trade_metrics["cost"]
    metrics["total_revenue"] += trade_metrics["revenue"]
    metrics["total_profit"] += trade_metrics["profit"]
    metrics["returns"].append(trade_metrics["return_rate"])
    metrics["trade_count"] += 1

    # 更新胜率
    if trade_metrics["return_rate"] > 0:
        metrics["win_count"] += 1

    # 更新最大回撤
    if trade_metrics["sell_price"] > metrics["peak"]:
        metrics["peak"] = trade_metrics["sell_price"]
    drawdown = metrics["peak"] - trade_metrics["sell_price"]
    if drawdown > metrics["max_drawdown"]:
        metrics["max_drawdown"] = drawdown
        metrics["max_drawdown_rate"] = drawdown / metrics["peak"]

def calculate_aggregated_metrics(trades):
    # 初始化汇总容器
    metrics = {
        "total_cost": 0,
        "total_revenue": 0,
        "total_profit": 0,
        "returns": [],
        "trade_count": 0,
        "win_count": 0,
        "peak": -np.inf,
        "max_drawdown": 0,
        "max_drawdown_rate": 0,
    }

    # 逐笔交易计算并更新汇总数据
    for trade in trades:
        trade_metrics = calculate_trade_metrics(trade)
        update_metrics(metrics, trade_metrics)

    # 计算最终指标
    average_return = np.mean(metrics["returns"]) if metrics["returns"] else 0
    win_rate = (metrics["win_count"] / metrics["trade_count"]) if metrics["trade_count"] > 0 else 0
    return_std_dev = np.std(metrics["returns"]) if metrics["returns"] else 0

    return {
        "average_return": average_return,
        "win_rate": win_rate,
        "total_return": metrics["total_profit"],
        "average_profit": metrics["total_profit"] / metrics["trade_count"] if metrics["trade_count"] > 0 else 0,
        "return_std_dev": return_std_dev,
        "max_drawdown": metrics["max_drawdown"],
        "max_drawdown_rate": metrics["max_drawdown_rate"]
    }

metrics = calculate_aggregated_metrics(trades)

print(f"Average Return: {metrics['average_return']*100:.2f}%")
print(f"Win Rate: {metrics['win_rate']*100:.2f}%")
print(f"Total Return: {metrics['total_return']:.2f}")
print(f"Average Profit: {metrics['average_profit']:.2f}")
print(f"Return Standard Deviation: {metrics['return_std_dev']*100:.2f}%")
print(f"Maximum Drawdown: {metrics['max_drawdown']:.2f}")
print(f"Maximum Drawdown Rate: {metrics['max_drawdown_rate']*100:.2f} %")
