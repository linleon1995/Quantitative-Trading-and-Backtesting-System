from src.backtset.wallet import SingletonCoin


def test_coin():
    btc = SingletonCoin('BTC')
    btc2 = SingletonCoin('BTC')
    assert btc == btc2
    assert btc is btc2

    btc.add_coin(number=1, price=50000)
    assert btc2.number == 1
    assert btc2.cost == 50000

    btc.add_coin(number=1, price=40000)
    assert btc2.number == 2
    assert btc2.cost == 45000

    btc.remove_coin(number=1)
    assert btc2.number == 1
    assert btc2.cost == 45000