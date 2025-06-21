import unittest
from typing import List, Any, Dict

from src.strategies.strategy_executor import StrategyExecutor
from src.data_process.product_state import ProductState
from tests.mocks import MockStrategy


class TestStrategyExecutor(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        self.executor = StrategyExecutor()
        self.mock_strategy1 = MockStrategy(name="Strat1")
        self.mock_strategy2 = MockStrategy(name="Strat2", signals_to_return=[{"action": "buy", "product": "BTCUSD"}])

    # Test Strategy Registration and ProductState Creation
    def test_register_single_strategy_single_product(self):
        self.executor.register_strategy(self.mock_strategy1, ["BTCUSD"])
        self.assertIn("BTCUSD", self.executor.strategies)
        self.assertIn(self.mock_strategy1, self.executor.strategies["BTCUSD"])
        self.assertIn("BTCUSD", self.executor.product_states)
        self.assertIsInstance(self.executor.product_states["BTCUSD"], ProductState)

    def test_register_single_strategy_multiple_products(self):
        self.executor.register_strategy(self.mock_strategy1, ["BTCUSD", "ETHUSD"])
        self.assertIn(self.mock_strategy1, self.executor.strategies["BTCUSD"])
        self.assertIn(self.mock_strategy1, self.executor.strategies["ETHUSD"])
        self.assertIn("BTCUSD", self.executor.product_states)
        self.assertIn("ETHUSD", self.executor.product_states)
        self.assertIsInstance(self.executor.product_states["BTCUSD"], ProductState)
        self.assertIsInstance(self.executor.product_states["ETHUSD"], ProductState)

    def test_register_multiple_strategies_single_product(self):
        self.executor.register_strategy(self.mock_strategy1, ["BTCUSD"])
        self.executor.register_strategy(self.mock_strategy2, ["BTCUSD"])
        self.assertEqual(len(self.executor.strategies["BTCUSD"]), 2)
        self.assertIn(self.mock_strategy1, self.executor.strategies["BTCUSD"])
        self.assertIn(self.mock_strategy2, self.executor.strategies["BTCUSD"])

    # Test get_product_state
    def test_get_product_state_existing(self):
        self.executor.register_strategy(self.mock_strategy1, ["BTCUSD"])  # Creates the state
        ps = self.executor.get_product_state("BTCUSD")
        self.assertIsInstance(ps, ProductState)
        self.assertEqual(ps.product_id, "BTCUSD")

    def test_get_product_state_new(self):
        ps = self.executor.get_product_state("ETHUSD")  # Should create on demand
        self.assertIn("ETHUSD", self.executor.product_states)
        self.assertIsInstance(ps, ProductState)
        self.assertEqual(ps.product_id, "ETHUSD")

    # Test on_market_data Basic Operation
    def test_on_market_data_updates_product_state(self):
        self.executor.register_strategy(self.mock_strategy1, ["BTCUSD"])
        market_data = {"price": 50000, "timestamp": 1234567890}
        self.executor.on_market_data("BTCUSD", market_data)
        product_state = self.executor.product_states["BTCUSD"]
        self.assertEqual(product_state.get_market_data('latest_data'), market_data)

    def test_on_market_data_calls_strategy_initialize_and_handle_data(self):
        self.executor.register_strategy(self.mock_strategy1, ["BTCUSD"])
        market_data = {"price": 51000}

        # Initial call to on_market_data
        self.executor.on_market_data("BTCUSD", market_data)
        self.assertIsNotNone(self.mock_strategy1.initialize_called_with)
        # Check if it's an empty dict as passed by StrategyExecutor
        self.assertEqual(self.mock_strategy1.initialize_called_with, {})
        self.assertEqual(len(self.mock_strategy1.handle_data_calls), 1)
        call_args = self.mock_strategy1.handle_data_calls[0]
        self.assertEqual(call_args['product_id'], "BTCUSD")
        self.assertEqual(call_args['data'], market_data)
        self.assertEqual(call_args['product_state_type'], ProductState)
        self.assertEqual(call_args['product_state_id'], "BTCUSD")

        # Second call to ensure initialize is not called again
        market_data2 = {"price": 51500}
        self.executor.on_market_data("BTCUSD", market_data2)
        # initialize_called_with should remain the same, not called again
        self.assertEqual(self.mock_strategy1.initialize_called_with, {})
        self.assertEqual(len(self.mock_strategy1.handle_data_calls), 2) # handle_data called again
        call_args2 = self.mock_strategy1.handle_data_calls[1]
        self.assertEqual(call_args2['data'], market_data2)


    def test_on_market_data_routes_to_correct_strategy(self):
        self.executor.register_strategy(self.mock_strategy1, ["BTCUSD"])
        self.executor.register_strategy(self.mock_strategy2, ["ETHUSD"])

        # Data for BTCUSD
        self.executor.on_market_data("BTCUSD", {"price": 52000})
        self.assertEqual(len(self.mock_strategy1.handle_data_calls), 1)
        self.assertEqual(len(self.mock_strategy2.handle_data_calls), 0)
        self.assertIsNotNone(self.mock_strategy1.initialize_called_with) # Strat1 initialized
        self.assertIsNone(self.mock_strategy2.initialize_called_with) # Strat2 not yet

        # Data for ETHUSD
        self.executor.on_market_data("ETHUSD", {"price": 4000})
        self.assertEqual(len(self.mock_strategy1.handle_data_calls), 1)  # Unchanged
        self.assertEqual(len(self.mock_strategy2.handle_data_calls), 1)
        self.assertIsNotNone(self.mock_strategy2.initialize_called_with) # Strat2 initialized now

    def test_on_market_data_collects_signals(self):
        self.executor.register_strategy(self.mock_strategy2, ["BTCUSD"])  # mock_strategy2 returns a signal
        signals = self.executor.on_market_data("BTCUSD", {"price": 53000})
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0], {"action": "buy", "product": "BTCUSD"})

    def test_on_market_data_no_strategies_for_product(self):
        # Market data for a product with no registered strategies
        signals = self.executor.on_market_data("DOGEUSD", {"price": 0.5})
        # ProductState should still be created
        self.assertIn("DOGEUSD", self.executor.product_states)
        self.assertIsInstance(self.executor.product_states["DOGEUSD"], ProductState)
        # No signals should be generated
        self.assertEqual(len(signals), 0)

    # Test Chain Mode Placeholder
    def test_run_chain_mode_for_product_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.executor.run_chain_mode_for_product("BTCUSD", {"price": 123})

if __name__ == '__main__':
    unittest.main()
