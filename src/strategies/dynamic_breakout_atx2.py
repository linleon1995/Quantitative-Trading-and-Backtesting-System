from collections import deque
import numpy as np

# === 單幣種信號代理 ===
class CoinSignalAgent:
    def __init__(self, symbol, lookback=14, pr_x=0.8, pr_y=0.7):
        self.symbol = symbol
        self.lookback = lookback
        self.pr_x = pr_x
        self.pr_y = pr_y
        self.prices = deque(maxlen=lookback)
        self.volumes = deque(maxlen=lookback)
        self.mean_atr = None
        self.high = float('-inf')
        self.low = float('inf')

    def on_tick(self, price, volume):
        self.prices.append(price)
        self.volumes.append(volume)
        if len(self.prices) < self.lookback:
            return 0.0  # 沒有足夠資料時返回0分

        atr = np.mean(np.abs(np.diff(self.prices)))
        self.mean_atr = atr
        self.high = max(self.prices)
        self.low = min(self.prices)

        upper = self.high - self.pr_x * atr
        lower = self.low + self.pr_y * atr

        # 簡單的訊號強度：距離上/下界的相對位置
        pos = (price - lower) / (upper - lower + 1e-8)
        score = np.clip(2 * pos - 1, -1, 1)  # normalize to [-1, 1]
        return score


class PortfolioTrader:
    def __init__(self, capital=100000, max_single_position=0.2,
                 stop_loss_callback=None, exit_callback=None,
                 risk_limit_callback=None):
        self.capital = capital
        self.max_single_position = max_single_position
        self.positions = {}
        self.total_loss = 0.0
        self.stop_loss_callback = stop_loss_callback
        self.exit_callback = exit_callback
        self.risk_limit_callback = risk_limit_callback
        self.agents = {}
        self.agent_config = {
            'lookback': 14,
            'pr_x': 0.8,
            'pr_y': 0.7
        }

    def on_market_tick(self, timestamp, data_dict):
        """
        data_dict: {symbol: {'close_price': ..., 'volume': ...}}
        agents: {symbol: CoinSignalAgent}
        """
        # Step 1. 計算所有coin的 normalized signal
        scores = {}
        for symbol, data in data_dict.items():
            if symbol not in self.agents:
                self.agents[symbol] = CoinSignalAgent(symbol=symbol, **self.agent_config)
            agent = self.agents[symbol]
            score = agent.on_tick(data['close_price'], data['volume'])
            if score is not None:
                scores[symbol] = score
        
        if not scores:
            return  # 沒有有效訊號時跳過

        # Step 2. 風控檢查
        if self.risk_limit_callback and self.risk_limit_callback(self):
            print(f"{timestamp} [STOP TRADING] Risk limit hit.")
            return

        # Step 3. 選出最高分的coin嘗試開倉
        top_symbol = max(scores, key=scores.get)
        if scores[top_symbol] > 0.8 and top_symbol not in self.positions:
            self._open_position(timestamp, top_symbol, data_dict[top_symbol]['close_price'], scores[top_symbol])

        # Step 4. 檢查是否要平倉
        for sym, pos in list(self.positions.items()):
            if self.exit_callback and self.exit_callback(pos, data_dict[sym]['close_price']):
                self._close_position(timestamp, sym, data_dict[sym]['close_price'])

    def _open_position(self, timestamp, symbol, price, score):
        size = self.capital * self.max_single_position / price
        self.positions[symbol] = {
            'entry_price': price,
            'size': size,
            'entry_time': timestamp
        }
        print(f"{timestamp} BUY {symbol} at {price:.2f}, score={score:.2f}")

    def _close_position(self, timestamp, symbol, price):
        pos = self.positions[symbol]
        pnl = (price - pos['entry_price']) / pos['entry_price']
        self.total_loss += min(0, pnl)
        print(f"{timestamp} EXIT {symbol} at {price:.2f}, PnL={pnl:.4f}")
        del self.positions[symbol]
