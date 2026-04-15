from abc import ABC, abstractmethod

class BaseTrader(ABC):
    """
    Abstract base class for traders.
    This class serves as a template for all specific trader implementations.
    """

    @abstractmethod
    def buy(self, symbol: str, amount: float):
        """
        Buys a certain amount of a given symbol.
        """
        pass

    @abstractmethod
    def sell(self, symbol: str, amount: float):
        """
        Sells a certain amount of a given symbol.
        """
        pass

    @abstractmethod
    def get_balance(self) -> float:
        """
        Returns the current account balance.
        """
        pass

    @abstractmethod
    def get_positions(self) -> dict:
        """
        Returns the current open positions.
        """
        pass

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage for a symbol.

        Default implementation is a no-op that returns success so that
        non-futures traders (e.g. spot) and test stubs work without override.
        Override in subclasses that support leverage (e.g. BinanceTrader).
        """
        return {'success': True, 'leverage': leverage, 'cached': False}
