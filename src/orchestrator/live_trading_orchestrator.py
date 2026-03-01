"""
Live Trading Orchestrator - Coordinates trading operations.

This class separates concerns:
- Strategy: Pure signal generation logic
- Trader: Exchange-specific API calls  
- Orchestrator: Coordination, logging, portfolio tracking, notifications
"""
import logging
from datetime import datetime
from typing import Dict, Optional
from collections import defaultdict

from src.strategies.dynamic_breakout_atx import TradingSignal, SignalType
from src.trader.base_trader import BaseTrader
from src.config.trading_config import LiveTradingConfig
from src.event import telegram_bot


class PortfolioTracker:
    """Tracks portfolio state and performance metrics."""
    
    def __init__(self, initial_capital: float, trading_fee_rate: float):
        """
        Args:
            initial_capital: Actual balance fetched from exchange at startup.
                             Must NOT be a config assumption — caller is responsible
                             for passing the real value.
            trading_fee_rate: Fee rate per trade leg (e.g., 0.0004 = 0.04%)
        """
        self.initial_capital = initial_capital
        self.peak_capital = initial_capital   # informational only, not used for stop
        self.current_capital = initial_capital
        self.trading_fee_rate = trading_fee_rate
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_fees = 0.0
        
        # Position tracking
        self.active_positions: Dict[str, list] = defaultdict(list)
        self.position_count = 0
        
    def update_capital(self, new_capital: float):
        """Update current capital. Peak is tracked for display only."""
        self.current_capital = new_capital
        if new_capital > self.peak_capital:
            self.peak_capital = new_capital
    
    def get_total_return(self) -> float:
        """Return rate from initial capital. Negative means loss."""
        if self.initial_capital <= 0:
            return 0.0
        return (self.current_capital - self.initial_capital) / self.initial_capital
    
    def get_drawdown(self) -> float:
        """Drawdown from peak (informational display only, not used for stop)."""
        if self.peak_capital <= 0:
            return 0.0
        return (self.peak_capital - self.current_capital) / self.peak_capital
    
    def record_trade(self, profit: float, trade_value: float):
        """Record a completed trade."""
        fee = trade_value * self.trading_fee_rate * 2  # Entry + exit fees
        net_profit = profit - fee
        
        self.total_trades += 1
        self.total_profit += net_profit
        self.total_fees += fee
        
        if net_profit > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
    
    def get_win_rate(self) -> float:
        """Calculate win rate."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    def get_summary(self) -> str:
        """Get portfolio summary string."""
        total_return = self.get_total_return()
        return f"""
Portfolio Summary:
  Capital: ${self.current_capital:,.2f} (Initial: ${self.initial_capital:,.2f})
  Total Return: {total_return*100:+.2f}%
  Peak Capital: ${self.peak_capital:,.2f} (informational)
  Drawdown from Peak: {self.get_drawdown()*100:.2f}%
  
  Total Trades: {self.total_trades}
  Win Rate: {self.get_win_rate()*100:.1f}%
  Total Profit: ${self.total_profit:,.2f}
  Total Fees: ${self.total_fees:,.2f}
  Active Positions: {self.position_count}
"""


class LiveTradingOrchestrator:
    """
    Orchestrates live trading operations.
    
    Responsibilities:
    - Receive signals from strategies via callbacks
    - Execute trades through trader abstraction
    - Track portfolio state and performance
    - Manage logging and notifications
    - Enforce risk limits (max drawdown)
    """
    
    def __init__(self, trader: BaseTrader, config: LiveTradingConfig, logger: logging.Logger):
        self.trader = trader
        self.config = config
        self.logger = logger
        
        # Fetch actual balance from exchange to use as baseline — never use config assumption
        self.logger.info("Fetching initial balance from exchange to establish baseline...")
        actual_initial = self._fetch_usdt_balance()
        if actual_initial is None:
            raise RuntimeError("Cannot start: failed to fetch initial balance from exchange")
        self.logger.info(f"Baseline capital set from exchange: ${actual_initial:,.2f}")
        
        # Portfolio tracking (pass actual balance, not config assumption)
        self.portfolio = PortfolioTracker(
            initial_capital=actual_initial,
            trading_fee_rate=config.trading.trading_fee_rate
        )
        
        # State management
        self.is_trading_active = True
        self.active_orders: Dict[str, Dict] = {}  # order_id -> order_data
        self.symbol_validity: Dict[str, bool] = {}  # Track if symbol is tradeable
        
        # Tracking timestamps
        self.last_portfolio_update = datetime.now()
        self.last_telegram_update = datetime.now()
        
        self.logger.info("LiveTradingOrchestrator initialized")
        self.logger.info(config.get_summary())
    
    def _fetch_usdt_balance(self) -> Optional[float]:
        """
        Fetch current USDT balance from exchange.
        
        Returns:
            USDT balance as float, or None on failure.
        """
        try:
            balance = self.trader.get_balance(account_type='futures')
            if isinstance(balance, dict) and balance.get('success') is False:
                self.logger.error(f"Balance API error: {balance.get('message')}")
                return None
            if isinstance(balance, dict) and 'USDT' in balance:
                return float(balance['USDT'])
            self.logger.error(f"Unexpected balance format: {balance}")
            return None
        except Exception as e:
            self.logger.error(f"Exception fetching balance: {e}", exc_info=True)
            return None

    def check_loss_limit(self) -> bool:
        """
        Check if total return has dropped below the max loss threshold.
        
        Stop condition: (current - initial) / initial < -max_loss_rate
        e.g., initial=$5000, current=$3900, max_loss_rate=0.2
             return = (3900-5000)/5000 = -22% < -20% → STOP
        
        Returns:
            True if trading should stop, False otherwise.
        """
        total_return = self.portfolio.get_total_return()
        if total_return <= -self.config.trading.max_loss_rate:
            self.logger.critical(
                f"🛑 MAX LOSS REACHED: total return {total_return*100:.2f}% <= "
                f"-{self.config.trading.max_loss_rate*100:.2f}%"
            )
            self.logger.critical("🛑 STOPPING ALL TRADING OPERATIONS")
            telegram_bot.send_msg(
                f"🛑 EMERGENCY STOP\n"
                f"Total Return: {total_return*100:.2f}%\n"
                f"Stop Threshold: -{self.config.trading.max_loss_rate*100:.2f}%\n"
                f"Capital: ${self.portfolio.current_capital:,.2f}\n"
                f"Initial: ${self.portfolio.initial_capital:,.2f}"
            )
            self.is_trading_active = False
            return True
        return False
    
    def reset_for_online_backtest(self, strategies: Dict) -> Dict:
        """
        Reset the system for a fresh online-backtest run.

        Performs three steps in order:
          1. Close all open futures positions on the exchange.
          2. Fetch the post-close balance and reset PortfolioTracker with it
             as the new baseline (initial_capital / peak_capital / current_capital).
          3. Clear all internal strategy state (positions, trade records, stats).

        This must be called *before* starting a new online-backtest run so every
        run begins from a known, clean state.

        Args:
            strategies: dict mapping symbol -> DynamicBreakoutTrader (the current
                        strategy instances used in the run, e.g., from live_trading.py)

        Returns:
            {
                'positions_closed': int,
                'positions_failed': list,
                'new_baseline': float,    # USDT balance after closing
            }
        """
        self.logger.info("=" * 60)
        self.logger.info("🔄 ONLINE BACKTEST RESET STARTED")
        self.logger.info("=" * 60)

        # --- Step 1: Close all open exchange positions ---
        self.logger.info("Step 1: Closing all open exchange positions...")
        close_result = self.trader.close_all_positions()
        n_closed = len(close_result['closed'])
        n_failed = len(close_result['failed'])

        for item in close_result['closed']:
            self.logger.info(
                f"  ✅ Closed {item['symbol']} {item['side']} qty={item['qty']}"
            )
        for item in close_result['failed']:
            self.logger.warning(
                f"  ⚠️  Failed to close {item['symbol']}: {item.get('error')} (code={item.get('code')})"
            )
        self.logger.info(f"  Closed {n_closed} position(s), {n_failed} failure(s)")

        # --- Step 2: Re-baseline portfolio from actual post-close balance ---
        self.logger.info("Step 2: Re-fetching balance to establish new baseline...")
        new_balance = self._fetch_usdt_balance()
        if new_balance is None:
            self.logger.error("Could not fetch balance after closing positions; baseline unchanged")
            new_balance = self.portfolio.current_capital

        self.portfolio.initial_capital = new_balance
        self.portfolio.peak_capital = new_balance
        self.portfolio.current_capital = new_balance
        self.portfolio.total_trades = 0
        self.portfolio.winning_trades = 0
        self.portfolio.losing_trades = 0
        self.portfolio.total_profit = 0.0
        self.portfolio.total_fees = 0.0
        self.portfolio.position_count = 0
        self.portfolio.active_positions.clear()
        self.logger.info(f"  New baseline capital: ${new_balance:,.2f}")

        # --- Step 3: Reset all strategy instances ---
        self.logger.info(f"Step 3: Resetting {len(strategies)} strategy instance(s)...")
        for symbol, strategy in strategies.items():
            strategy.positions.clear()
            strategy.trade_records.clear()
            strategy.num_trade = 0
            strategy.total_earn = 0.0
            strategy.avg_earn = 0.0
            # Reset price/indicator deques so warm-up runs fresh
            strategy.prices.clear()
            strategy.volumes.clear()
            strategy.atr_values.clear()
            strategy.adx_values.clear()
            strategy.mean_atr = None
            strategy.mean_adx = None
            strategy.mean_vol = None
            strategy.high = None
            strategy.low = None
            strategy.short_high = float('-inf')
            strategy.short_low = float('inf')
            self.logger.info(f"  ✅ Reset strategy: {symbol}")

        # Re-enable trading (in case it was stopped by loss limit)
        self.is_trading_active = True
        self.active_orders.clear()
        self.symbol_validity.clear()
        self.last_portfolio_update = datetime.now()
        self.last_telegram_update = datetime.now()

        self.logger.info("=" * 60)
        self.logger.info("✅ ONLINE BACKTEST RESET COMPLETE")
        self.logger.info(f"   Closed: {n_closed} positions | New capital: ${new_balance:,.2f}")
        self.logger.info("=" * 60)

        return {
            'positions_closed': n_closed,
            'positions_failed': close_result['failed'],
            'new_baseline': new_balance,
        }

    def sync_portfolio_from_exchange(self):
        """Sync current capital from exchange (called periodically)."""
        usdt_balance = self._fetch_usdt_balance()
        if usdt_balance is not None:
            self.portfolio.update_capital(usdt_balance)
            self.logger.info(f"Portfolio synced: ${usdt_balance:,.2f}")
        else:
            self.logger.warning("Portfolio sync skipped: could not fetch balance")
    
    def calculate_order_quantity(self, price: float, target_value_usdt: float) -> Optional[float]:
        """
        Calculate order quantity based on price and target USDT value.
        
        Args:
            price: Current price of the asset
            target_value_usdt: Target trade value in USDT
            
        Returns:
            Rounded quantity that meets exchange precision requirements, or None if invalid
        """
        if price <= 0:
            return None
            
        # Calculate raw quantity
        raw_quantity = target_value_usdt / price
        
        # Determine appropriate precision based on price
        if price >= 1000:  # e.g., BTC
            precision = 3
        elif price >= 10:  # e.g., ETH, BNB
            precision = 2
        elif price >= 1:
            precision = 1
        elif price >= 0.1:
            precision = 0
        else:  # Very low price
            precision = 0
            raw_quantity = round(raw_quantity)
        
        # Round to appropriate precision
        if precision > 0:
            quantity = round(raw_quantity, precision)
        else:
            quantity = int(raw_quantity)
        
        # Ensure minimum quantity
        if quantity <= 0:
            quantity = 1 if precision == 0 else 10 ** (-precision)
            
        return quantity
    
    def handle_signal(self, signal: TradingSignal, strategy):
        """
        Handle a trading signal from a strategy.
        
        This is the callback that strategies call when they generate signals.
        
        Args:
            signal: Trading signal
            strategy: Strategy instance that generated the signal
        """
        # Check if trading is still active
        if not self.is_trading_active:
            self.logger.warning(f"Trading inactive, ignoring signal: {signal}")
            return
        
        # Check loss limit before executing
        if self.check_loss_limit():
            return
        
        # Check if symbol is valid
        if signal.symbol in self.symbol_validity and not self.symbol_validity[signal.symbol]:
            self.logger.warning(f"Symbol {signal.symbol} marked as invalid, skipping signal")
            return
        
        if signal.signal_type == SignalType.BUY:
            self._execute_buy(signal, strategy)
        elif signal.signal_type == SignalType.SELL:
            self._execute_sell(signal, strategy)
    
    def _execute_buy(self, signal: TradingSignal, strategy):
        """Execute a BUY order based on signal."""
        try:
            # Calculate position size
            position_size = self.calculate_order_quantity(
                signal.price, 
                self.config.trading.trade_value_usdt
            )
            
            if position_size is None:
                self.logger.error(f"[{signal.symbol}] Invalid position size calculation")
                return
            
            self.logger.info(
                f"[{signal.symbol}] Attempting BUY {position_size} at market price ~{signal.price:.2f}"
            )
            self.logger.info(f"  Reason: {signal.reason}")
            
            # Execute via trader
            result = self.trader.open_futures_position(
                symbol=signal.symbol,
                side='BUY',
                quantity=position_size,
                order_type='MARKET'
            )
            
            if result.get('success'):
                order_data = result['data']
                order_id = order_data.get('orderId')
                executed_qty = float(order_data.get('executedQty', position_size))
                executed_price = float(order_data.get('avgPrice', signal.price))
                
                if executed_price <= 0:
                    executed_price = signal.price
                
                trade_value = executed_qty * executed_price
                
                # Log success
                self.logger.info("=" * 80)
                self.logger.info(f"📈 LONG POSITION OPENED - {signal.symbol}")
                self.logger.info(f"   Time: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"   Order ID: {order_id}")
                self.logger.info(f"   Entry Price: ${executed_price:,.2f}")
                self.logger.info(f"   Quantity: {executed_qty}")
                self.logger.info(f"   Trade Value: ${trade_value:,.2f}")
                self.logger.info(f"   Strategy Signal: {signal.reason}")
                self.logger.info("=" * 80)
                
                # Update strategy's internal position tracking
                strategy.add_position(
                    entry_price=executed_price,
                    size=executed_qty,
                    entry_time=signal.timestamp,
                    order_id=str(order_id),
                    trade_value=trade_value
                )
                
                # Track order
                self.active_orders[str(order_id)] = order_data
                self.portfolio.position_count += 1
                
                # Send notification
                telegram_bot.send_msg(
                    f"🟢 BUY {signal.symbol}\n"
                    f"Qty: {executed_qty}\n"
                    f"Price: ${executed_price:,.2f}\n"
                    f"Value: ${trade_value:,.2f}\n"
                    f"Reason: {signal.reason}"
                )
                
                # Sync portfolio after trade
                self.sync_portfolio_from_exchange()
                
            else:
                error_msg = result.get('message', 'Unknown error')
                error_code = result.get('code', 'N/A')
                self.logger.error(
                    f"[{signal.symbol}] BUY ORDER FAILED: {error_msg} (code: {error_code})"
                )
                
                # Mark symbol as invalid if error indicates symbol issue
                if error_code in [-1121, -1111]:
                    self.symbol_validity[signal.symbol] = False
                    self.logger.warning(f"Marking {signal.symbol} as invalid")
                
        except Exception as e:
            self.logger.error(f"[{signal.symbol}] Exception in _execute_buy: {e}", exc_info=True)
    
    def _execute_sell(self, signal: TradingSignal, strategy):
        """Execute a SELL order based on signal."""
        try:
            position = signal.metadata.get('position')
            if not position:
                self.logger.error(f"[{signal.symbol}] No position in SELL signal metadata")
                return
            
            self.logger.info(
                f"[{signal.symbol}] Attempting SELL {position['size']} at market price "
                f"~{signal.price:.2f}, Reason: {signal.reason}"
            )
            
            # Execute via trader
            result = self.trader.close_futures_position(
                symbol=signal.symbol,
                side='SELL',
                quantity=position['size'],
                order_type='MARKET'
            )
            
            if result.get('success'):
                order_data = result['data']
                order_id = order_data.get('orderId')
                executed_qty = float(order_data.get('executedQty', position['size']))
                executed_price = float(order_data.get('avgPrice', signal.price))
                
                if executed_price <= 0:
                    executed_price = signal.price
                
                # Calculate profit/loss
                entry_price = position.get('entry', 0)
                if entry_price <= 0:
                    self.logger.error(f"Invalid entry price in position: {position}")
                    return
                
                trade_value = executed_qty * executed_price
                profit = (executed_price - entry_price) * executed_qty
                profit_pct = (executed_price - entry_price) / entry_price * 100
                holding_time = signal.metadata.get('holding_time_minutes', 0)
                
                # Determine profit/loss emoji
                pnl_emoji = "✅" if profit > 0 else "❌"
                
                # Log success
                self.logger.info("=" * 80)
                self.logger.info(f"📉 POSITION CLOSED - {signal.symbol}")
                self.logger.info(f"   Time: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"   Order ID: {order_id}")
                self.logger.info(f"   Entry Price: ${entry_price:,.2f}")
                self.logger.info(f"   Exit Price: ${executed_price:,.2f}")
                self.logger.info(f"   Quantity: {executed_qty}")
                self.logger.info(f"   Trade Value: ${trade_value:,.2f}")
                self.logger.info(f"   Profit/Loss: ${profit:,.2f} ({profit_pct:+.2f}%)")
                self.logger.info(f"   Holding Time: {holding_time:.1f} minutes")
                self.logger.info(f"   Exit Reason: {signal.reason}")
                self.logger.info("=" * 80)
                
                # Update strategy's internal position tracking
                trade_record = strategy.close_position(
                    position=position,
                    exit_price=executed_price,
                    exit_time=signal.timestamp,
                    reason=signal.reason
                )
                
                # Update portfolio statistics
                self.portfolio.record_trade(profit, trade_value)
                self.portfolio.position_count -= 1
                
                # Send notification
                telegram_bot.send_msg(
                    f"{pnl_emoji} CLOSE {signal.symbol}\n"
                    f"Entry: ${entry_price:,.2f}\n"
                    f"Exit: ${executed_price:,.2f}\n"
                    f"P/L: ${profit:,.2f} ({profit_pct:+.2f}%)\n"
                    f"Hold: {holding_time:.0f}min\n"
                    f"Reason: {signal.reason}"
                )
                
                # Sync portfolio after trade
                self.sync_portfolio_from_exchange()
                
            else:
                error_msg = result.get('message', 'Unknown error')
                error_code = result.get('code', 'N/A')
                self.logger.error(
                    f"[{signal.symbol}] SELL ORDER FAILED: {error_msg} (code: {error_code})"
                )
                
        except Exception as e:
            self.logger.error(f"[{signal.symbol}] Exception in _execute_sell: {e}", exc_info=True)
    
    def periodic_update(self):
        """
        Perform periodic updates: portfolio tracking and Telegram notifications.
        
        Should be called regularly in the main loop.
        """
        now = datetime.now()
        
        # Portfolio tracking
        if (now - self.last_portfolio_update).total_seconds() >= self.config.logging.portfolio_tracking_interval:
            self.sync_portfolio_from_exchange()
            self.logger.info(self.portfolio.get_summary())
            self.last_portfolio_update = now
            
            # Check loss limit (stop if total return <= -max_loss_rate)
            self.check_loss_limit()
        
        # Telegram updates
        if (now - self.last_telegram_update).total_seconds() >= self.config.logging.telegram_update_interval:
            summary = (
                f"📊 Portfolio Update\n"
                f"Capital: ${self.portfolio.current_capital:,.2f}\n"
                f"Return: {self.portfolio.get_total_return()*100:+.2f}%\n"
                f"Drawdown: {self.portfolio.get_drawdown()*100:.2f}%\n"
                f"Trades: {self.portfolio.total_trades} "
                f"(Win: {self.portfolio.get_win_rate()*100:.0f}%)\n"
                f"Active Positions: {self.portfolio.position_count}"
            )
            telegram_bot.send_msg(summary)
            self.last_telegram_update = now
