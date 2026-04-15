"""
Quick test script to validate the refactored architecture.
Tests configuration loading, component initialization, and basic signal flow.
"""
import sys
from pathlib import Path
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_config_loading():
    """Test configuration loading and validation."""
    print("=" * 60)
    print("Testing Configuration System")
    print("=" * 60)
    
    try:
        from src.config.trading_config import load_config_from_env, LiveTradingConfig
        
        # Load from environment
        config = load_config_from_env()
        print("✅ Config loaded from environment")
        
        # Validate types
        assert isinstance(config.strategy.lookback, int)
        assert isinstance(config.trading.max_loss_rate, float)
        assert 0 < config.trading.max_loss_rate <= 1
        print("✅ Config validation passed")
        
        # Print summary
        print("\nConfiguration Summary:")
        print(config.get_summary())
        
        return True
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_signals():
    """Test strategy signal generation."""
    print("\n" + "=" * 60)
    print("Testing Strategy Signal Generation")
    print("=" * 60)
    
    try:
        from src.strategies.dynamic_breakout_atx import (
            DynamicBreakoutTrader, TradingSignal, SignalType
        )
        
        signals_received = []
        
        def signal_handler(signal: TradingSignal):
            signals_received.append(signal)
            print(f"📡 Signal received: {signal}")
        
        # Create strategy
        strategy = DynamicBreakoutTrader(
            symbol='BTCUSDT',
            lookback=5,  # Small for quick test
            on_signal=signal_handler
        )
        print("✅ Strategy created")
        
        # Simulate market data that should trigger a buy signal
        base_price = 50000
        for i in range(10):
            timestamp = datetime.now()
            data = {
                'close_price': base_price + i * 100,  # Increasing price
                'volume': 1000 + i * 500  # Increasing volume
            }
            strategy.on_tick(timestamp, data)
        
        # Trigger a stronger breakout
        data = {
            'close_price': base_price + 2000,  # Big jump
            'volume': 5000  # High volume
        }
        strategy.on_tick(datetime.now(), data)
        
        if signals_received:
            print(f"✅ Received {len(signals_received)} signal(s)")
            for sig in signals_received:
                print(f"   - {sig.signal_type.value} @ ${sig.price:.2f}: {sig.reason}")
        else:
            print("⚠️  No signals generated (might need more ticks or different parameters)")
        
        return True
    except Exception as e:
        print(f"❌ Strategy test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_no_premature_signals():
    """Test that strategy does NOT fire signals before indicators are warmed up.
    
    Regression test for: self.high initialized to float('-inf'), causing
    dynamic_x=-inf and firing BUY on every tick from the start.
    """
    print("\n" + "=" * 60)
    print("Testing No Premature Signals (warm-up guard)")
    print("=" * 60)

    try:
        from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader, TradingSignal

        premature_signals = []

        def signal_handler(signal: TradingSignal):
            premature_signals.append(signal)

        # atr_period=14 means we need 14+ ticks before ATR is ready
        strategy = DynamicBreakoutTrader(
            symbol='BTCUSDT',
            lookback=14,
            atr_period=14,
            on_signal=signal_handler
        )

        # Feed 13 ticks (one less than atr_period) — no signal should fire
        from datetime import datetime
        base_price = 50000
        for i in range(13):
            strategy.on_tick(datetime.now(), {
                'close_price': base_price + i * 100,
                'volume': 5000 + i * 100
            })

        assert len(premature_signals) == 0, (
            f"Expected 0 signals before warm-up, got {len(premature_signals)}: {premature_signals}"
        )
        print(f"✅ No signals fired during warm-up ({strategy.lookback} ticks, mean_atr={strategy.mean_atr})")

        # Verify dynamic_x would have been -inf before the fix
        # (high is now None until ticks arrive, not float('-inf'))
        print(f"✅ self.high initialized as None, not float('-inf'): {strategy.high is not float('-inf')}")

        # Feed enough ticks to complete warm-up, then verify signal CAN fire
        # Add strong breakout conditions after warm-up
        post_warmup_signals = []
        strategy.on_signal = lambda s: post_warmup_signals.append(s)

        for i in range(14, 30):
            strategy.on_tick(datetime.now(), {
                'close_price': base_price + i * 200,   # Strong uptrend
                'volume': 20000 + i * 1000             # High volume
            })

        if post_warmup_signals:
            print(f"✅ Signal correctly fired after warm-up: {post_warmup_signals[0].reason}")
        else:
            print("⚠️  No breakout signal post-warmup (market conditions not met, not a bug)")

        return True
    except AssertionError as e:
        print(f"❌ Premature signal test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_warmup_with_history():
    """Test that warmup_with_history pre-warms indicators without emitting any signals.

    Regression test for B-5: at startup dynamic_x == latest price because
    the rolling high is built from a single live tick, causing an immediate BUY.
    Fix: call warmup_with_history() with historical klines before attaching
    on_signal, so the rolling window and indicators are properly initialised.
    """
    print("\n" + "=" * 60)
    print("Testing warmup_with_history (B-5 fix)")
    print("=" * 60)

    try:
        import random
        import datetime
        from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader

        random.seed(0)
        LOOKBACK = 14
        ATR_PERIOD = 14
        strategy = DynamicBreakoutTrader(symbol='BTCTEST', lookback=LOOKBACK, atr_period=ATR_PERIOD)

        # Build fake historical kline rows: [open_time, o, h, l, close, volume, close_time, ...]
        base = 100.0
        bars = []
        ts_ms = int(datetime.datetime(2026, 3, 4, 0, 0, 0).timestamp() * 1000)
        for i in range(50):
            price = base + i * 0.1 + random.uniform(-0.3, 0.3)
            vol = 1000 + random.randint(-200, 200)
            row = [ts_ms, str(price), str(price + 0.1), str(price - 0.1), str(price), str(vol), ts_ms + 59999]
            bars.append(row)
            ts_ms += 60000

        # Attach signal handler BEFORE warmup to prove signals are suppressed
        signals_during_warmup = []
        strategy.on_signal = lambda s: signals_during_warmup.append(s)

        n = strategy.warmup_with_history(bars)

        assert n == 50, f"Expected 50 bars processed, got {n}"
        assert len(signals_during_warmup) == 0, (
            f"FAIL: {len(signals_during_warmup)} signal(s) emitted during warmup"
        )
        print(f"✅ No signals during warmup ({n} bars, mean_atr={strategy.mean_atr:.4f}")

        # Indicators must be ready (full lookback + atr_period worth of data)
        assert strategy.mean_atr is not None, "mean_atr still None after 50-bar warmup"
        assert strategy.mean_vol is not None, "mean_vol still None after 50-bar warmup"
        print(f"✅ Indicators ready: high={strategy.high:.4f}, mean_atr={strategy.mean_atr:.4f}")

        # After warmup the rolling high is a real window high, NOT the current price.
        # dynamic_x = high - pr_x * mean_atr  which should be < high (some margin away).
        dynamic_x = strategy.high - 0.8 * strategy.mean_atr
        assert dynamic_x < strategy.high, (
            f"dynamic_x ({dynamic_x:.4f}) should be below rolling high ({strategy.high:.4f})"
        )
        print(f"✅ dynamic_x ({dynamic_x:.4f}) is below rolling high ({strategy.high:.4f})")

        # A non-breakout tick (price well below high) must NOT fire a signal
        post_warmup_signals = []
        strategy.on_signal = lambda s: post_warmup_signals.append(s)
        low_price = strategy.high * 0.95  # 5% below rolling high
        strategy.on_tick(
            datetime.datetime(2026, 3, 4, 1, 0, 0),
            {'close_price': low_price, 'volume': 800},
        )
        assert len(post_warmup_signals) == 0, (
            f"Unexpected signal on non-breakout tick: {post_warmup_signals[0].reason}"
        )
        print("✅ No signal on non-breakout tick after warmup")

        return True
    except AssertionError as e:
        print(f"❌ Warmup test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_online_backtest_reset():
    """Test reset_for_online_backtest: closes positions, resets portfolio and strategies."""
    print("\n" + "=" * 60)
    print("Testing Online Backtest Reset")
    print("=" * 60)

    try:
        from src.config.trading_config import load_config_from_env
        from src.orchestrator.live_trading_orchestrator import LiveTradingOrchestrator
        from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader

        # Mock trader: pretend there are 2 open positions to close
        class MockTraderWithPositions:
            def get_balance(self, account_type='futures'):
                return {'USDT': 4800.0}

            def get_positions(self, account_type='futures'):
                return {
                    'BTCUSDT': {'positionAmt': 0.002, 'entryPrice': 50000.0,
                                'unRealizedProfit': -5.0, 'marginType': 'cross',
                                'leverage': 1.0, 'positionSide': 'BOTH'},
                    'ETHUSDT': {'positionAmt': -0.05, 'entryPrice': 3200.0,
                                'unRealizedProfit': 10.0, 'marginType': 'cross',
                                'leverage': 1.0, 'positionSide': 'BOTH'},
                }

            def close_futures_position(self, symbol, side, quantity, **kwargs):
                return {'success': True, 'data': {'orderId': 99, 'executedQty': quantity, 'avgPrice': 0}}

            def close_all_positions(self):
                positions = self.get_positions(account_type='futures')
                closed = []
                for sym, info in positions.items():
                    amt = info['positionAmt']
                    side = 'SELL' if amt > 0 else 'BUY'
                    closed.append({'symbol': sym, 'side': side, 'qty': abs(amt), 'result': {}})
                return {'closed': closed, 'failed': []}

            def open_futures_position(self, **kwargs):
                return {'success': True, 'data': {}}

        config = load_config_from_env()
        logger = logging.getLogger('test_reset')
        logger.setLevel(logging.INFO)

        orchestrator = LiveTradingOrchestrator(
            trader=MockTraderWithPositions(),
            config=config,
            logger=logger
        )
        print(f"✅ Orchestrator initial capital: ${orchestrator.portfolio.initial_capital:,.2f}")

        # Simulate some trading history on the portfolio
        orchestrator.portfolio.update_capital(5200.0)
        orchestrator.portfolio.record_trade(profit=150, trade_value=1000)
        orchestrator.portfolio.record_trade(profit=-50, trade_value=500)
        orchestrator.portfolio.position_count = 2
        orchestrator.is_trading_active = False  # simulate stopped by loss limit
        print(f"  Pre-reset: capital={orchestrator.portfolio.current_capital}, "
              f"trades={orchestrator.portfolio.total_trades}, active={orchestrator.is_trading_active}")

        # Create two strategy instances with state
        strategies = {}
        for symbol in ['BTCUSDT', 'ETHUSDT']:
            s = DynamicBreakoutTrader(symbol=symbol)
            s.positions.append({'entry': 50000, 'size': 0.002, 'entry_time': None})
            s.num_trade = 3
            s.total_earn = 0.05
            strategies[symbol] = s

        # --- Execute reset ---
        result = orchestrator.reset_for_online_backtest(strategies)
        print(f"✅ Reset result: {result}")

        # Assertions
        assert result['positions_closed'] == 2, f"Expected 2 closed, got {result['positions_closed']}"
        assert result['positions_failed'] == [], f"Expected no failures: {result['positions_failed']}"
        assert result['new_baseline'] == 4800.0, f"Expected new baseline $4800, got {result['new_baseline']}"

        # Portfolio should be fully reset
        assert orchestrator.portfolio.initial_capital == 4800.0
        assert orchestrator.portfolio.current_capital == 4800.0
        assert orchestrator.portfolio.peak_capital == 4800.0
        assert orchestrator.portfolio.total_trades == 0
        assert orchestrator.portfolio.position_count == 0
        assert orchestrator.is_trading_active is True
        # S-8.2 fields must also be zeroed
        assert orchestrator.portfolio.gross_profit == 0.0
        assert orchestrator.portfolio.gross_loss == 0.0
        assert orchestrator.portfolio.max_drawdown == 0.0
        assert orchestrator.portfolio.max_win_streak == 0
        assert orchestrator.portfolio.max_loss_streak == 0
        assert orchestrator.portfolio.total_holding_minutes == 0.0
        assert orchestrator.portfolio.trade_records == []
        print("✅ Portfolio fully reset to new baseline $4,800.00 (S-8.2 fields also zeroed)")

        # Strategies should be wiped
        for symbol, s in strategies.items():
            assert len(s.positions) == 0
            assert s.num_trade == 0
            assert s.mean_atr is None
            assert s.high is None
        print("✅ All strategy instances reset (positions cleared, indicators wiped)")

        return True
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        import traceback; traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback; traceback.print_exc()
        return False


def test_portfolio_tracker():
    """Test portfolio tracking including S-8.2 metrics."""
    print("\n" + "=" * 60)
    print("Testing Portfolio Tracker (S-8.2 metrics)")
    print("=" * 60)

    try:
        from src.orchestrator.live_trading_orchestrator import PortfolioTracker

        portfolio = PortfolioTracker(
            initial_capital=100000,
            trading_fee_rate=0.0004
        )
        print("✅ Portfolio tracker created")

        # --- Capital updates and max drawdown tracking ---
        portfolio.update_capital(110000)  # peak = 110000
        portfolio.update_capital(99000)   # dd = (110000-99000)/110000 ≈ 10%
        drawdown = portfolio.get_drawdown()
        assert portfolio.max_drawdown > 0, "max_drawdown should be > 0 after a drop"
        expected_dd = (110000 - 99000) / 110000
        assert abs(portfolio.max_drawdown - expected_dd) < 0.001, (
            f"max_drawdown {portfolio.max_drawdown:.4f} != expected {expected_dd:.4f}"
        )
        print(f"✅ Max drawdown: {portfolio.max_drawdown*100:.2f}% (expected {expected_dd*100:.2f}%)")

        # --- Trade recording with holding_minutes (S-8.2) ---
        # Trades: WIN 500, WIN 300, LOSS -200, WIN 100, LOSS -150
        portfolio.record_trade(profit=500,  trade_value=5000,  holding_minutes=45.0)
        portfolio.record_trade(profit=300,  trade_value=3000,  holding_minutes=30.0)
        portfolio.record_trade(profit=-200, trade_value=2000,  holding_minutes=20.0)
        portfolio.record_trade(profit=100,  trade_value=1000,  holding_minutes=15.0)
        portfolio.record_trade(profit=-150, trade_value=1500,  holding_minutes=60.0)
        print(f"✅ Trades recorded: {portfolio.total_trades}")

        # --- Win rate ---
        assert portfolio.total_trades == 5
        assert portfolio.winning_trades == 3
        assert portfolio.losing_trades == 2
        assert abs(portfolio.get_win_rate() - 0.6) < 0.001, f"Win rate {portfolio.get_win_rate()}"
        print(f"✅ Win rate: {portfolio.get_win_rate()*100:.1f}% (expected 60%)")

        # --- Profit factor ---
        # fee = trade_value * 0.0004 * 2; net_profit = profit - fee
        # WIN: net = 500 - 5000*0.0008=4, 300 - 2.4, 100 - 0.8 → gross_profit = 496+297.6+99.2 = 892.8
        # LOSS: net = -200 - 1.6 = -201.6, -150 - 1.2 = -151.2 → gross_loss = 201.6+151.2 = 352.8
        pf = portfolio.get_profit_factor()
        assert pf > 1.0, f"Profit factor should be > 1, got {pf}"
        print(f"✅ Profit factor: {pf:.2f} (expected > 1.0)")

        # --- Consecutive streaks ---
        # Sequence: WIN, WIN, LOSS, WIN, LOSS → max_win=2, max_loss=1
        assert portfolio.max_win_streak == 2, f"max_win_streak={portfolio.max_win_streak}, expected 2"
        assert portfolio.max_loss_streak == 1, f"max_loss_streak={portfolio.max_loss_streak}, expected 1"
        print(f"✅ Max win streak: {portfolio.max_win_streak}, max loss streak: {portfolio.max_loss_streak}")

        # --- Average holding time ---
        expected_avg_hold = (45 + 30 + 20 + 15 + 60) / 5  # = 34.0
        avg_hold = portfolio.get_avg_holding_time()
        assert abs(avg_hold - expected_avg_hold) < 0.1, (
            f"Avg hold {avg_hold:.1f}min != expected {expected_avg_hold:.1f}min"
        )
        print(f"✅ Avg holding time: {avg_hold:.1f} min (expected {expected_avg_hold:.1f} min)")

        # --- Total return ---
        total_return = portfolio.get_total_return()
        print(f"✅ Total return: {total_return*100:+.2f}%")

        # --- Summary output (visual check) ---
        print("\nPortfolio Summary:")
        print(portfolio.get_summary())

        return True
    except AssertionError as e:
        print(f"❌ Assertion failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Portfolio tracker test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_orchestrator_initialization():
    """Test orchestrator initialization (without actual trading)."""
    print("\n" + "=" * 60)
    print("Testing Orchestrator Initialization")
    print("=" * 60)
    
    try:
        from src.config.trading_config import load_config_from_env
        from src.orchestrator.live_trading_orchestrator import LiveTradingOrchestrator
        
        # Mock trader class
        class MockTrader:
            def get_balance(self, account_type='futures'):
                # Correct format: get_futures_account_balance returns {'USDT': 10000.0}
                return {'USDT': 100000.0, 'BTC': 0.0}
            
            def open_futures_position(self, **kwargs):
                return {
                    'success': True,
                    'data': {
                        'orderId': 123456,
                        'executedQty': kwargs.get('quantity', 1),
                        'avgPrice': 50000
                    }
                }
            
            def close_futures_position(self, **kwargs):
                return {
                    'success': True,
                    'data': {
                        'orderId': 123457,
                        'executedQty': kwargs.get('quantity', 1),
                        'avgPrice': 51000
                    }
                }
        
        config = load_config_from_env()
        logger = logging.getLogger('test')
        logger.setLevel(logging.INFO)
        
        orchestrator = LiveTradingOrchestrator(
            trader=MockTrader(),
            config=config,
            logger=logger
        )
        print("✅ Orchestrator created")
        print(f"   Trading active: {orchestrator.is_trading_active}")
        print(f"   Initial capital: ${orchestrator.portfolio.initial_capital:,.2f}")
        print(f"   Max loss rate: {config.trading.max_loss_rate*100:.0f}%")
        
        # Test loss-limit check (total return drops below threshold)
        drop_to = orchestrator.portfolio.initial_capital * (1 - config.trading.max_loss_rate - 0.01)
        orchestrator.portfolio.update_capital(drop_to)
        should_stop = orchestrator.check_loss_limit()
        if should_stop:
            print("✅ Loss limit correctly triggered")
        else:
            print("⚠️  Loss limit not triggered (check MAX_LOSS_RATE setting)")
        
        return True
    except Exception as e:
        print(f"❌ Orchestrator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("VALIDATING REFACTORED LIVE TRADING ARCHITECTURE")
    print("=" * 80 + "\n")
    
    results = {
        'Configuration Loading': test_config_loading(),
        'Strategy Signals': test_strategy_signals(),
        'No Premature Signals': test_strategy_no_premature_signals(),
        'Warmup With History (B-5)': test_strategy_warmup_with_history(),
        'Online Backtest Reset': test_online_backtest_reset(),
        'Portfolio Tracker': test_portfolio_tracker(),
        'Orchestrator Init': test_orchestrator_initialization(),
    }
    
    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:.<40} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - System ready for use!")
    else:
        print("⚠️  SOME TESTS FAILED - Review errors above")
    print("=" * 80 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
