"""
Trading configuration using Pydantic for validation and type safety.
Supports configuration from environment variables and config files.
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class StrategyConfig(BaseModel):
    """Configuration for DynamicBreakoutTrader strategy.
    
    Fields:
        lookback: Number of periods for lookback window (default: 14)
        pr_x: Multiplier for upper breakout threshold, 0-1 range (default: 0.8)
        pr_y: Multiplier for lower breakout threshold, 0-1 range (default: 0.7)
        atr_period: Period for ATR calculation (default: 14)
        adx_period: Period for ADX calculation (default: 14)
        max_risk: Maximum risk per trade as fraction of capital (default: 0.02)
        leverage: Trading leverage multiplier (default: 1)
        drawback: Drawback percentage for exit condition, 0-1 range (default: 0.05)
        hold_minutes: Minimum holding time in minutes before exit (default: 60)
    """
    lookback: int = Field(default=14, ge=1, description="Lookback period for price analysis")
    pr_x: float = Field(default=0.8, ge=0.0, le=1.0, description="Upper breakout threshold multiplier")
    pr_y: float = Field(default=0.7, ge=0.0, le=1.0, description="Lower breakout threshold multiplier")
    atr_period: int = Field(default=14, ge=1, description="ATR calculation period")
    adx_period: int = Field(default=14, ge=1, description="ADX calculation period")
    max_risk: float = Field(default=0.02, ge=0.0, le=1.0, description="Max risk per trade (fraction)")
    leverage: int = Field(default=1, ge=1, le=125, description="Trading leverage")
    drawback: float = Field(default=0.05, ge=0.0, le=1.0, description="Drawback for exit condition")
    hold_minutes: int = Field(default=60, ge=0, description="Minimum holding time in minutes")


class TradingConfig(BaseModel):
    """Main trading configuration.
    
    Fields:
        max_positions: Maximum number of concurrent positions (default: 1)
        trade_value_usdt: Target trade value per order in USDT (default: 100)
        trading_fee_rate: Trading fee rate as decimal, e.g., 0.001 = 0.1% (default: 0.0004)
        max_loss_rate: Stop trading when total return drops below -max_loss_rate.
            Measured from actual exchange balance at startup, NOT from a config assumption.
            e.g., 0.2 means stop when total return < -20% (default: 0.2)
        use_testnet: Use Binance testnet instead of production (default: True)
    """
    max_positions: int = Field(default=1, ge=1, description="Maximum concurrent positions")
    trade_value_usdt: float = Field(default=100.0, gt=0, description="Target value per trade in USDT")
    trading_fee_rate: float = Field(default=0.0004, ge=0.0, le=0.1, description="Trading fee rate (decimal)")
    max_loss_rate: float = Field(default=0.2, gt=0.0, le=1.0, description="Stop when total return < -max_loss_rate (fraction)")
    use_testnet: bool = Field(default=True, description="Use testnet environment")
    reset_on_start: bool = Field(default=False, description="Close all positions and re-baseline portfolio on startup (online backtest mode)")

    @field_validator('max_loss_rate')
    @classmethod
    def validate_max_loss_rate(cls, v: float) -> float:
        if v <= 0 or v > 1:
            raise ValueError('max_loss_rate must be between 0 and 1')
        return v


class KafkaConfig(BaseModel):
    """Kafka consumer configuration.
    
    Fields:
        bootstrap_servers: List of Kafka bootstrap servers (default: ['localhost:29092'])
        topic: Kafka topic to consume from (default: 'binance_kline')
        auto_offset_reset: Kafka auto offset reset policy (default: 'latest')
    """
    bootstrap_servers: list[str] = Field(default=['localhost:29092'], description="Kafka bootstrap servers")
    topic: str = Field(default='binance_kline', description="Kafka topic name")
    auto_offset_reset: str = Field(default='latest', description="Auto offset reset policy")


class LoggingConfig(BaseModel):
    """Logging and notification configuration.
    
    Fields:
        log_level: Logging level (default: 'INFO')
        log_file: Path to log file (default: 'logs/live_trading.log')
        telegram_update_interval: Interval for Telegram updates in seconds (default: 600 = 10 minutes)
        portfolio_tracking_interval: Interval for portfolio tracking in seconds (default: 300 = 5 minutes)
    """
    log_level: str = Field(default='INFO', description="Logging level")
    log_file: str = Field(default='logs/live_trading.log', description="Log file path")
    telegram_update_interval: int = Field(default=600, ge=60, description="Telegram update interval (seconds)")
    portfolio_tracking_interval: int = Field(default=300, ge=60, description="Portfolio tracking interval (seconds)")


class LiveTradingConfig(BaseModel):
    """Complete configuration for live trading system.
    
    This is the root configuration model that contains all sub-configurations.
    """
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        extra = 'forbid'  # Prevent extra fields
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the configuration."""
        return f"""
=== Live Trading Configuration ===
Strategy:
  - Lookback: {self.strategy.lookback}
  - PR_X: {self.strategy.pr_x}, PR_Y: {self.strategy.pr_y}
  - ATR Period: {self.strategy.atr_period}, ADX Period: {self.strategy.adx_period}
  - Drawback: {self.strategy.drawback}, Hold Time: {self.strategy.hold_minutes}min
  - Max Risk: {self.strategy.max_risk}, Leverage: {self.strategy.leverage}

Trading:
  - Max Positions: {self.trading.max_positions}
  - Trade Value: ${self.trading.trade_value_usdt:,.2f}
  - Trading Fee: {self.trading.trading_fee_rate*100:.3f}%
  - Max Loss Rate: -{self.trading.max_loss_rate*100:.1f}% total return
  - Environment: {'TESTNET' if self.trading.use_testnet else 'PRODUCTION'}
  - Reset on Start: {'YES (online backtest mode)' if self.trading.reset_on_start else 'No'}

Kafka:
  - Bootstrap Servers: {self.kafka.bootstrap_servers}
  - Topic: {self.kafka.topic}

Logging:
  - Level: {self.logging.log_level}
  - Log File: {self.logging.log_file}
  - Telegram Updates: Every {self.logging.telegram_update_interval}s
  - Portfolio Tracking: Every {self.logging.portfolio_tracking_interval}s
==================================
"""


def load_config_from_env() -> LiveTradingConfig:
    """Load configuration from environment variables with defaults."""
    import os
    
    config = LiveTradingConfig(
        strategy=StrategyConfig(
            lookback=int(os.getenv('STRATEGY_LOOKBACK', '14')),
            pr_x=float(os.getenv('STRATEGY_PR_X', '0.8')),
            pr_y=float(os.getenv('STRATEGY_PR_Y', '0.7')),
            atr_period=int(os.getenv('STRATEGY_ATR_PERIOD', '14')),
            adx_period=int(os.getenv('STRATEGY_ADX_PERIOD', '14')),
            max_risk=float(os.getenv('STRATEGY_MAX_RISK', '0.02')),
            leverage=int(os.getenv('STRATEGY_LEVERAGE', '1')),
            drawback=float(os.getenv('STRATEGY_DRAWBACK', '0.05')),
            hold_minutes=int(os.getenv('STRATEGY_HOLD_MINUTES', '60')),
        ),
        trading=TradingConfig(
            max_positions=int(os.getenv('MAX_POSITIONS', '1')),
            trade_value_usdt=float(os.getenv('TRADE_VALUE_USDT', '100')),
            trading_fee_rate=float(os.getenv('TRADING_FEE_RATE', '0.0004')),
            max_loss_rate=float(os.getenv('MAX_LOSS_RATE', os.getenv('MAX_DRAWDOWN', '0.2'))),
            use_testnet=os.getenv('USE_TESTNET', 'True').lower() == 'true',
            reset_on_start=os.getenv('RESET_ON_START', 'False').lower() == 'true',
        ),
        kafka=KafkaConfig(
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092').split(','),
            topic=os.getenv('KAFKA_TOPIC', 'binance_kline'),
        ),
        logging=LoggingConfig(
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_file=os.getenv('LOG_FILE', 'logs/live_trading.log'),
            telegram_update_interval=int(os.getenv('TELEGRAM_UPDATE_INTERVAL', '600')),
            portfolio_tracking_interval=int(os.getenv('PORTFOLIO_TRACKING_INTERVAL', '300')),
        ),
    )
    
    return config
