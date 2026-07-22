


# Assuming a singleton implementation for Market
class Market:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Market, cls).__new__(cls)
            # cls._instance._init()
        return cls._instance

    # def _init(self, wallet, db_operator):
    #     self.wallet = wallet
    #     self.db_operator = db_operator
    #     self.trades = []

    def __init__(self, wallet, db_operator):
        self.wallet = wallet
        self.db_operator = db_operator
        self.trades = []

    def get_wallet(self):
        return self.wallet

    def get_ticker(self, symbol, start_time, end_time):
        return [tick for tick in self.ticker_data.get(symbol, [])
                if start_time <= tick['time'] <= end_time]

    def add_trade(self, symbol, trade_type, quantity, price):
        trade = {'symbol': symbol, 'type': trade_type, 'quantity': quantity, 'price': price}
        self.trades.append(trade)
        # Update wallet based on trade
        if trade_type == 'buy':
            self.wallet.adjust_balance(-price * quantity)
        elif trade_type == 'sell':
            self.wallet.adjust_balance(price * quantity)