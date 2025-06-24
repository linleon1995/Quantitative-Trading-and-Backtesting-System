import abc
from typing import List

import gymnasium as gym
import numpy as np
from collections import deque

from src.data_process.data_structure import \
    GeneralTickData  # Assuming GeneralTickData is the relevant data structure
from src.strategies import Strategy
from src.strategies.base_strategy import Signal


class ContinuousTradingEnv(gym.Env):
    def __init__(self, max_data_points=1000):
        super().__init__()
        self.action_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(10,), dtype=np.float32)
        self.data = deque(maxlen=max_data_points)
        self.reset()

    def load_data(self, tic):
        return self.data.append(tic)

    def reset(self, seed=None):
        self.balance = 10000
        self.current_step = 0
        return self.data[self.current_step]

    def step(self, action):
        self.current_step += 1
        done = self.current_step >= len(self.data) - 1

        price_change = self.data[self.current_step][0]

        # action ∈ [-1, 1] 表示買進/賣出百分比
        action = np.clip(action[0], -1, 1)
        reward = action * price_change * 100  # reward 與方向成正比

        self.balance += reward

        obs = self.data[self.current_step]
        info = {"balance": self.balance}
        return obs, reward, done, info
    

class PPOStrategy(Strategy):
    def __init__(self, model, model_path: str):
        super().__init__()
        self.model_path = model_path
        self.model = self._load_model(model, model_path)
        self.env = ContinuousTradingEnv()

    def _load_model(self, model, model_path: str):
        """
        Loads the PPO model from the specified path.
        
        Args:
            model_path (str): Path to the pre-trained PPO model.
        
        Returns:
            The loaded PPO model.
        """
        # This is a placeholder for actual model loading logic
        # For example, using stable_baselines3 or similar library
        model = model.load(model_path)
        return model
    
    def handle_data(self, product_id: str, data: Signal, product_state: 'ProductState') -> list:
        self.env.load_data(data)
        obs = self.env.reset()
        action, _ = self.model.predict(obs, deterministic=True)
        obs, reward, done, truncated, info = self.env.step(action)
        return [action]
    

class RLStrategyBase(abc.ABC):
    def __init__(self, model_path: str):
        """
        Initializes the RL strategy base.
        
        Args:
            model_path (str): Path to the pre-trained RL model.
        """
        self.model_path = model_path
        self.model = self._load_model(model_path)

    @abc.abstractmethod
    def _load_model(self, model_path: str) -> any:
        """
        Loads the RL model from the specified path.
        This method should be implemented by subclasses to handle specific model types.
        """
        pass

    @abc.abstractmethod
    def get_observation(self, tick_data: GeneralTickData) -> any:
        """
        Transforms the incoming tick_data into an observation format suitable for the RL model.

        Args:
            tick_data (GeneralTickData): The current market data.

        Returns:
            any: The observation for the RL model.
        """
        pass

    @abc.abstractmethod
    def generate_signal(self, observation: any) -> str:
        """
        Generates a trading signal ('BUY', 'SELL', 'HOLD') based on the model's prediction.

        Args:
            observation (any): The observation processed by get_observation.

        Returns:
            str: The trading signal.
        """
        pass

    # Optional: A method to run the strategy for a given tick, similar to StrategyExecuter
    # This can be fleshed out more once the interaction model is clearer.
    def decide_action(self, tick_data: GeneralTickData) -> str:
        """
        Processes the latest tick data and decides on a trading action.
        """
        observation = self.get_observation(tick_data)
        signal = self.generate_signal(observation)
        return signal