from typing import List, Any, Callable, Dict

from src.strategies.base_strategy import Strategy
# ProductState is forward-referenced in Strategy, but we might use it for type hints here
# or in the TODO section, so importing it is fine.
from src.data_process.product_state import ProductState


class MockStrategy(Strategy):
    """
    A mock implementation of the Strategy interface for testing purposes.
    Allows configuring return values for handle_data and tracking calls.
    """

    def __init__(self, name: str, signals_to_return: List[Any] = None, on_handle_data_callback: Callable = None):
        """
        Initializes the MockStrategy.

        Args:
            name: A name for this mock strategy instance, useful for debugging.
            signals_to_return: A list of signals that handle_data will return.
            on_handle_data_callback: An optional callback function that will be invoked
                                     when handle_data is called. It receives
                                     (product_id, data, product_state).
        """
        self.name = name
        self.signals_to_return = signals_to_return if signals_to_return is not None else []
        self.on_handle_data_callback = on_handle_data_callback
        self.initialize_called_with: Dict[str, Any] = None
        self.handle_data_calls: List[Dict[str, Any]] = []

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Mock initialize method. Stores the config it was called with.
        """
        self.initialize_called_with = config
        print(f"MockStrategy {self.name}: initialized with {config}")

    def handle_data(self, product_id: str, data: Any, product_state: 'ProductState') -> List[Any]:
        """
        Mock handle_data method. Records the call, optionally invokes a callback,
        and returns predefined signals.

        Args:
            product_id: The product identifier.
            data: The market data.
            product_state: The current state of the product.

        Returns:
            A list of signals (as configured during initialization).
        """
        # Store the type of product_state to avoid issues with comparing complex objects
        # directly in assertions for now, and to simplify mock call verification.
        self.handle_data_calls.append({
            'product_id': product_id,
            'data': data,
            'product_state_type': type(product_state),
            'product_state_id': product_state.product_id if product_state else None
        })
        print(f"MockStrategy {self.name}: handle_data called for {product_id} with data {data}")

        if self.on_handle_data_callback:
            self.on_handle_data_callback(product_id, data, product_state)

        return self.signals_to_return


# TODO: Add helper functions or fixtures for creating MockProductState instances
# if direct instantiation of ProductState becomes cumbersome for tests.
# from src.data_process.product_state import ProductState
# def create_mock_product_state(product_id: str, initial_market_data: Any = None, initial_trading_state: Dict = None) -> ProductState:
#     ps = ProductState(product_id)
#     if initial_market_data:
#         ps.update_market_data(initial_market_data)
#     if initial_trading_state:
#         for k, v in initial_trading_state.items():
#             ps.update_trading_state(k, v)
#     return ps
