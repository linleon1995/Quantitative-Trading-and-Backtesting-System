import numpy as np


def mock_stock_price(random_seed = 0, 
                     num_steps: int = 100, 
                     initial_price: float = 100.0, 
                     drift: float = 0.5, 
                     volatility: float = 0.2):
        
    # Set random seed for reproducibility
    np.random.seed(random_seed)

    # Generate stock price data using geometric Brownian motion model
    returns = np.random.normal((drift / num_steps), volatility, num_steps)
    prices = initial_price * np.exp(np.cumsum(returns))
    return prices