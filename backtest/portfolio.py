class Portfolio:
    def __init__(self, initial_capital=100000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades = []
        self.equity_curve = [initial_capital]

    def apply_trade(self, trade_return):
        pnl = self.capital * trade_return
        self.capital += pnl
        self.trades.append(trade_return)
        self.equity_curve.append(self.capital)
