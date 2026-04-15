# 快速启动指南

## 测试网实盘交易系统

### 1. 快速测试

测试所有功能（Spot和Futures测试网）：
```bash
python3 test_both_testnets.py
```

### 2. 启动实盘交易

确保Kafka正在运行并有数据流，然后启动实盘交易系统：
```bash
python3 live_trading.py
```

### 3. 查看日志

实时查看交易日志：
```bash
tail -f logs/live_trading.log
```

查看最近的交易：
```bash
tail -100 logs/live_trading.log | grep -E "OPENED|CLOSED|SUMMARY"
```

## 日志格式说明

### 开仓日志示例
```
================================================================================
📈 LONG POSITION OPENED - BTCUSDT
   Time: 2026-02-26 10:30:45
   Order ID: 12547269296
   Entry Price: $95,234.50
   Quantity: 0.002 BTC
   Trade Value: $190.47
   Strategy Signal: Breakout (Price >= Dynamic High)
================================================================================
```

### 平仓日志示例
```
================================================================================
📉 POSITION CLOSED - BTCUSDT
   Time: 2026-02-26 11:45:23
   Order ID: 12547269300
   Exit Reason: PROFIT_TAKE
   Entry Price: $95,234.50 (at 10:30:45)
   Exit Price: $96,123.80
   Quantity: 0.002 BTC
   Holding Time: 74.6 minutes
   P&L: +0.93% (+$1.78)
   Total Trades: 15
   Average Return: 1.25%
================================================================================
```

### 投资组合汇总（每5分钟）
```
================================================================================
📊 PORTFOLIO SUMMARY
================================================================================
Time: 2026-02-26 12:00:00
Total Symbols Traded: 23
Total Trades Executed: 156
Active Positions: 3
Average Return: 1.45%
Best Return: 5.67%
Worst Return: -2.34%

Top 3 Performers:
   ETHUSDT: +5.67%
   SOLUSDT: +3.21%
   BTCUSDT: +2.45%

Worst 3 Performers:
   ADAUSDT: -2.34%
   DOTUSDT: -1.23%
   LINKUSDT: -0.56%
================================================================================
```

## 配置文件

所有配置都在 `.env` 文件中：
```bash
# 编辑配置
nano .env

# 关键配置项
USE_TESTNET=True              # 使用测试网
ACCOUNT_TYPE=futures          # 账户类型 (spot/futures)
INITIAL_CAPITAL=100000        # 初始资金
MAX_POSITIONS=1               # 最大持仓数
LEVERAGE=1                    # 杠杆倍数
```

## 账户余额

### Spot Testnet
- USDT: 10,000
- BTC: 1.0
- ETH: 1.0
- 其他测试币种

### Futures Testnet  
- USDT: 5,000
- BTC: 0.01

## 注意事项

1. **最小订单金额**: 100 USDT (约0.002 BTC @ $50,000)
2. **交易费用**: 测试网通常不收费，但会模拟费用
3. **数据延迟**: 实时数据依赖Kafka数据流
4. **停止交易**: 按 `Ctrl+C` 优雅退出

## 故障排除

### Kafka未运行
```bash
# 检查Kafka状态
docker-compose ps

# 启动Kafka
docker-compose up -d
```

### API连接失败
```bash
# 测试API连接
python3 test_both_testnets.py

# 检查API密钥配置
cat .env | grep API_KEY
```

### 日志文件满了
```bash
# 清理旧日志
> logs/live_trading.log

# 或归档
mv logs/live_trading.log logs/live_trading_$(date +%Y%m%d).log
```

## Telegram通知

如果已配置Telegram Bot，交易通知会实时发送到你的Telegram。

## 支持的交易对

所有Binance Futures USDT合约，包括：
- BTCUSDT
- ETHUSDT  
- SOLUSDT
- 等等...

系统会自动从Kafka数据流中识别交易对。
