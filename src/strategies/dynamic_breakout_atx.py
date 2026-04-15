import logging
from collections import deque
from typing import Callable, Optional, Dict, Any
from enum import Enum


class SignalType(Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class TradingSignal:
    """Represents a trading signal from the strategy."""
    def __init__(self, signal_type: SignalType, symbol: str, price: float, 
                 timestamp: Any, reason: str = "", metadata: Optional[Dict] = None):
        self.signal_type = signal_type
        self.symbol = symbol
        self.price = price
        self.timestamp = timestamp
        self.reason = reason
        self.metadata = metadata or {}
    
    def __repr__(self):
        return f"TradingSignal({self.signal_type.value}, {self.symbol}@{self.price}, reason={self.reason})"


class DynamicBreakoutTrader:
    """
    Exchange-agnostic dynamic breakout trading strategy.
    
    This strategy only handles signal generation logic and does NOT execute trades.
    It maintains internal state for tracking positions but delegates actual execution
    to an external orchestrator via callbacks.
    
    The strategy can be used with any exchange by providing appropriate callbacks.
    """
    
    def __init__(self, symbol: str, lookback: int = 14, pr_x: float = 0.8, 
                 pr_y: float = 0.7, atr_period: int = 14, max_risk: float = 0.02, 
                 leverage: int = 1, adx_period: int = 14, drawback: float = 0.05,
                 hold_minutes: int = 60, max_positions: int = 1,
                 on_signal: Optional[Callable[[TradingSignal], None]] = None,
                 # --- Signal filters (set to 0 / None to disable) ---
                 min_atr_pct: float = 0.003,
                 min_adx: float = 0.0,
                 min_volume_usdt: float = 0.0,
                 min_vol_ratio: float = 1.0,
                 min_price: float = 0.0,
                 max_price: float = 0.0,
                 ):
        """
        Initialize the strategy.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            lookback: Number of periods for lookback window
            pr_x: Multiplier for upper breakout threshold
            pr_y: Multiplier for lower breakout threshold
            atr_period: Period for ATR calculation
            max_risk: Maximum risk per trade
            leverage: Trading leverage
            adx_period: Period for ADX calculation
            drawback: Drawback percentage for exit condition
            hold_minutes: Minimum holding time before exit
            max_positions: Maximum concurrent positions for this symbol
            on_signal: Callback function to receive trading signals

            Filter parameters (set to 0 to disable):
            min_atr_pct: Minimum ATR as % of price (e.g. 0.003 = 0.3%).
                Filters out low-volatility / very cheap coins where the
                breakout threshold collapses to ≈ rolling_high and every
                tick triggers a BUY (e.g. YGGUSDT, DOGEUSDT at tiny prices).
            min_adx: Minimum mean_adx value required for entry. Filters
                out choppy, trendless markets. 0 = disabled.
            min_volume_usdt: Minimum notional volume per bar in USDT
                (volume * price). Filters illiquid coins. 0 = disabled.
            min_vol_ratio: Volume must exceed mean_vol * min_vol_ratio
                (default 1.0 = same as current, set >1 for stronger surge).
            min_price: Skip symbols below this absolute price. 0 = disabled.
            max_price: Skip symbols above this absolute price. 0 = disabled.
        """
        self.symbol = symbol
        self.lookback = lookback
        self.pr_x = pr_x
        self.pr_y = pr_y
        self.atr_period = atr_period
        self.adx_period = adx_period
        self.max_risk = max_risk
        self.leverage = leverage
        self.drawback = drawback
        self.hold_minutes = hold_minutes
        self.max_positions = max_positions

        # --- Filter settings ---
        self.min_atr_pct = min_atr_pct          # 0 = disabled
        self.min_adx = min_adx                  # 0 = disabled
        self.min_volume_usdt = min_volume_usdt  # 0 = disabled
        self.min_vol_ratio = min_vol_ratio       # ≥ 1.0
        self.min_price = min_price              # 0 = disabled
        self.max_price = max_price              # 0 = disabled
        
        # Callback for signal emission
        self.on_signal = on_signal

        # Internal position tracking (abstract, not actual exchange positions)
        self.positions = []
        self.trade_records = []

        # Technical indicators
        self.prices = deque(maxlen=lookback)
        self.volumes = deque(maxlen=lookback)
        self.atr_values = deque(maxlen=atr_period)
        self.adx_values = deque(maxlen=adx_period)

        self.mean_atr = None
        self.mean_adx = None
        self.mean_vol = None

        self.high: Optional[float] = None
        self.low: Optional[float] = None
        self.short_high = float('-inf')
        self.short_low = float('inf')
        self.short_time_len = int(self.lookback * 0.5)

        # Statistics
        self.num_trade = 0
        self.total_earn = 0.0
        self.avg_earn = 0.0

        self.logger = logging.getLogger(f"strategy.{symbol}")

    def warmup_with_history(self, bars: list) -> int:
        """Pre-warm all indicators using historical bars WITHOUT emitting signals.

        Call this before attaching ``on_signal`` (or while ``on_signal`` is None)
        so that the first live tick fires into a fully-initialised strategy rather
        than into one where ``self.high ≈ current_price`` and
        ``dynamic_x ≈ current_price``.

        Args:
            bars: List of kline rows as returned by Binance klines API:
                  [open_time, open, high, low, close, volume, close_time, ...]
                  close is index 4, volume is index 5, close_time is index 6 (ms).

        Returns:
            Number of bars processed.
        """
        from datetime import datetime

        saved_callback = self.on_signal
        self.on_signal = None  # Suppress all signals during warmup
        try:
            for row in bars:
                try:
                    close_time_ms = int(row[6])
                    ts = datetime.utcfromtimestamp(close_time_ms / 1000)
                    tick = {
                        'close_price': float(row[4]),
                        'volume': float(row[5]),
                    }
                    self.on_tick(ts, tick)
                except Exception:
                    pass  # Skip malformed rows; warmup is best-effort
        finally:
            self.on_signal = saved_callback  # Always restore, even on error
        return len(bars)

    def _update_mean(self, old_mean, new_val, length):
        # NOTE: must check `is not None`, not truthiness — old_mean == 0.0 is valid.
        return (old_mean * (length - 1) + new_val) / length if old_mean is not None else new_val

    def _update_atr(self, price):
        if len(self.prices) >= 2:
            atr_val = abs(price - self.prices[-2])
            self.atr_values.append(atr_val)
            if len(self.atr_values) >= self.atr_period:
                self.mean_atr = self._update_mean(self.mean_atr, atr_val, self.atr_period)

    def _update_adx(self, price):
        if len(self.prices) >= 2:
            high = max(price, self.prices[-2])
            low = min(price, self.prices[-2])
            tr = max(high - low, abs(high - self.prices[-2]), abs(low - self.prices[-2]))
            self.adx_values.append(tr)
            if len(self.adx_values) >= self.adx_period:
                self.mean_adx = self._update_mean(self.mean_adx, tr, self.adx_period)

    def _update_volume_stats(self, volume):
        self.volumes.append(volume)
        if len(self.volumes) >= self.lookback:
            self.mean_vol = self._update_mean(self.mean_vol, volume, len(self.volumes))

    def on_tick(self, timestamp, data):
        """
        Process a new tick of market data.
        
        This method updates indicators and emits trading signals via callback.
        It does NOT execute trades directly.
        
        Args:
            timestamp: Timestamp of the tick
            data: Market data dictionary with 'close_price' and 'volume'
        """
        price = float(data['close_price'])
        volume = float(data['volume'])

        self.prices.append(price)

        # Always update rolling high/low from the current lookback window
        self.high = max(self.prices)
        self.low = min(self.prices)

        self._update_atr(price)
        self._update_adx(price)
        self._update_volume_stats(volume)

        if len(self.prices) < self.lookback:
            return

        # Wait until all indicators are fully warmed up before evaluating entry.
        # Without this guard, mean_atr=None causes dynamic_x to fall back to
        # self.high which was previously float('-inf'), firing on every tick.
        if self.mean_atr is None or self.mean_vol is None:
            return

        # Calculate dynamic breakout entry thresholds
        dynamic_x = self.high - self.pr_x * self.mean_atr
        dynamic_y = self.low + self.pr_y * self.mean_atr

        # ------------------------------------------------------------------
        # Signal filters — each can be disabled by setting its param to 0
        # ------------------------------------------------------------------

        # Filter 1: Absolute price range
        if self.min_price > 0 and price < self.min_price:
            return
        if self.max_price > 0 and price > self.max_price:
            return

        # Filter 2: ATR% — prevents low-volatility / low-price coins from
        # triggering because dynamic_x ≈ rolling_high when ATR is tiny.
        # atr_pct = mean_atr / price normalises ATR across different price levels.
        atr_pct = self.mean_atr / price if price > 0 else 0.0
        if self.min_atr_pct > 0 and atr_pct < self.min_atr_pct:
            return

        # Filter 3: ADX trend-strength filter (skip choppy markets)
        if self.min_adx > 0 and (self.mean_adx is None or self.mean_adx < self.min_adx):
            return

        # Filter 4: Minimum notional volume (illiquid coin guard)
        notional_volume = volume * price
        if self.min_volume_usdt > 0 and notional_volume < self.min_volume_usdt:
            return

        # Entry condition - emit BUY signal
        # Filter 5: Volume surge ratio (min_vol_ratio ≥ 1.0; default keeps existing behaviour)
        if (price >= dynamic_x and volume > self.mean_vol * self.min_vol_ratio and
            len(self.positions) < self.max_positions):

            vol_ratio = volume / self.mean_vol if self.mean_vol else 0.0
            reason = (
                f"Breakout: price {price:.6f} >= dynamic_x {dynamic_x:.6f}, "
                f"vol {volume:.2f} > mean*{self.min_vol_ratio} {self.mean_vol * self.min_vol_ratio:.2f}, "
                f"atr_pct {atr_pct*100:.3f}%"
            )
            self.logger.info(
                "[BUY] ts=%s symbol=%s price=%.6f "
                "dynamic_x=%.6f dynamic_y=%.6f "
                "rolling_high=%.6f rolling_low=%.6f "
                "mean_atr=%.6f atr_pct=%.4f%% "
                "mean_adx=%s "
                "volume=%.2f mean_vol=%.2f vol_ratio=%.3f min_vol_ratio=%.2f "
                "open_positions=%d",
                timestamp, self.symbol, price,
                dynamic_x, dynamic_y,
                self.high, self.low,
                self.mean_atr, atr_pct * 100,
                f"{self.mean_adx:.4f}" if self.mean_adx is not None else "N/A",
                volume, self.mean_vol, vol_ratio, self.min_vol_ratio,
                len(self.positions),
            )
            # Emit BUY signal via callback
            signal = TradingSignal(
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                price=price,
                timestamp=timestamp,
                reason=reason,
                metadata={
                    'dynamic_x': dynamic_x,
                    'dynamic_y': dynamic_y,
                    'mean_atr': self.mean_atr,
                    'atr_pct': atr_pct,
                    'mean_vol': self.mean_vol,
                    'vol_ratio': vol_ratio,
                    'mean_adx': self.mean_adx,
                    'rolling_high': self.high,
                    'rolling_low': self.low,
                }
            )
            if self.on_signal:
                self.on_signal(signal)

        # Short-term high/low tracking
        if len(self.prices) >= self.short_time_len:
            self.short_high = max(self.short_high, price)
            self.short_low = min(self.short_low, price)

        # Exit condition - emit SELL signal
        for pos in self.positions[:]:  # copy to avoid mutation during iteration
            holding_time = (timestamp - pos['entry_time']).total_seconds() / 60
            unrealized_gain = (price - pos['entry']) / pos['entry']
            stop_loss_price = pos['entry'] * (1 - self.drawback)
            trailing_stop_price = self.short_high * (1 - self.drawback)

            self.logger.debug(
                "[EXIT_CHECK] ts=%s symbol=%s price=%.6f entry=%.6f "
                "holding_min=%.1f short_high=%.6f trailing_stop=%.6f "
                "stop_loss=%.6f unrealized_gain=%.4f%%",
                timestamp, self.symbol, price, pos['entry'],
                holding_time, self.short_high, trailing_stop_price,
                stop_loss_price, unrealized_gain * 100,
            )

            if (price < trailing_stop_price and
                holding_time > self.hold_minutes and
                price > pos['entry']):
                self._emit_sell_signal(timestamp, pos, price, "WIN: Price below short high drawback")

            elif price < stop_loss_price:
                # BUG FIX: was `short_low * (1 - drawback)` — short_low is a
                # monotonically decreasing all-time minimum, so the threshold
                # kept dropping and stop-loss almost never triggered.
                # Now uses a fixed percentage below entry price.
                self._emit_sell_signal(timestamp, pos, price, "LOSS: Price below entry stop-loss")

    def _emit_sell_signal(self, timestamp, pos, exit_price, reason):
        """Emit a SELL signal for a position."""
        holding_time = (timestamp - pos['entry_time']).total_seconds() / 60
        gain_pct = (exit_price - pos['entry']) / pos['entry']
        self.logger.info(
            "[SELL] ts=%s symbol=%s exit_price=%.6f entry_price=%.6f "
            "gain=%.4f%% holding_min=%.1f reason=%s "
            "short_high=%.6f stop_loss_threshold=%.6f",
            timestamp, self.symbol, exit_price, pos['entry'],
            gain_pct * 100, holding_time, reason,
            self.short_high, pos['entry'] * (1 - self.drawback),
        )
        signal = TradingSignal(
            signal_type=SignalType.SELL,
            symbol=self.symbol,
            price=exit_price,
            timestamp=timestamp,
            reason=reason,
            metadata={
                'position': pos,
                'holding_time_minutes': holding_time,
                'gain_pct': gain_pct,
                'short_high': self.short_high,
                'stop_loss_threshold': pos['entry'] * (1 - self.drawback),
            }
        )
        if self.on_signal:
            self.on_signal(signal)
    
    def add_position(self, entry_price: float, size: float, entry_time: Any, 
                     order_id: Optional[str] = None, **metadata):
        """
        Add a position to internal tracking.
        
        This is called by the orchestrator after a BUY order is executed.
        
        Args:
            entry_price: Entry price of the position
            size: Position size
            entry_time: Entry timestamp
            order_id: Exchange order ID (optional)
            **metadata: Additional metadata to store
        """
        position = {
            'entry': entry_price,
            'size': size,
            'entry_time': entry_time,
            'order_id': order_id,
            **metadata
        }
        self.positions.append(position)
        # Reset short_high to entry price so trailing profit tracks peak from entry onwards
        self.short_high = entry_price
        self.logger.info(
            "[POSITION_OPEN] ts=%s symbol=%s entry=%.6f size=%.6f order_id=%s",
            entry_time, self.symbol, entry_price, size, order_id,
        )
        return position
    
    def close_position(self, position: Dict, exit_price: float, exit_time: Any, reason: str = ""):
        """
        Close a position and update statistics.
        
        This is called by the orchestrator after a SELL order is executed.
        
        Args:
            position: Position dictionary to close
            exit_price: Exit price
            exit_time: Exit timestamp
            reason: Reason for closing
        
        Returns:
            Trade record dictionary
        """
        if position not in self.positions:
            return None
            
        earn = (exit_price - position['entry']) / position['entry'] * position['size']
        trade_record = {
            'earn': earn,
            'entry': position['entry'],
            'exit': exit_price,
            'size': position['size'],
            'entry_time': position['entry_time'],
            'exit_time': exit_time,
            'reason': reason
        }
        
        self.trade_records.append(trade_record)
        self.num_trade += 1
        self.total_earn += earn
        self.avg_earn = self.total_earn / self.num_trade if self.num_trade else 0.0
        self.positions.remove(position)
        self.logger.info(
            "[POSITION_CLOSE] ts=%s symbol=%s entry=%.6f exit=%.6f "
            "earn=%.6f gain_pct=%.4f%% holding_min=%.1f reason=%s "
            "total_trades=%d total_earn=%.6f avg_earn=%.6f",
            exit_time, self.symbol, position['entry'], exit_price,
            earn,
            (exit_price - position['entry']) / position['entry'] * 100,
            (exit_time - position['entry_time']).total_seconds() / 60 if hasattr(exit_time - position['entry_time'], 'total_seconds') else 0,
            reason, self.num_trade, self.total_earn, self.avg_earn,
        )
        return trade_record

    def _close_position(self, timestamp, pos, exit_price, reason):
        """
        Internal method for compatibility with backtesting.
        
        For live trading, this is handled by the orchestrator.
        """
        print(f"{timestamp} {self.symbol} EXIT {reason} at {exit_price}, size {pos['size']}")
        self.close_position(pos, exit_price, timestamp, reason)
