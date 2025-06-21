import pytest

from src.backtset.wallet import Asset


@pytest.fixture
def mock_asset():
    asset = Asset()
    asset.deposit(symbol="USDT", number=10000, cost=1.0)
    return asset


@pytest.mark.parametrize(
    "symbol, number, cost, expected_balance",
    [
        ("USDT", 5000, 1.0, 15000),  # Deposit to existing asset
        ("ETH", 2.0, 3000, 2.0),  # Deposit new asset
    ],
    ids=["deposit_usdt_existing", 
         "deposit_eth_new"],
)
def test_deposit(mock_asset, symbol, number, cost, expected_balance):
    mock_asset.deposit(symbol=symbol, number=number, cost=cost)
    assert mock_asset.get_balance(symbol) == expected_balance


@pytest.mark.parametrize(
    "symbol, number, cost, excetion",
    [
        ("USDT", -5000, 1.0, ValueError),  # Negative deposit
        ("USDT", 0, 1.0, ValueError),  # Negative deposit
        ("ETH", None, 1.0, TypeError),  # Missing number
    ],
    ids=['deposit_negative',
         'deposit_zero',
         'deposit_type_error'],
)
def test_deposit_exception(mock_asset, symbol, number, cost, excetion):
    with pytest.raises(excetion):
        mock_asset.deposit(symbol=symbol, number=number, cost=cost)


@pytest.mark.parametrize(
    "symbol, number, expected_balance",
    [
        ("USDT", 5000, 5000),  # Valid withdrawal
    ],
    ids=["withdraw_valid"],
)
def test_withdraw(mock_asset, symbol, number, expected_balance):
    mock_asset.withdraw(symbol=symbol, number=number)
    assert mock_asset.get_balance(symbol) == expected_balance


@pytest.mark.parametrize(
    "symbol, number, exception",
    [
        ("USDT", 15000, ValueError),  # Over-withdrawal
        ("USDT", -15000, ValueError), # Negative withdrawal
        ("USDT", 0, ValueError), # Zero withdrawal
        ("ETH", 1.0, ValueError),  # Non-existent asset

    ],
    ids=["Over-withdrawal", 
         "Negative withdrawal", 
         "Zero withdrawal",
         "Non-existent asset"],
)
def test_withdraw_exception(mock_asset, symbol, number, exception):
    with pytest.raises(expected_exception=exception):
        mock_asset.withdraw(symbol=symbol, number=number)


@pytest.mark.parametrize(
    "symbol, expected_balance",
    [
        ("USDT", 10000),
        ("ETH", 0.0),  # Non-existent asset
        ("BTC", 0.0),  # Non-existent asset
    ],
    ids=["balance_usdt", "balance_eth_missing", "balance_btc_missing"],
)
def test_get_balance(mock_asset, symbol, expected_balance):
    assert mock_asset.get_balance(symbol) == expected_balance


@pytest.mark.parametrize(
    "symbol, number, expected_result",
    [
        ("USDT", 5000, True),
        ("USDT", 15000, False),
        ("ETH", 1.0, False),  # Non-existent asset
    ],
    ids=["balance_enough_usdt", "balance_not_enough_usdt", "balance_not_enough_eth"],
)
def test_is_balance_enough(mock_asset, symbol, number, expected_result):
    assert mock_asset.is_balance_enough(symbol, number) == expected_result


@pytest.mark.parametrize(
    "symbol, deposits, expected_cost",
    [
        ("USDT", [(1.0, 5000)], 1.0),  # Same cost
        ("ETH", [(3000, 1.0)], 3000),  # New asset
        ("ETH", [(3000, 0.5), (2000, 0.5)], 2500),  # Weighted average cost
    ],
    ids=["cost_usdt_single", "cost_eth_single", "cost_eth_weighted_avg"],
)
def test_get_cost(mock_asset, symbol, deposits, expected_cost):
    for cost, number in deposits:
        mock_asset.deposit(symbol=symbol, number=number, cost=cost)
    assert mock_asset.get_cost(symbol) == expected_cost
