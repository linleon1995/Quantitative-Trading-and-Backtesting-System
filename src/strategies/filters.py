import yaml


class TradingStrategy:
    def __init__(self, config_file):
        self.load_config(config_file)

    def load_config(self, config_file):
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
        
        self.volume_threshold = config.get('volume_threshold', 5)
        self.price_threshold = config.get('price_threshold', 2)
        self.trend_threshold = config.get('trend_threshold', 50)

    def volume_filter(self, current_volume, previous_volume):
        volume_change = (current_volume - previous_volume) / previous_volume * 100
        return abs(volume_change) > self.volume_threshold

    def price_filter(self, current_price, previous_price):
        price_change = (current_price - previous_price) / previous_price * 100
        return abs(price_change) > self.price_threshold

    def trend_filter(self, price_series):
        # 使用合适的趋势指标计算价格的趋势
        # 这里简单演示使用移动平均线
        moving_average = sum(price_series) / len(price_series)
        return moving_average > self.trend_threshold

    def generate_trade_signal(self, current_volume, previous_volume, current_price, previous_price, price_series):
        signal = {
            'volume_signal': self.volume_filter(current_volume, previous_volume),
            'price_signal': self.price_filter(current_price, previous_price),
            'trend_signal': self.trend_filter(price_series)
        }
        return signal

# 使用 YAML 文件配置
config_file = 'trading_strategy_config.yaml'
strategy = TradingStrategy(config_file)

# 示例数据
current_volume = 1000
previous_volume = 800
current_price = 50
previous_price = 48
price_series = [45, 47, 50, 52, 55]

# 生成交易信号
trade_signal = strategy.generate_trade_signal(current_volume, previous_volume, current_price, previous_price, price_series)

print("Trade Signal:")
print(trade_signal)