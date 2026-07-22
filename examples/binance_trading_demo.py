"""Minimal command-line helper to exercise BinanceTrader spot and futures flows.

Usage examples (testnet recommended):

    export BINANCE_API_KEY="your_testnet_key"
    export BINANCE_API_SECRET="your_testnet_secret"
    python -m examples.binance_trading_demo balance --account spot
    python -m examples.binance_trading_demo order spot --symbol BTCUSDT --side BUY --quantity 0.001
    python -m examples.binance_trading_demo order futures --symbol BTCUSDT --side BUY --quantity 0.001 --reduce-only

Run with ``--help`` for the complete option list. All requests default to Binance
Testnet endpoints unless ``--live`` is provided explicitly.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

from src.trader.binance_trader import BinanceAPIException, BinanceTrader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Interact with Binance via BinanceTrader.')
    parser.add_argument(
        '--live',
        action='store_true',
        help='Use production Binance endpoints. Defaults to testnet for safety.',
    )
    parser.add_argument(
        '--rsa-key-path',
        help='Path to PEM-formatted RSA private key for RSA signatures (optional).',
    )
    parser.add_argument(
        '--rsa-key-passphrase',
        help='Passphrase for the RSA private key, if encrypted.',
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    balance_parser = subparsers.add_parser('balance', help='Fetch account balances.')
    balance_parser.add_argument('--account', choices=['spot', 'futures'], default='spot')

    positions_parser = subparsers.add_parser('positions', help='Fetch open positions.')
    positions_parser.add_argument('--account', choices=['spot', 'futures'], default='spot')

    order_parser = subparsers.add_parser('order', help='Submit an order.')
    order_parser.add_argument('market', choices=['spot', 'futures'])
    order_parser.add_argument('--symbol', required=True)
    order_parser.add_argument('--side', required=True, choices=['BUY', 'SELL', 'buy', 'sell'])
    order_parser.add_argument('--quantity', type=float, required=True)
    order_parser.add_argument('--price', type=float)
    order_parser.add_argument('--order-type', default=None)
    order_parser.add_argument('--time-in-force', default=None)
    order_parser.add_argument('--quote-order-qty', type=float)
    order_parser.add_argument('--position-side', default=None)
    order_parser.add_argument('--reduce-only', action='store_true')

    return parser


def require_credentials(expect_secret: bool) -> Dict[str, Optional[str]]:
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    if not api_key or not api_secret:
        if expect_secret:
            sys.exit('BINANCE_API_KEY and BINANCE_API_SECRET environment variables are required.')
    return {'api_key': api_key, 'api_secret': api_secret}


def pretty_print(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    sys.stdout.flush()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    use_rsa = bool(args.rsa_key_path)
    credentials = require_credentials(expect_secret=not use_rsa)
    rsa_key_bytes = None
    if args.rsa_key_path:
        with open(args.rsa_key_path, 'rb') as handle:
            rsa_key_bytes = handle.read()
    trader = BinanceTrader(
        credentials['api_key'],
        credentials.get('api_secret'),
        use_testnet=not args.live,
        rsa_private_key=rsa_key_bytes,
        rsa_private_key_password=args.rsa_key_passphrase,
    )

    try:
        if args.command == 'balance':
            pretty_print(trader.get_balance(args.account))
        elif args.command == 'positions':
            pretty_print(trader.get_positions(args.account))
        elif args.command == 'order':
            if args.market == 'spot':
                result = trader.buy(
                    args.symbol,
                    args.quantity,
                    price=args.price,
                    order_type=args.order_type,
                    quote_order_qty=args.quote_order_qty,
                    time_in_force=args.time_in_force,
                ) if args.side.upper() == 'BUY' else trader.sell(
                    args.symbol,
                    args.quantity,
                    price=args.price,
                    order_type=args.order_type,
                    quote_order_qty=args.quote_order_qty,
                    time_in_force=args.time_in_force,
                )
            else:
                if args.side.upper() == 'BUY':
                    result = trader.open_futures_position(
                        args.symbol,
                        'BUY',
                        args.quantity,
                        price=args.price,
                        order_type=args.order_type,
                        position_side=args.position_side,
                        reduce_only=args.reduce_only,
                        time_in_force=args.time_in_force,
                    )
                else:
                    result = trader.open_futures_position(
                        args.symbol,
                        'SELL',
                        args.quantity,
                        price=args.price,
                        order_type=args.order_type,
                        position_side=args.position_side,
                        reduce_only=args.reduce_only,
                        time_in_force=args.time_in_force,
                    )
            pretty_print(result)
        else:
            parser.error('Unsupported command')
    except BinanceAPIException as exc:  # pragma: no cover - defensive logging path
        sys.exit(f'Binance API error: {exc.message} (code={exc.error_code})')


if __name__ == '__main__':
    main()
