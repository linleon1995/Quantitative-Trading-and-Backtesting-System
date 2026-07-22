import time

import matplotlib.pyplot as plt
import numpy as np

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

    st= time.time()

    for _ in range(100):
        # 计算移动平均线
        window_size = 20
        moving_average = np.convolve(price, np.ones(window_size)/window_size, mode='valid')

        # 计算移动标准差
        rolling_std = np.zeros_like(moving_average)
        for i in range(len(moving_average)):
            rolling_std[i] = np.std(price[i:i+window_size])

        # 计算布林通道的上轨和下轨
        upper_bound = moving_average + 2 * rolling_std
        lower_bound = moving_average - 2 * rolling_std

    elapsed = time.time() - st
    print(elapsed)

    # 绘制股价图和布林通道
    plt.plot(time_range[window_size-1:], price[window_size-1:], label='Stock Price')
    plt.plot(time_range[window_size-1:], moving_average, label='Moving Average')
    plt.plot(time_range[window_size-1:], upper_bound, 'r--', label='Upper Bound')
    plt.plot(time_range[window_size-1:], lower_bound, 'g--', label='Lower Bound')

    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.title('Simulated Stock Price with Bollinger Bands')
    plt.legend()
    plt.grid(True)
    plt.show()
