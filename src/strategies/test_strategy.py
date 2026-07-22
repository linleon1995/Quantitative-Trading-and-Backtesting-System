import time
from collections import deque
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.data_source.create_backtest_database import ArcticDBOperator


class SimpleMomentumStrategy:
    def __init__(self, short_window=3, long_window=10, base_threshold=0.001, stop_loss=0.10, 
                 take_profit=None, fee_rate=0.001, momentum_window=20, momentum_threshold_ratio=0.5):
        """
        初始化策略參數
        """
        self.short_window = short_window
        self.long_window = long_window
        self.base_threshold = base_threshold
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.fee_rate = fee_rate
        self.momentum_window = momentum_window
        self.momentum_threshold_count = int(momentum_threshold_ratio*momentum_window)

        self.data_window_size = max(short_window, long_window, momentum_window)
        self.price_data = deque(maxlen=self.data_window_size)
        self.position = None  # "BUY", or None
        self.entry_price = None  # 持倉價格
        self.total_profit = 0.0  # 累積淨利潤
        self.momentum_signals = deque(maxlen=momentum_window)  # 儲存近期 momentum 信號
        self.momentum = None
        self.dynamic_threshold = None
        self.total_earn = 0
        self.trade_count = 0

    def add_price(self, price):
        """
        新增價格到資料窗口
        """
        self.price_data.append(price)

    def calculate_sma(self, window):
        """
        計算移動平均線
        """
        if len(self.price_data) < window:
            return None
        return sum(list(self.price_data)[-window:]) / window

    def calculate_momentum(self):
        """
        計算價格變化率
        """
        if len(self.price_data) < 2:
            return None
        prices = list(self.price_data)
        return (prices[-1] - prices[-2]) / prices[-2]

    def adjust_threshold(self):
        """
        動態調整動能閾值
        """
        # TODO: auto base_threshold
        if len(self.price_data) < self.data_window_size:
            return self.base_threshold

        # 使用價格變化率的標準差來調整
        prices = list(self.price_data)
        momentum_values = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
        # avg_momentum = sum(momentum_values) / len(momentum_values)
        # adjusted_threshold = self.base_threshold + avg_momentum * 0.5
        max_momentum = max(momentum_values)
        adjusted_threshold = self.base_threshold + max_momentum * 0.125
        return max(self.base_threshold, adjusted_threshold)  # 確保閾值不小於基準

    def update_momentum_signals(self, momentum, threshold):
        """
        更新 momentum 信號狀態
        """
        if momentum is None:
            return
        signal = 0
        if momentum > threshold:
            signal = 1  # 上漲信號
        elif momentum < -threshold:
            signal = -1  # 下跌信號

        self.momentum_signals.append(signal)

    def check_momentum_density(self):
        """
        檢查最近 momentum 窗口內信號密集程度
        """
        if len(self.momentum_signals) < self.momentum_window:
            return False

        # 計算正向與負向信號數量
        buy_signals = sum(1 for sig in self.momentum_signals if sig == 1)
        sell_signals = sum(1 for sig in self.momentum_signals if sig == -1)

        return buy_signals >= self.momentum_threshold_count or sell_signals >= self.momentum_threshold_count

    def check_stop_loss_or_take_profit(self, price):
        """
        判斷是否觸發止損或停利
        """
        if self.entry_price is None:
            return None

        # 計算價格變化百分比
        change_percentage = (price - self.entry_price) / self.entry_price

        if change_percentage <= -self.stop_loss:
            return "SELL"  # 止損
        if self.take_profit is not None and change_percentage >= self.take_profit:
            return "SELL"  # 停利
        return None

    def update_last_high(self):
        import numpy as np
        from scipy.signal import find_peaks
        valleys, _ = find_peaks(-np.array(list(self.price_data)))
        if valleys.size == 0:
            return self.price_data[-1]
        else:
            return self.price_data[valleys[-1]]

    def check_signal(self):
        """
        判斷交易信號
        """
        if len(self.price_data) < self.data_window_size:
            return None

        sma_short = self.calculate_sma(self.short_window)
        sma_long = self.calculate_sma(self.long_window)
        momentum = self.calculate_momentum()
        # dynamic_threshold = self.adjust_threshold()
        dynamic_threshold = self.base_threshold

        if sma_short is None or sma_long is None or momentum is None:
            return None

        # 更新 momentum 信號
        self.update_momentum_signals(momentum, dynamic_threshold)

        # 停利與止損優先判斷
        price = self.price_data[-1]

        self.momentum = momentum
        self.dynamic_threshold = dynamic_threshold

        stop_signal = self.check_stop_loss_or_take_profit(price)
        if stop_signal:
            return stop_signal

        # 檢查 momentum 密集條件
        if not self.check_momentum_density():
            return None

        self.last_high = self.update_last_high()
        # 僅在空倉時允許買入
        if self.position is None and momentum > dynamic_threshold:
            self.last_high = price * (1-self.stop_loss)
            return "BUY"
        # 僅在持倉時允許賣出
        elif self.position == "BUY" and momentum < -dynamic_threshold and price < self.last_high:
            # reset momentum signals
            self.momentum_signals.clear()
            return "SELL"
        
        return None

    def execute_trade(self, signal, price):
        """
        執行交易
        """
        if signal == "BUY":
            self.position = "BUY"
            self.entry_price = price
            cost = price * self.fee_rate
            print(f"------Executed BUY at price {price} (Fee: {cost:.2f})")
        elif signal == "SELL":
            # 計算交易收益
            profit = price - self.entry_price
            net_profit = profit - (self.entry_price + price) * self.fee_rate
            earn = net_profit / self.entry_price
            self.total_profit += net_profit
            self.trade_count += 1
            self.total_earn += earn
            avg_earn = self.total_earn / self.trade_count
            print(f"------Executed SELL at price {price} (Earn: {earn*100:.2f} % Avg Earn: {avg_earn*100:.2f} %)")
            print(f"------Net Profit: {net_profit:.2f}, Total Profit: {self.total_profit:.2f})")
            self.position = None
            self.entry_price = None

    def on_new_price(self, price):
        """
        處理新價格數據
        """
        self.signal = None
        self.add_price(price)
        signal = self.check_signal()
        if signal:
            self.signal = signal
            self.execute_trade(signal, price)



def plot_price_with_signals(symbol, prices, timestamps, buy_signals, sell_signals, dyanmic_thresholds, avg_earn, save_root):
    """
    繪製價格走勢圖，並標記 Buy 和 Sell 信號，X 軸顯示時間戳。
    
    :param prices: 價格數據 (list or pandas.Series)
    :param timestamps: 時間戳數據 (list or pandas.Series)
    :param buy_signals: Buy 信號的索引列表 (list of int)
    :param sell_signals: Sell 信號的索引列表 (list of int)
    """
    # 確保 timestamps 為 pandas.Timestamp 格式
    if not isinstance(timestamps[0], pd.DatetimeIndex):
        timestamps = pd.to_datetime(timestamps)

    # 創建圖表
    fig, ax = plt.subplots(figsize=(15, 5))

    # 繪製價格走勢圖
    ax.plot(timestamps, prices, label="Price", linewidth=1.5, color="blue")
    # ax.plot(timestamps, dyanmic_thresholds, label='threshold')

    # 標記 Buy 信號
    for idx in buy_signals:
        ax.scatter(
            timestamps[idx], prices[idx], color="green", marker="^", s=200,
            label="Buy Signal" if idx == buy_signals[0] else ""
        )

    # 標記 Sell 信號
    for idx in sell_signals:
        ax.scatter(
            timestamps[idx], prices[idx], color="red", marker="v", s=200,
            label="Sell Signal" if idx == sell_signals[0] else ""
        )

    # 設置 X 軸為時間並自動格式化日期
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%Y-%m-%d %H:%M"))
    fig.autofmt_xdate()  # 自動旋轉 X 軸標籤

    # 加入標籤與圖例
    ax.set_title(f"({symbol}) Price Trend with Buy/Sell Signals")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Price")
    ax.legend()
    ax.grid(True)
    ax.text(0.05, 0.95, f'Avg Earn: {avg_earn*100:.2f} %', transform=ax.transAxes)
    return fig


def setup_save_root():
    save_root = 'results'
    save_root = Path(save_root)
    save_root.mkdir(parents=True, exist_ok=True)
    unix_time = str(time.time())
    save_root = save_root / unix_time
    save_root.mkdir(parents=True, exist_ok=True)
    return save_root


def test_once_strategy(symbol, strategy, dataset, save_root):
    prices, dyanmic_thresholds, momentums = [], [], []
    buy_signals, sell_signals = [], []
    
    for i, (timestamp, data) in enumerate(dataset.iterrows()):
        open_price = float(data['open_price'])
        strategy.on_new_price(open_price)
        if strategy.signal == 'BUY':
            buy_signals.append(i)
        elif strategy.signal == 'SELL':
            sell_signals.append(i)

        if strategy.dynamic_threshold is not None:
            dyanmic_thresholds.append(strategy.dynamic_threshold)
        if strategy.momentum is not None:
            momentums.append(strategy.momentum)
        prices.append(open_price)

        if i%100 == 0:
            print(f'{timestamp} - {symbol} - open_price: {open_price}')

    prices = prices[strategy.momentum_window-1:]
    timestamps = dataset.index[strategy.momentum_window-1:]
    if strategy.trade_count == 0:
        avg_earn = 0.0
    else:
        avg_earn = strategy.total_earn / strategy.trade_count

    fig = plot_price_with_signals(symbol, prices, timestamps=timestamps, buy_signals=buy_signals, 
                            sell_signals=sell_signals, dyanmic_thresholds=dyanmic_thresholds, 
                            avg_earn=avg_earn, save_root=save_root)
    
    
    save_path = save_root / f'{symbol}-th-{strategy.base_threshold}-len_mw-{strategy.momentum_window}.png'
    fig.savefig(save_path)
    return avg_earn


def test():
    # data
    coin_list = [
        'ETHUSDT'
    ]
    coin_list = [
        'ATAUSDT', 'PEPEUSDT', 'ETHUSDT', 'BTCUSDT', 'BNBUSDT', 'WIFUSDT', 'NEIROUSDT', 'PNUTUSDT', 'FTTUSDT', 'DOGEUSDT'
    ]
    # binance_api = BinanceAPI()
    # ticker_prices = binance_api.get_usdt_ticker(bridge='USDT')
    # coin_list = [coin['symbol'] for coin in ticker_prices]
    coin_list = ['ADAUSDT', 'FUNUSDT']
    
    start_time = datetime(2024, 3, 1, 0, 0)
    end_time = datetime(2024, 4, 1, 0, 0)
    arctic_ops = ArcticDBOperator(url="lmdb://arctic_database", lib_name='Binance')
    save_root = setup_save_root()


    base_threshold_list = [0.008]
    momentum_window_list = [3, 4, 5, 6, 7]

    for symbol in coin_list:
        stop_loss = 0.10
        earn_matrix = pd.DataFrame(index=[f"mw_{mw}" for mw in momentum_window_list], 
                                    columns=[f"th_{th}" for th in base_threshold_list])
        for i, base_threshold in enumerate(base_threshold_list):
            for j, momentum_window in enumerate(momentum_window_list):
                strategy = SimpleMomentumStrategy(
                    base_threshold=base_threshold,
                    stop_loss=stop_loss,
                    momentum_window=momentum_window
                )

                # Read data from database
                try:
                    arctic_obj = arctic_ops.read(data_name=symbol, start_time=start_time, end_time=end_time)
                except Exception as e:
                    print(f'Error: {e}')
                    continue
                dataset = arctic_obj.data

                avg_earn = test_once_strategy(symbol, strategy, dataset, save_root=save_root)
                earn_matrix.iloc[j, i] = avg_earn

        earn_matrix.to_csv(save_root / f'{symbol}_earn_matrix.csv')

        # average earn matrix
        heatmap_data = np.float32(earn_matrix.values)*100
        fig, ax = plt.subplots(figsize=(10, 8))

        cax = ax.matshow(heatmap_data, cmap='RdYlGn')

        # Add color bar
        # TODO: color should be binary linear, means all positive earn should be green, all negative earn should be red
        fig.colorbar(cax)

        # Set axis labels
        ax.set_xticks(range(len(earn_matrix.columns)))
        ax.set_xticklabels(earn_matrix.columns)
        ax.set_yticks(range(len(earn_matrix.index)))
        ax.set_yticklabels(earn_matrix.index)

        # Add text
        for (i, j), val in np.ndenumerate(earn_matrix.values):
            ax.text(j, i, f'{val*100:.2f} %', ha='center', va='center', color='black')

        # Add grid lines
        ax.set_xticks(np.arange(len(earn_matrix.columns) + 1) - 0.5, minor=True)
        ax.set_yticks(np.arange(len(earn_matrix.index) + 1) - 0.5, minor=True)
        ax.grid(which="minor", color="black", linestyle='-', linewidth=2)
        ax.tick_params(which="minor", size=0)

        # Rotate the x labels
        plt.xticks(rotation=45)

        # Add title
        plt.title(f'Earn Matrix for {symbol}')

        # Save the plot
        plt.savefig(save_root / f'{symbol}_earn_matrix_plot.png')
        plt.show()
        
        
if __name__ == '__main__':
    test()