"""
Test both Spot and Futures testnet APIs with separate credentials.
"""
import os

from dotenv import load_dotenv

from src.trader.binance_trader import BinanceTrader

# Load environment variables
load_dotenv()

def test_spot_testnet():
    """Test Spot Testnet API."""
    print("\n" + "=" * 60)
    print("Testing SPOT TESTNET")
    print("=" * 60)
    
    api_key = os.getenv('BINANCE_SPOT_TESTNET_API_KEY')
    api_secret = os.getenv('BINANCE_SPOT_TESTNET_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ Spot testnet credentials not found")
        return False
    
    trader = BinanceTrader(
        api_key=api_key,
        api_secret=api_secret,
        use_testnet=True
    )
    
    try:
        print("\n📊 Getting Spot Balance...")
        balance = trader.get_balance(account_type='spot')
        print(f"✅ Spot Balance: {balance}")
        return True
    except Exception as e:
        print(f"❌ Spot Test Failed: {e}")
        return False


def test_futures_testnet():
    """Test Futures Testnet API."""
    print("\n" + "=" * 60)
    print("Testing FUTURES TESTNET (Demotrading)")
    print("=" * 60)
    
    api_key = os.getenv('BINANCE_FUTURES_TESTNET_API_KEY')
    api_secret = os.getenv('BINANCE_FUTURES_TESTNET_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ Futures testnet credentials not found")
        return False
    
    print(f"\nAPI Key: {api_key[:10]}...")
    print(f"Secret: {api_secret[:10]}...")
    
    trader = BinanceTrader(
        api_key=api_key,
        api_secret=api_secret,
        use_testnet=True
    )
    
    try:
        print("\n📊 Getting Futures Balance...")
        balance = trader.get_balance(account_type='futures')
        print(f"✅ Futures Balance: {balance}")
        
        print("\n📈 Getting Futures Positions...")
        positions = trader.get_positions(account_type='futures')
        print(f"✅ Active Positions: {positions if positions else 'None'}")
        
        # Try to place a small order (min 100 USDT notional value)
        print("\n🔄 Testing MARKET BUY order (0.002 BTC)...")
        buy_result = trader.open_futures_position(
            symbol='BTCUSDT',
            side='BUY',
            quantity=0.002,
            order_type='MARKET'
        )
        
        if buy_result.get('success'):
            order_data = buy_result['data']
            print(f"✅ BUY Order Success!")
            print(f"   Order ID: {order_data.get('orderId')}")
            print(f"   Executed Qty: {order_data.get('executedQty')}")
            print(f"   Avg Price: {order_data.get('avgPrice')}")
            
            # Close position
            print("\n🔄 Closing position (SELL 0.002 BTC)...")
            sell_result = trader.close_futures_position(
                symbol='BTCUSDT',
                side='SELL',
                quantity=0.002,
                order_type='MARKET'
            )
            
            if sell_result.get('success'):
                print(f"✅ SELL Order Success!")
                print(f"   Order ID: {sell_result['data'].get('orderId')}")
                return True
            else:
                print(f"❌ SELL Failed: {sell_result.get('message')}")
                print(f"   Code: {sell_result.get('code')}")
                return False
        else:
            print(f"❌ BUY Failed: {buy_result.get('message')}")
            print(f"   Code: {buy_result.get('code')}")
            return False
            
    except Exception as e:
        print(f"❌ Futures Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Test both APIs
    spot_success = test_spot_testnet()
    futures_success = test_futures_testnet()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Spot Testnet: {'✅ PASS' if spot_success else '❌ FAIL'}")
    print(f"Futures Testnet: {'✅ PASS' if futures_success else '❌ FAIL'}")
    print("=" * 60)
