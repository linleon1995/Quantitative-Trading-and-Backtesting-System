import numpy as np
from scipy.stats import t

# 假設 price_changes 是包含每個時間點的價格變化率的數組
price_changes = np.array([1.2, -0.5, 0.8, -1.0, 0.6, -1.0, -0.9])
price_changes = np.array([8.118, 5.154, 15.272, 7.048, 2.683, 17.006])

# 計算平均值和標準差
mean_change = np.mean(price_changes)
std_dev = np.std(price_changes, ddof=1)  # 使用 ddof=1 以計算樣本標準差

# 計算置信區間
n = len(price_changes)
confidence_level = 0.95  # 95% 置信水平
t_value = t.ppf((1 + confidence_level) / 2, df=n-1)  # 使用 t 分佈

interval_lower = mean_change - t_value * (std_dev / np.sqrt(n))
interval_upper = mean_change + t_value * (std_dev / np.sqrt(n))

print("平均值:", mean_change)
print("標準差:", std_dev)
print(f"{confidence_level * 100}% 置信區間: ({interval_lower}, {interval_upper})")
