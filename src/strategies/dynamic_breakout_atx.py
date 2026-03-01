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
                 on_signal: Optional[Callable[[TradingSignal], None]] = None):
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

        self.high = float('-inf')
        self.low = float('inf')
        self.short_high = float('-inf')
        self.short_low = float('inf')
        self.short_time_len = int(self.lookback * 0.5)

        # Statistics
        self.num_trade = 0
        self.total_earn = 0.0
        self.avg_earn = 0.0

    def _update_mean(self, old_mean, new_val, length):
        return (old_mean * (length - 1) + new_val) / length if old_mean else new_val

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

        # Efficiently track rolling high/low
        if self.high is None:
            self.high = max(self.prices)
        if self.low is None:
            self.low = min(self.prices)

        self._update_atr(price)
        self._update_adx(price)
        self._update_volume_stats(volume)

        if len(self.prices) < self.lookback:
            return

        # Calculate dynamic breakout entry thresholds
        dynamic_x = self.high - self.pr_x * self.mean_atr if self.mean_atr else self.high
        dynamic_y = self.low + self.pr_y * self.mean_atr if self.mean_atr else self.low

        # Entry condition - emit BUY signal
        if (price >= dynamic_x and volume > self.mean_vol and 
            len(self.positions) < self.max_positions):
            
            # Emit BUY signal via callback
            signal = TradingSignal(
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                price=price,
                timestamp=timestamp,
                reason=f"Breakout: price {price:.2f} >= dynamic_x {dynamic_x:.2f}, volume {volume:.0f} > mean {self.mean_vol:.0f}",
                metadata={
                    'dynamic_x': dynamic_x,
                    'dynamic_y': dynamic_y,
                    'mean_atr': self.mean_atr,
                    'mean_vol': self.mean_vol,
                    'mean_adx': self.mean_adx
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

            if (price < self.short_high * (1 - self.drawback) and 
                holding_time > self.hold_minutes and 
                price > pos['entry']):
                self._emit_sell_signal(timestamp, pos, price, "WIN: Price below short high drawback")

            elif price < self.short_low * (1 - self.drawback):
                self._emit_sell_signal(timestamp, pos, price, "LOSS: Price below short low drawback")

    def _emit_sell_signal(self, timestamp, pos, exit_price, reason):
        """Emit a SELL signal for a position."""
        signal = TradingSignal(
            signal_type=SignalType.SELL,
            symbol=self.symbol,
            price=exit_price,
            timestamp=timestamp,
            reason=reason,
            metadata={
                'position': pos,
                'holding_time_minutes': (timestamp - pos['entry_time']).total_seconds() / 60,
                'unrealized_gain': (exit_price - pos['entry']) / pos['entry']
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
        
        return trade_record

    def _close_position(self, timestamp, pos, exit_price, reason):
        """
        Internal method for compatibility with backtesting.
        
        For live trading, this is handled by the orchestrator.
        """
        print(f"{timestamp} {self.symbol} EXIT {reason} at {exit_price}, size {pos['size']}")
        self.close_position(pos, exit_price, timestamp, reason)
