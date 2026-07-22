from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional

from src.eval.evaluator import Evaluator


class SingletonCoin:
    _instances = {}

    def __new__(cls, name):
        if name not in cls._instances:
            cls._instances[name] = super(SingletonCoin, cls).__new__(cls)
            cls._instances[name].name = name
            cls._instances[name].number = 0
            cls._instances[name].cost = 0
        return cls._instances[name]

    def __eq__(self, other):
        return self.name == other.name

    def add_coin(self, number, price):
        total_cost = self.cost * self.number + price * number
        self.number += number
        self.cost = total_cost / self.number if self.number else 0

    def remove_coin(self, number):
        self.number -= number
        if self.number < 0:
            self.number = 0


@dataclass
class Response:
    status: str
    msg: str = ''


@dataclass
class ActionStatus:
    success: str = 'success'
    fail: str = 'fail'
    

    
# TODO: add timestamp?
@dataclass
class TradeRequest:
    action: str
    number: float
    symbol: str
    price: float
    bridgecoin_name: str = 'USDT'
    bridgecoin_price: float = 1


@dataclass
class Coin:
    symbol: str
    number: float = 0.0
    cost: float = None

    def add_balance(self, number, cost) -> None:
        if self.number == 0:
            self.number = number
            self.cost = cost
        else:
            if self.cost is not None and cost is not None:
                total_cost = self.cost * self.number + cost * number
                self.cost = total_cost / (self.number + number)
            elif self.cost is None:
                self.cost = cost
            self.number += number

    def subtract_balance(self, number) -> None:
        if number <= self.number:
            self.number -= number
            if self.number == 0:
                self.cost = None
        else:
            raise ValueError(f'Not enough to withdraw {number} {self.symbol} for current balance {self.number}')


@dataclass
class Asset:
    coins: Dict[str, Coin] = field(default_factory=dict)

    def get_coin(self, symbol: str) -> Optional[Coin]:
        coin = self.coins.get(symbol)
        if coin is None:
            coin = Coin(symbol=symbol)
            self.coins[symbol] = coin
        return coin
        
    def deposit(self, symbol: str, number: float, cost: float) -> None:
        storeged_coin = self.get_coin(symbol)
        storeged_coin.add_balance(number, cost)

    def withdraw(self, symbol: str, number: int) -> None:
        coin = self.get_coin(symbol)
        try:
            coin.subtract_balance(number=number)
        except ValueError as e:
            raise ValueError(f'Not enough to withdraw {number} {symbol} for current balance {self.coins[symbol].number}')
    
    def get_balance(self, symbol: Optional[str] = None) -> float:
        if symbol is not None:
            coin = self.get_coin(symbol)
            if coin is not None:
                return coin.number
            else:
                return 0.0
        else:
            return {coin.symbol: coin.number for coin in self.coins.values()}
    
    def is_balance_enough(self, symbol: str, number: int) -> bool:
        return self.get_balance(symbol) >= number
    
    def get_cost(self, symbol: str) -> Optional[float]:
        coin = self.coins.get(symbol)
        if coin is not None:
            return coin.cost
        else:
            return None


class BaseWallet:
    def __init__(self):
        self.asset = Asset()
        self.trade_history = deque(maxlen=1000)
        self.metrics = None
        self.evaluator = Evaluator()

    # # TODO: deposit without coin object
    # def deposit(self, coin, symbol, number):
    #     pass
    
    def get_cost(self, symbol: str) -> Optional[float]:
        return self.asset.get_cost(symbol)

    def deposit(self, coin: Coin) -> dict:
        try:
            self.asset.deposit(coin.symbol, coin.number, coin.cost)
            return Response(status=ActionStatus.success)
        except Exception as e:
            return Response(status=ActionStatus.fail)
        
    def get_coin_balance(self, symbol: str) -> float:
        coin = self.asset.coins.get(symbol)
        if coin is not None:
            return coin.number
        else:
            return 0.0
    
    def add_trade(self, trade_signal: TradeRequest):
        cost = self.get_cost(trade_signal.bridgecoin_name)
        trade_response = self.update_trade_with_asset(trade_signal)
        if trade_response.status == 'success':
            self.trade_history.append(trade_signal)
            if trade_signal.action == 'sell':
                self.update_trade_metrics(cost, [trade_signal], self.metrics)
        return trade_response, self.metrics
        
    def update_trade_with_asset(self, trade_signal: TradeRequest):
        if trade_signal.action == 'buy':
            if self.check_balance(symbol=trade_signal.bridgecoin_name, number=trade_signal.price * trade_signal.number):
                self.asset.withdraw(symbol=trade_signal.bridgecoin_name, number=trade_signal.price * trade_signal.number)
                coin = Coin(symbol=trade_signal.symbol, number=trade_signal.number, cost=trade_signal.price)
                try:
                    self.deposit(coin)
                    return Response(status=ActionStatus.success)
                except Exception as e:
                    return Response(status=ActionStatus.fail)
            else:
                return Response(status=ActionStatus.fail)
        elif trade_signal.action == 'sell':
            if self.check_balance(symbol=trade_signal.symbol, number=trade_signal.number):
                self.asset.withdraw(symbol=trade_signal.symbol, number=trade_signal.number)
                coin = Coin(symbol=trade_signal.bridgecoin_name, number=trade_signal.price * trade_signal.number, cost=trade_signal.price)
                try:
                    self.deposit(coin)
                    return Response(status=ActionStatus.success)
                except Exception as e:
                    return Response(status=ActionStatus.fail)
            else:
                return Response(status=ActionStatus.fail)
        else:
            raise ValueError(f'Invalid action: {trade_signal.action}')

    def check_balance(self, symbol: str, number: int) -> bool:
        return self.asset.is_balance_enough(symbol, number)
    
    def update_trade_metrics(self, cost, trade_history, metrics):
        self.metrics = self.evaluator.calculate_aggregated_metrics(cost, trade_history, metrics)