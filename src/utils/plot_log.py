
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

log = """
2025-05-11 12:18:46,761 - INFO - 2025-05-11 12:18:59 - CVCUSDT, Close Price: 0.1185, Ticks: 100, Total Coins: 397
2025-05-11 12:18:46,908 - INFO - 2025-05-11 12:18:59 - 1MBABYDOGEUSDT, Close Price: 0.0017495, Ticks: 100, Total Coins: 397
2025-05-11 12:18:46,959 - INFO - 2025-05-11 12:18:59 - ARDRUSDT, Close Price: 0.1036, Ticks: 100, Total Coins: 397
"""
# Read log from file
with open('logs/trading_log.log', 'r') as file:
    log = file.read()
    
# 1. 讀取並解析 log
lines = log.strip().split('\n')
records = []
for line in lines:
    parts = line.split(' - ')
    ts_full = parts[2].split(' - ')[0]  # e.g., "2025-05-11 12:18:59"
    coin = parts[3].split(', ')[0]
    ts_min = ts_full[:16]  # "2025-05-11 12:18"
    records.append((ts_min, coin))

df = pd.DataFrame(records, columns=["minute", "coin"])

# 2. 製作透視表
pivot = df.pivot_table(index='minute', columns='coin', aggfunc='size', fill_value=0)

# 3. 畫圖
plt.figure(figsize=(12, 6))
sns.heatmap(pivot.T, cmap='YlGnBu', cbar_kws={'label': 'Occurrences per Minute'})
plt.xlabel("Time (Minute)")
plt.ylabel("Coin")
plt.title("Coin Appearance Heatmap per Minute")
plt.tight_layout()
plt.show()
