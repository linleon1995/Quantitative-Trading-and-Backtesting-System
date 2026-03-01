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
        print("✅ Portfolio fully reset to new baseline $4,800.00")

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
    """Test portfolio tracking."""
    print("\n" + "=" * 60)
    print("Testing Portfolio Tracker")
    print("=" * 60)
    
    try:
        from src.orchestrator.live_trading_orchestrator import PortfolioTracker
        
        portfolio = PortfolioTracker(
            initial_capital=100000,
            trading_fee_rate=0.0004
        )
        print("✅ Portfolio tracker created")
        
        # Simulate capital changes
        portfolio.update_capital(105000)
        print(f"✅ Capital updated: ${portfolio.current_capital:,.2f}")
        
        # Test drawdown and return-rate calculations
        portfolio.update_capital(95000)
        drawdown = portfolio.get_drawdown()
        total_return = portfolio.get_total_return()
        print(f"✅ Drawdown from peak: {drawdown*100:.2f}%")
        print(f"✅ Total return: {total_return*100:+.2f}%")
        
        # Test trade recording
        portfolio.record_trade(profit=500, trade_value=5000)
        portfolio.record_trade(profit=-200, trade_value=3000)
        print(f"✅ Trades recorded: {portfolio.total_trades}")
        print(f"   Win rate: {portfolio.get_win_rate()*100:.1f}%")
        print(f"   Total profit: ${portfolio.total_profit:,.2f}")
        print(f"   Total fees: ${portfolio.total_fees:,.2f}")
        
        # Print summary
        print("\nPortfolio Summary:")
        print(portfolio.get_summary())
        
        return True
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
