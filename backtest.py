import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import List, Type

import arcticdb as adb
from tqdm import tqdm

from src.backtset.wallet import BaseWallet, Coin
from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader


@dataclass
class BacktestResult:
    symbol: str
    total_return_pct: float
    trade_records: List[dict]


def run_backtest(
    symbol: str,
    strategy_cls: Type,
    start: datetime,
    end: datetime,
    lookback: int,
    usdt_balance: float
) -> BacktestResult:
    print(f'Backtesting {symbol}')
    lib = adb.Arctic("lmdb://arctic_database")['BinanceSpot']
    DBobject = lib.read(symbol, date_range=(start, end))

    strategy = strategy_cls(lookback=lookback, symbol=symbol)
    wallet = BaseWallet()
    wallet.deposit(Coin(symbol='USDT', number=usdt_balance, cost=1))

    for tick in DBobject.data.iterrows():
        strategy.on_tick(*tick)

    total_earn = sum(trade['earn'] for trade in strategy.trade_records)
    return BacktestResult(
        symbol=symbol,
        total_return_pct=total_earn * 100,
        trade_records=strategy.trade_records,
    )


def main():
    args = parse_args()
    lib = adb.Arctic("lmdb://arctic_database")['BinanceSpot']
    coin_list = args.coins or lib.list_symbols()
    start_time = datetime.fromisoformat(args.start)
    end_time = datetime.fromisoformat(args.end)

    strategy_cls = DynamicBreakoutTrader  # ✅ 這裡可以改成別的策略 class

    st = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {
            executor.submit(
                run_backtest,
                symbol,
                strategy_cls=strategy_cls,
                start=start_time,
                end=end_time,
                lookback=args.lookback,
                usdt_balance=args.usdt
            ): symbol for symbol in coin_list
        }

        for future in tqdm(futures, desc="Backtesting all symbols"):
            result = future.result()
            results.append(result)

    results.sort(key=lambda r: r.total_return_pct, reverse=True)
    elapsed_time = time.time() - st

    print("\n=== Backtest Summary ===")
    for res in results:
        print(f'{res.symbol}: {res.total_return_pct:.2f} %')
    avg_return = sum(r.total_return_pct for r in results) / len(results)
    print(f'Average Return: {avg_return:.2f} %')
    print(10*'-')
    print(f'Total Time: {elapsed_time:.2f} seconds')
    print(f'Average Time per Symbol: {elapsed_time / len(results):.2f} seconds')


def parse_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--coins', nargs='*', help='List of coin symbols (default: all)')
    parser.add_argument('--start', type=str, default='2024-09-01T00:00', help='Start time (ISO format)')
    parser.add_argument('--end', type=str, default='2025-03-30T00:00', help='End time (ISO format)')
    parser.add_argument('--lookback', type=int, default=60, help='Lookback window for strategy')
    parser.add_argument('--usdt', type=float, default=10000, help='Initial USDT balance')
    parser.add_argument('--threads', type=int, default=4, help='Number of threads')
    return parser.parse_args()


if __name__ == '__main__':
    main()
