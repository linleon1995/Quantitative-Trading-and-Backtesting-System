from abc import ABC, abstractmethod
from typing import List, Any
from statemachine import State, StateMachine

from src.data_process.data_structure import GeneralTickData

# TODO: Refine Signal type, e.g. using a dataclass with fields like type: str and details: dict
Signal = Any


class Strategy(ABC):
    """
    Interface for trading strategies.
    """

    def initialize(self, config: dict) -> None:
        """
        Initializes the strategy with the given configuration.
        This method is called once before the strategy starts handling data.
        Args:
            config: A dictionary containing configuration parameters for the strategy.
        """
        pass

    @abstractmethod
    def handle_data(self, product_id: str, data: Any, product_state: 'ProductState') -> List[Signal]:
        """
        Processes incoming market data and generates trading signals.
        Args:
            product_id: The identifier of the product.
            data: The incoming market data.
            product_state: The current state of the product.
        Returns:
            A list of trading signals.
        """
        pass


# Keep Strategy stateless and make sure StrategyExecuter taking good care of it.
# Legacy component
class StrategyExecuter:
    def run(self, tic):
        self.collect(tic)
        trade_signal = self.strategy()
        return trade_signal

    def collect(self):
        pass

    def strategy(self):
        pass


class TestStateMachine(StateMachine):
    s0 = State(initial=True)
    s1 = State()
    s2 = State()
    s3 = State()
    s4 = State()

    steady = (
        s0.to(s1, cond='price_stable')
        | s0.to(s0, unless='price_stable')
    )
    rampup = (
        s1.to(s2, cond='price_rising')
        | s1.to(s0, unless='price_stable')
        | s1.to(s1, cond='price_stable')
    )
    buy = (
        s2.to(s3, cond='buy_complete')
        | s2.to(s2, unless='buy_complete')
    )
    break_last_low = (
        s3.to(s0, cond='sell_complete')
        | s3.to(s3, unless='sell_complete')
    )
    sell = (
        s4.to(s0, cond='sell_complete')
        | s4.to(s4, unless='sell_complete')
    )
    run = steady | rampup | buy | break_last_low | sell

    def __init__(self, data_queue: GeneralTickData):
        self.data_queue = data_queue
        self.stable_count = 0
        super(TestStateMachine, self).__init__()
        # self.allow_event_without_transition = True

    def receive(self, price, timestamp, trade_result=None):
        print('receive')
        self.data_queue.put_tick(tick=price, unix_time=timestamp)
        self.run()
    
    def receive_trade_response(self, trade_response):
        if trade_response.result == 'buy success':
            self.buy_success = True
        elif trade_response.result == 'sell success':
            self.sell_success = True
        else:
            raise ValueError('Invalid trade response.')

    # TODO: std, time range to decide, consider Bollinger Bands
    def price_stable(self): 
        latest_price = self.data_queue.latest_price
        upper_bound = self.data_queue.bollinger_band.upper_bound
        lower_bound = self.data_queue.bollinger_band.lower_bound
        if latest_price < upper_bound and upper_bound > lower_bound:
            self.stable_count += 1
        else:
            self.stable_count = 0
        if self.stable_count > 120:
            return True
        else:
            return False
    
    def price_rising(self):
        if self.data_queue.slope > 0.1:
            return True
        else:
            return False
    
    def buy_complete(self):
        self.buy_success = False
        return True
    
    def sell_complete(self):
        self.sell_success = False
        return True
