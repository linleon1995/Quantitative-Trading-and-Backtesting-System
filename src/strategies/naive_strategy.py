from src.backtset.wallet import TradeRequest


class NaiveStrategy:
    def __init__(self, buy_rate: float, sell_rate: float, trade_unit: float):
        self.buy_rate = buy_rate
        self.sell_rate = sell_rate
        self.last_price = None
        self.state = 'init'
        self.trade_unit = trade_unit

    def add_tick(self, symbol: str, price: float):
        if self.last_price is None:
            self.last_price = price
            return None

        if self.state == 'init' or self.state == 'sell':
            if price > self.last_price * (1 + self.buy_rate):
                self.last_price = price
                self.state = 'buy'
                return TradeRequest(action=self.state, number=self.trade_unit, symbol=symbol, price=price)
        elif self.state == 'buy':
            return_rate = (price-self.last_price) / self.last_price
            if return_rate > self.sell_rate:
                self.last_price = price
                self.state = 'sell'
                return TradeRequest(action=self.state, number=self.trade_unit, symbol=symbol, price=price)
            
        # self.last_price = price
        return None
    