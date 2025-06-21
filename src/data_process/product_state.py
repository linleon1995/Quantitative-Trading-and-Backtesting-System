from typing import Any, Dict

class ProductState:
    """
    Manages the state of a specific product, including market data and trading status.
    """
    def __init__(self, product_id: str):
        """
        Initializes the ProductState.
        Args:
            product_id: The identifier of the product.
        """
        self.product_id: str = product_id
        # TODO: Consider integrating GeneralTickData or similar for more structured time-series data management.
        self.market_data: Dict[str, Any] = {}
        self.trading_state: Dict[str, Any] = {
            'position': 0.0,
            'open_orders': [],
            'pnl': 0.0
        }

    def update_market_data(self, data: Any) -> None:
        """
        Updates the market data for the product.
        Currently, it stores the latest raw data object under the key 'latest_data'.
        Args:
            data: The incoming market data.
        """
        self.market_data['latest_data'] = data

    def update_trading_state(self, key: str, value: Any) -> None:
        """
        Updates a specific part of the trading state.
        Args:
            key: The key of the trading state to update.
            value: The new value for the trading state.
        """
        self.trading_state[key] = value

    def get_market_data(self, key: str = 'latest_data') -> Any:
        """
        Retrieves market data associated with the given key.
        Args:
            key: The key for the desired market data. Defaults to 'latest_data'.
        Returns:
            The market data associated with the key, or None if the key doesn't exist.
        """
        return self.market_data.get(key)

    def get_trading_state(self, key: str) -> Any:
        """
        Retrieves a specific part of the trading state.
        Args:
            key: The key of the trading state to retrieve.
        Returns:
            The value of the trading state for the given key, or None if the key doesn't exist.
        """
        return self.trading_state.get(key)
