from collections import deque


class DynamicBreakoutTrader:
    def __init__(self, symbol, lookback=14, pr_x=0.8, pr_y=0.7, atr_period=14,
                 max_risk=0.02, leverage=1, adx_period=14):
        self.symbol = symbol
        self.lookback = lookback
        self.pr_x = pr_x
        self.pr_y = pr_y
        self.atr_period = atr_period
        self.adx_period = adx_period
        self.max_risk = max_risk
        self.leverage = leverage

        self.capital = 100000
        self.max_positions = 1
        self.positions = []
        self.trade_records = []

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
        # dynamic_x = self.high
        # dynamic_y = self.low
        dynamic_x = self.high - self.pr_x * self.mean_atr if self.mean_atr else self.high
        dynamic_y = self.low + self.pr_y * self.mean_atr if self.mean_atr else self.low

        # Entry condition
        if (price >= dynamic_x and volume > self.mean_vol and 
            # (self.mean_adx is None or self.mean_adx > 25) and 
            len(self.positions) < self.max_positions):

            # risk_amount = self.capital * self.max_risk
            # position_size = (risk_amount / self.mean_atr) * self.leverage if self.mean_atr else 1
            position_size = 1
            self.positions.append({
                'entry': price,
                'size': position_size,
                'entry_time': timestamp
            })
            print(f"{timestamp} {self.symbol} BUY at {price}, size {position_size}, ADX {self.mean_adx}")

        # Short-term high/low tracking
        if len(self.prices) >= self.short_time_len:
            self.short_high = max(self.short_high, price)
            self.short_low = min(self.short_low, price)

        # Exit condition
        drawback = 0.05
        hold_minutes = 60

        for pos in self.positions[:]:  # copy to avoid mutation during iteration
            holding_time = (timestamp - pos['entry_time']).total_seconds() / 60
            unrealized_gain = (price - pos['entry']) / pos['entry']

            if (price < self.short_high * (1 - drawback) and 
                holding_time > hold_minutes and 
                price > pos['entry']):
                self._close_position(timestamp, pos, price, "WIN")

            elif price < self.short_low * (1 - drawback):
                self._close_position(timestamp, pos, price, "LOSS")

    def _close_position(self, timestamp, pos, exit_price, reason):
        print(f"{timestamp} {self.symbol} EXIT {reason} at {exit_price}, size {pos['size']}")
        earn = (exit_price - pos['entry']) / pos['entry'] * pos['size']
        self.trade_records.append({
            'earn': earn,
            'entry': pos['entry'],
            'exit': exit_price,
            'size': pos['size'],
            'entry_time': pos['entry_time'],
            'exit_time': timestamp
        })
        self.num_trade += 1
        self.total_earn += earn
        self.avg_earn = self.total_earn / self.num_trade if self.num_trade else 0.0
        self.positions.remove(pos)
