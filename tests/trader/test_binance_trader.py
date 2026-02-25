from unittest import TestCase
from unittest.mock import MagicMock, patch

from src.trader.binance_trader import BinanceTrader, BinanceAPIException


class TestBinanceTrader(TestCase):
    def setUp(self) -> None:
        patcher = patch('src.trader.binance_trader.BinanceAPI')
        self.addCleanup(patcher.stop)
        self.api_cls = patcher.start()
        self.api = MagicMock()
        self.api_cls.return_value = self.api

        # Default mocks
        self.api.create_spot_order.return_value = {'orderId': 1}
        self.api.create_futures_order.return_value = {'orderId': 2}
        self.api.get_spot_balances.return_value = {'USDT': 1000.0, 'BTC': 0.1}
        self.api.get_spot_positions.return_value = {'BTC': 0.1}
        self.api.get_futures_account_balance.return_value = {'USDT': 1000.0}
        self.api.get_futures_positions.return_value = []

        self.trader = BinanceTrader(api_key='test', api_secret='secret')

    def test_buy_limit_order_calls_api(self):
        result = self.trader.buy('BTCUSDT', 0.1, price=50000.0)

        self.api.create_spot_order.assert_called_once_with(
            symbol='BTCUSDT',
            side='BUY',
            order_type='LIMIT',
            quantity=0.1,
            quote_order_qty=None,
            price=50000.0,
            time_in_force='GTC',
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], {'orderId': 1})

    def test_sell_market_order_uses_quantity(self):
        result = self.trader.sell('ETHUSDT', 2.0)

        self.api.create_spot_order.assert_called_once_with(
            symbol='ETHUSDT',
            side='SELL',
            order_type='MARKET',
            quantity=2.0,
            quote_order_qty=None,
            price=None,
            time_in_force=None,
        )
        self.assertTrue(result['success'])

    def test_buy_handles_api_exception(self):
        self.api.create_spot_order.side_effect = BinanceAPIException(400, -2010, 'Account has insufficient balance for requested action.')

        result = self.trader.buy('BTCUSDT', 1.0, price=50000.0)

        self.assertFalse(result['success'])
        self.assertEqual(result['message'], 'Account has insufficient balance for requested action.')
        self.assertEqual(result['code'], -2010)

    def test_get_spot_balance_returns_raw_balances(self):
        balances = self.trader.get_balance('spot')
        self.assertEqual(balances, {'USDT': 1000.0, 'BTC': 0.1})

    def test_get_spot_balance_handles_exception(self):
        self.api.get_spot_balances.side_effect = BinanceAPIException(500, -1000, 'Server error')

        balances = self.trader.get_balance('spot')
        self.assertFalse(balances['success'])
        self.assertEqual(balances['message'], 'Server error')

    def test_get_futures_positions_normalizes(self):
        self.api.get_futures_positions.return_value = [
            {
                'symbol': 'BTCUSDT',
                'positionAmt': '0.01',
                'entryPrice': '30000.0',
                'unRealizedProfit': '12.5',
                'marginType': 'isolated',
                'leverage': '20',
                'positionSide': 'LONG',
            },
            {
                'symbol': 'ETHUSDT',
                'positionAmt': '0',
            },
        ]

        positions = self.trader.get_positions('futures')

        self.assertIn('BTCUSDT', positions)
        btc = positions['BTCUSDT']
        self.assertEqual(btc['positionAmt'], 0.01)
        self.assertEqual(btc['entryPrice'], 30000.0)
        self.assertEqual(btc['unRealizedProfit'], 12.5)
        self.assertEqual(btc['marginType'], 'isolated')
        self.assertEqual(btc['leverage'], 20.0)
        self.assertEqual(btc['positionSide'], 'LONG')
        self.assertNotIn('ETHUSDT', positions)

    def test_open_futures_position_calls_api(self):
        result = self.trader.open_futures_position('BTCUSDT', 'BUY', 0.01)

        self.api.create_futures_order.assert_called_once_with(
            symbol='BTCUSDT',
            side='BUY',
            order_type='MARKET',
            quantity=0.01,
            price=None,
            position_side=None,
            reduce_only=False,
            time_in_force=None,
        )
        self.assertTrue(result['success'])

    def test_close_futures_position_sets_reduce_only(self):
        self.trader.close_futures_position('BTCUSDT', 'SELL', 0.01, price=25000.0)

        self.api.create_futures_order.assert_called_once_with(
            symbol='BTCUSDT',
            side='SELL',
            order_type='LIMIT',
            quantity=0.01,
            price=25000.0,
            position_side=None,
            reduce_only=True,
            time_in_force='GTC',
        )

    def test_get_positions_spot_error(self):
        self.api.get_spot_positions.side_effect = BinanceAPIException(400, -1001, 'Error')

        response = self.trader.get_positions('spot')

        self.assertFalse(response['success'])
        self.assertEqual(response['code'], -1001)

    def test_web3_placeholders_still_operational(self):
        self.assertTrue(self.trader.connect_metamask())
        self.assertEqual(self.trader.metamask_address, 'mock_metamask_address_0x123')
        self.assertEqual(self.trader.get_web3_balance(), 1.5)
        self.assertEqual(self.trader.get_web3_balance(token_address='0xabc'), 5.0)


if __name__ == '__main__':
    import unittest

    unittest.main()
