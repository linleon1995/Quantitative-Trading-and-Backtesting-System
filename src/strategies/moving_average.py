from pathlib import Path

from src.data_process.data_structure import GeneralTickData


class Strategy:
    def __init__(self, ma_gap_rates, ma_grow_rates, count_threshold):
        self.strategy_name = Path(__file__).name
        self.ma_gap_rates = ma_gap_rates
        self.ma_grow_rates = ma_grow_rates
        self.count_threshold = count_threshold

    def run(self, coin_data: GeneralTickData):
        # TODO:
        ma_data_pool = [data for data in list(coin_data.moving_average_data_pool.values())]
        signal_count = coin_data.signal_count
        ma_singal = False
        if self.isNearMAGreater(ma_data_pool, self.ma_gap_rates):
            signal_count += 1
            isAllMARise = self.isAllMARising(ma_data_pool, self.ma_grow_rates)
            if signal_count >=  self.count_threshold and isAllMARise:
                signal_count = 0
                ma_singal = True
        else:
            signal_count = 0
        coin_data.signal_count = signal_count
        return ma_singal
    
    def isAllMARising(self, ma_data_pool: list, grow_rate_pool: list):
        isPriceRises = []
        for ma_data, grow_rate in zip(ma_data_pool, grow_rate_pool):
            if ma_data[-1] > ma_data[-2]*grow_rate:
                isPriceRises.append(True)
            else:
                return False
        return all(isPriceRises)

    def isNearMAGreater(self, ma_data_pool: list, gap_rate_pool: list):
        isNearMARises = []
        last_ma = ma_data_pool[0][-1]
        for ma_data, grow_rate in zip(ma_data_pool[1:], gap_rate_pool):
            if ma_data[-1] <= last_ma*grow_rate:
                isNearMARises.append(True)
            else:
                return False
            last_ma = ma_data[-1]
        return all(isNearMARises)

    
# class Strategy:
#     def __init__(self, time_periords, diff_rate, growth, acc_steps):
#         self.time_periords = time_periords
#         self.diff_rate = diff_rate
#         self.growth = growth
#         self.acc_steps = acc_steps
#         self.achieve_count = 0
#         self.last_sma_data = {}

#     def run(self, data, symbol):
#         judge, sma_data = self.cal_ma_diff(data)
#         if judge:
#             self.achieve_count += 1
#             if symbol not in self.last_sma_data:
#                 self.last_sma_data[symbol] = sma_data
#                 growing = [True]
#             else:
#                 growing, scores = [], []
#                 for cur_sma, last_sma in zip(sma_data, self.last_sma_data[symbol]):
#                     growing.append(cur_sma > last_sma*self.growth)
#                     # scores.append(cur_sma-last_sma)
#             if self.achieve_count >= self.acc_steps and all(growing):
#                 self.achieve_count = 0
#                 # mean_score = sum(scores) / len(scores)
#                 return True
#         else:
#             self.achieve_count = 0
#         return False

#     def cal_ma_diff(self, data):
#         sma_data = {}
#         for t in self.time_periords:
#             sma = np.mean(data[-t:])
#             sma_data[t] = sma
        
#         sma_data = [sma_data[key] for key in sorted(sma_data.keys(), reverse=True)]

#         last_sma = sma_data[0]
#         judge = []
#         for sma, r in zip(sma_data[1:], self.diff_rate):
#             judge.append(sma > r*last_sma)
#             last_sma = sma
#         # print(sma_data)
#         return all(judge), sma_data
