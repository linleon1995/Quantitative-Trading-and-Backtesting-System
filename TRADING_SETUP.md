# 测试网交易功能设置指南

## 概述
此项目现在支持在 Binance 测试网上进行实盘交易。系统会根据策略信号自动下单。

## 前置要求

### 1. 获取 Binance 测试网 API 密钥

**Futures 测试网**：
- 访问：https://testnet.binancefuture.com/
- 使用 GitHub 或 Google 账号登录
- 在右上角点击 API Key 生成新的测试密钥
- 保存 **API Key** 和 **Secret Key**

### 2. 配置环境变量

1. 复制示例配置文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的测试网 API 密钥：
```bash
# Testnet API Keys
BINANCE_TESTNET_API_KEY=你的测试网API密钥
BINANCE_TESTNET_API_SECRET=你的测试网密钥

# Trading Configuration
USE_TESTNET=True
INITIAL_CAPITAL=100000
MAX_POSITIONS=1
LEVERAGE=1
```

### 3. 安装依赖

如果使用 uv：
```bash
uv sync
```

或使用 pip：
```bash
pip install python-dotenv
```

## 测试 API 连接

运行测试脚本验证 API 连接：

```bash
python test_binance_testnet.py
```

这个脚本会：
1. 检查 API 密钥是否正确配置
2. 获取账户余额
3. 查看当前持仓
4. （可选）下一个小额测试订单并立即平仓

## 运行实盘交易

### 方式 1: Kafka 实时数据流 + 实盘交易

确保 Kafka 正在运行并有数据流：

```bash
# 启动实盘交易系统
python live_trading.py
```

系统会：
- 从 Kafka 消费实时市场数据
- 运行 DynamicBreakoutTrader 策略
- 在满足条件时自动下单
- 发送 Telegram 通知（如果已配置）

### 方式 2: 简单测试订单

使用原本的测试脚本：

```bash
python test_trade.py
```

## 文件说明

- **`.env.example`** - 环境变量配置模板
- **`.env`** - 你的实际配置（不会被提交到 Git）
- **`live_trading.py`** - 实盘交易主程序
- **`test_binance_testnet.py`** - API 连接测试脚本
- **`test_trade.py`** - 简单的订单测试脚本

## 安全注意事项

⚠️ **重要**：
- `.env` 文件包含敏感信息，**永远不要提交到 Git**
- 测试网的 API 密钥只能用于测试网，不影响真实资金
- 如果要切换到生产环境，请确保：
  1. 在 `.env` 中设置 `USE_TESTNET=False`
  2. 使用生产环境的 API 密钥
  3. **非常小心**，生产环境会使用真实资金

## 日志

所有交易活动会记录在：
- `logs/live_trading.log` - 实盘交易日志
- `logs/kafka_consumer.log` - Kafka 消费日志

## 故障排除

### 错误：API credentials not found
- 确保已创建 `.env` 文件
- 检查 API 密钥是否正确填写

### 错误：Connection failed
- 检查网络连接
- 确认测试网服务正常：https://testnet.binancefuture.com/

### 订单失败
- 检查账户余额是否足够
- 确认订单数量符合最小交易限制
- 查看日志文件了解详细错误信息

## 下一步

1. 提供你的 API 密钥后，我会帮你测试连接
2. 可以调整策略参数（在 `live_trading.py` 中）
3. 设置 Telegram 通知（如需要）
