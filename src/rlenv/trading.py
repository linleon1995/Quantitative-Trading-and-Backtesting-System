import gym
import numpy as np


class TradingEnv(gym.Env):
    def __init__(self, render_mode=False):
        super().__init__()
        self.action_space = gym.spaces.Discrete(3)  # 0=sell, 1=hold, 2=buy
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(10,), dtype=np.float32)
        self.data = self._load_data()
        self.current_step = 0
        self.balance = 10000
        self.position = 0  # -1: short, 0: none, 1: long

    def _load_data(self):
        # 載入價格或技術指標（可改成你的 dataframe）
        return np.random.randn(1000, 10)

    def reset(self):
        self.current_step = 0
        self.balance = 10000
        self.position = 0
        return self.data[self.current_step]

    def step(self, action):
        self.current_step += 1
        done = self.current_step >= len(self.data) - 1

        # 假設簡單的報酬策略
        price_change = self.data[self.current_step][0]  # 以第1維為價格變化
        reward = 0

        if action == 0:  # sell
            reward = -price_change
            self.position = -1
        elif action == 2:  # buy
            reward = price_change
            self.position = 1
        # hold 不變

        self.balance += reward * 100  # 放大效果

        return self.data[self.current_step], reward, done, {
            "balance": self.balance,
            "position": self.position
        }
