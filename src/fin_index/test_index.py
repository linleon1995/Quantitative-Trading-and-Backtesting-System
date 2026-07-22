import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __name__ == '__main__':
    # 设置随机种子，以便结果可重复
    np.random.seed(2)

    # 模拟的时间步长
    num_steps = 100

    # 生成时间序列
    time_range = np.arange(num_steps)

    # 使用随机游走模型生成股价数据
    initial_price = 100
    drift = 0.05  # 漂移率
    volatility = 0.2  # 波动率

    # 使用几何布朗运动模型生成股价数据
    returns = np.random.normal((drift / num_steps), volatility, num_steps)
    price = initial_price * np.exp(np.cumsum(returns))

    # 转换为 pandas Series 对象

    st= time.time()

    for _ in range(100):
        price_series = pd.Series(price)
        # 计算移动标准差
        window_size = 20
        moving_std = price_series.rolling(window=window_size).std()
        # 计算布林通道的上轨和下轨
        moving_average = price_series.rolling(window=window_size).mean()
        upper_bound = moving_average + 2 * moving_std
        lower_bound = moving_average - 2 * moving_std

    elapsed = time.time() - st
    print(elapsed)

    # 绘制股价图和布林通道
    plt.plot(time_range, price, label='Stock Price')
    plt.plot(time_range, moving_average, label='Moving Average')
    plt.plot(time_range, upper_bound, 'r--', label='Upper Bound')
    plt.plot(time_range, lower_bound, 'g--', label='Lower Bound')

    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.title('Simulated Stock Price with Bollinger Bands')
    plt.legend()
    plt.grid(True)
    plt.show()
