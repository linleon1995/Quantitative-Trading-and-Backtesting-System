import numpy as np
import pandas as pd


def bollinger_band(prices, window_size=20):
    price_series = pd.Series(prices)
    moving_std = price_series.rolling(window=window_size).std()

    # calculate upper bound and lowe bound
    moving_average = price_series.rolling(window=window_size).mean()
    upper_bound = moving_average + 2 * moving_std
    lower_bound = moving_average - 2 * moving_std

    bollinger_band_result = {
        'upper_bound': upper_bound,
        'moving_average': moving_average,
        'lower_bound': lower_bound,
    }
    return bollinger_band_result 


def once_bollinger_band(prices, std_ratio=2):
    mean = np.mean(prices)
    std = np.std(prices)
    upper_bound = mean + std_ratio * std
    lower_bound = mean - std_ratio * std

    bollinger_band_result = {
        'upper_bound': upper_bound,
        'moving_average': mean,
        'lower_bound': lower_bound,
    }
    return bollinger_band_result

