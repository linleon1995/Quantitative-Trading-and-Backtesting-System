from typing import Dict, List, Optional

from src.trader.base_trader import BaseTrader
from src.client.binance_api import BinanceAPI, BinanceAPIException
# TODO: Further integration with web3 and Metamask is needed.
#       The current BinanceAPI class focuses on market data,
#       and direct web3/Metamask integration with Binance (a CEX)
#       is atypical. This might be for a hybrid system or future features.


class BinanceTrader(BaseTrader):
    """Trading operations for Binance spot and USDT-margined futures."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        base_url: str = 'https://api.binance.com',
        futures_base_url: str = 'https://fapi.binance.com',
        request_timeout: int = 10,
        use_testnet: bool = False,
        rsa_private_key: Optional[bytes] = None,
        rsa_private_key_path: Optional[str] = None,
        rsa_private_key_password: Optional[bytes] = None,
    ) -> None:
        if use_testnet:
            # base_url = 'https://demo.binance.com/en/trade'
            # futures_base_url = 'https://demo.binance.com/en/futures'
            base_url = 'https://testnet.binance.vision'
            futures_base_url = 'https://testnet.binancefuture.com'

        self.api_key = api_key
        self.api_secret = api_secret
        self.api = BinanceAPI(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            futures_base_url=futures_base_url,
            request_timeout=request_timeout,
            rsa_private_key=rsa_private_key,
            rsa_private_key_path=rsa_private_key_path,
            rsa_private_key_password=rsa_private_key_password,
        )

        # Placeholder for web3/Metamask integration
        self.web3_provider = None
        self.metamask_address = None

        # Cache: symbol -> int leverage that was last applied on the exchange
        # Avoids redundant set_leverage API calls on every order for the same symbol.
        self._leverage_cache: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Spot trading
    # ------------------------------------------------------------------
    def buy(
        self,
        symbol: str,
        amount: float,
        *,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        quote_order_qty: Optional[float] = None,
        time_in_force: Optional[str] = None,
        **extra,
    ) -> Dict:
        """Create a Binance spot buy order."""
        order_type = order_type or ('LIMIT' if price is not None else 'MARKET')
        params: Dict = {
            # 'rsa_private_key': Optional[bytes],
            # 'rsa_private_key_path': Optional[str] = None,
            # 'rsa_private_key_password': Optional[bytes] = None,
            'symbol': symbol.upper(),
            'side': 'BUY',
            'order_type': order_type,
            'quantity': amount if quote_order_qty is None else None,
            'quote_order_qty': quote_order_qty,
            'price': price,
            'time_in_force': time_in_force or ('GTC' if price is not None else None),
        }
        return self._submit_spot_order(params, extra)

    def sell(
        self,
        symbol: str,
            # rsa_private_key=rsa_private_key,
            # rsa_private_key_path=rsa_private_key_path,
            # rsa_private_key_password=rsa_private_key_password,
        amount: float,
        *,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        quote_order_qty: Optional[float] = None,
        time_in_force: Optional[str] = None,
        **extra,
    ) -> Dict:
        """Create a Binance spot sell order."""
        order_type = order_type or ('LIMIT' if price is not None else 'MARKET')
        params: Dict = {
            'symbol': symbol.upper(),
            'side': 'SELL',
            'order_type': order_type,
            'quantity': amount if quote_order_qty is None else None,
            'quote_order_qty': quote_order_qty,
            'price': price,
            'time_in_force': time_in_force or ('GTC' if price is not None else None),
        }
        return self._submit_spot_order(params, extra)

    def _submit_spot_order(self, params: Dict, extra: Dict) -> Dict:
        payload = {k: v for k, v in params.items() if v is not None}
        payload.update(extra)
        try:
            response = self.api.create_spot_order(
                symbol=payload.pop('symbol'),
                side=payload.pop('side'),
                order_type=payload.pop('order_type'),
                quantity=payload.pop('quantity', None),
                quote_order_qty=payload.pop('quote_order_qty', None),
                price=payload.pop('price', None),
                time_in_force=payload.pop('time_in_force', None),
                **payload,
            )
            return {'success': True, 'data': response}
        except BinanceAPIException as exc:
            return {'success': False, 'message': exc.message, 'code': exc.error_code}

    def get_futures_symbols(self) -> set:
        """Return the set of USDT-margined perpetual symbols currently TRADING on futures."""
        return self.api.get_futures_symbols()

    def get_low_volume_symbols(self, min_volume_usdt: float) -> set:
        """Return the set of symbols whose 24 h quoteVolume is BELOW *min_volume_usdt*.

        Used at startup to build an exclusion list so low-liquidity coins are
        never processed.  Returns an empty set on API failure (fail-open).
        """
        try:
            tickers = self.api.get_futures_24h_tickers()
            excluded = {
                t['symbol']
                for t in tickers
                if float(t.get('quoteVolume', 0)) < min_volume_usdt
            }
            return excluded
        except Exception as exc:
            # Fail-open: if we can't fetch volume data, don't block trading
            print(f"get_low_volume_symbols error: {exc}")
            return set()

    def get_futures_klines(
        self,
        symbol: str,
        interval: str = '1m',
        limit: int = 100,
    ) -> Optional[List]:
        """Fetch recent futures klines for warmup purposes.

        Returns raw kline rows [[open_time, open, high, low, close, volume, ...], ...]
        or None on failure.
        """
        return self.api.get_futures_klines(symbol=symbol, interval=interval, limit=limit)

    def get_account_summary(self) -> Dict:
        """Fetch full futures account info for S-8.1 remote metrics.

        Returns the raw /fapi/v2/account dict, or {'success': False, ...} on error.
        Relevant fields: totalWalletBalance, totalMarginBalance, totalUnrealizedProfit,
        positions[].{symbol, positionAmt, unrealizedProfit, entryPrice}.
        """
        try:
            return self.api.get_futures_account_summary()
        except BinanceAPIException as exc:
            return {'success': False, 'message': exc.message, 'code': exc.error_code}

    def get_max_leverage(self, symbol: str) -> int:
        """Return the maximum allowed leverage for *symbol* on Binance Futures.

        Reads the first (highest-cap) leverage bracket for the symbol.
        Falls back to 1 on any error so callers can always proceed safely.
        """
        try:
            brackets = self.api.get_futures_leverage_brackets(symbol)
            if brackets:
                return int(brackets[0].get('initialLeverage', 1))
        except BinanceAPIException:
            pass
        return 1

    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for *symbol*, capped at the exchange maximum.

        Skips the API call when the requested leverage is already cached as
        the current setting (avoids hitting rate limits on every order).

        Returns:
            {'success': True, 'leverage': <applied>} on success, or
            {'success': False, 'message': ..., 'code': ...} on failure.
        """
        symbol = symbol.upper()
        max_lev = self.get_max_leverage(symbol)
        applied = min(leverage, max_lev)

        if self._leverage_cache.get(symbol) == applied:
            return {'success': True, 'leverage': applied, 'cached': True}

        try:
            self.api.set_futures_leverage(symbol, applied)
            self._leverage_cache[symbol] = applied
            return {'success': True, 'leverage': applied, 'cached': False}
        except BinanceAPIException as exc:
            return {'success': False, 'message': exc.message, 'code': exc.error_code}

    def get_balance(self, account_type: str = 'spot') -> Dict:
        """Return balances for the requested Binance account type."""
        account_type = account_type.lower()
        if account_type == 'spot':
            try:
                return self.api.get_spot_balances()
            except BinanceAPIException as exc:
                return {'success': False, 'message': exc.message, 'code': exc.error_code}
        if account_type == 'futures':
            try:
                return self.api.get_futures_account_balance()
            except BinanceAPIException as exc:
                return {'success': False, 'message': exc.message, 'code': exc.error_code}
        raise ValueError("account_type must be 'spot' or 'futures'")

    def get_positions(self, account_type: str = 'spot') -> Dict:
        """Return positions for spot or futures accounts."""
        account_type = account_type.lower()
        if account_type == 'spot':
            try:
                return self.api.get_spot_positions(exclude_assets=['USDT'])
            except BinanceAPIException as exc:
                return {'success': False, 'message': exc.message, 'code': exc.error_code}
        if account_type == 'futures':
            try:
                positions = self.api.get_futures_positions()
            except BinanceAPIException as exc:
                return {'success': False, 'message': exc.message, 'code': exc.error_code}
            normalized = {}
            for entry in positions:
                position_amt = float(entry.get('positionAmt', 0))
                if position_amt == 0:
                    continue
                normalized[entry['symbol']] = {
                    'positionAmt': position_amt,
                    'entryPrice': float(entry.get('entryPrice', 0)),
                    'unRealizedProfit': float(entry.get('unRealizedProfit', 0)),
                    'marginType': entry.get('marginType'),
                    'leverage': float(entry.get('leverage', 0)),
                    'positionSide': entry.get('positionSide'),
                }
            return normalized
        raise ValueError("account_type must be 'spot' or 'futures'")

    # ------------------------------------------------------------------
    # Futures trading helpers
    # ------------------------------------------------------------------
    def open_futures_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        *,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        position_side: Optional[str] = None,
        reduce_only: Optional[bool] = False,
        time_in_force: Optional[str] = None,
        **extra,
    ) -> Dict:
        """Create a futures order to open or adjust a position."""
        order_type = order_type or ('LIMIT' if price is not None else 'MARKET')
        try:
            response = self.api.create_futures_order(
                symbol=symbol.upper(),
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                position_side=position_side,
                reduce_only=reduce_only,
                time_in_force=time_in_force or ('GTC' if price is not None else None),
                **extra,
            )
            return {'success': True, 'data': response}
        except BinanceAPIException as exc:
            return {'success': False, 'message': exc.message, 'code': exc.error_code}

    def close_futures_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        *,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        position_side: Optional[str] = None,
        time_in_force: Optional[str] = None,
        **extra,
    ) -> Dict:
        """Close futures exposure using a reduce-only order."""
        return self.open_futures_position(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            position_side=position_side,
            reduce_only=True,
            time_in_force=time_in_force,
            **extra,
        )

    def close_all_positions(self) -> Dict:
        """
        Close all open futures positions with market reduce-only orders.

        Intended for online-backtest resets: call this before starting a new
        run to ensure a clean slate with no inherited positions.

        Returns:
            {
                'closed': [{'symbol': ..., 'side': ..., 'qty': ..., 'result': ...}],
                'failed': [{'symbol': ..., 'error': ...}],
            }
        """
        positions = self.get_positions(account_type='futures')
        if isinstance(positions, dict) and positions.get('success') is False:
            return {'closed': [], 'failed': [{'symbol': 'ALL', 'error': positions.get('message')}]}

        closed = []
        failed = []
        for symbol, info in positions.items():
            position_amt = info.get('positionAmt', 0)
            if position_amt == 0:
                continue

            # Long position (positive amt) → close with SELL
            # Short position (negative amt) → close with BUY
            close_side = 'SELL' if position_amt > 0 else 'BUY'
            qty = abs(position_amt)

            result = self.close_futures_position(
                symbol=symbol,
                side=close_side,
                quantity=qty,
                order_type='MARKET',
            )
            if result.get('success'):
                closed.append({'symbol': symbol, 'side': close_side, 'qty': qty, 'result': result['data']})
            else:
                failed.append({'symbol': symbol, 'error': result.get('message'), 'code': result.get('code')})

        return {'closed': closed, 'failed': failed}

    # Placeholder methods for web3/Metamask
    def connect_metamask(self):
        """
        Connects to Metamask wallet.
        Placeholder - actual web3 integration needed.
        """
        # Example: using web3.py
        # from web3 import Web3
        # if window.ethereum:
        # self.web3_provider = Web3(window.ethereum)
        # try:
        #     accounts = await window.ethereum.request({ 'method': 'eth_requestAccounts' })
        #     self.metamask_address = accounts[0]
        #     print(f"Connected to Metamask with address: {self.metamask_address}")
        #     return True
        # except Exception as e:
        #     print(f"Error connecting to Metamask: {e}")
        #     return False
        # else:
        #     print("Metamask not detected.")
        #     return False
        print("connect_metamask called - Placeholder for Metamask integration.")
        self.metamask_address = "mock_metamask_address_0x123" # Simulate connection
        return True

    def get_web3_balance(self, token_address=None):
        """
        Gets balance of ETH or a specific ERC20 token from connected Metamask wallet.
        Placeholder - actual web3 integration needed.
        """
        # if self.web3_provider and self.metamask_address:
        #     if token_address:
        #         # Logic to get ERC20 token balance
        #         # erc20_abi = [...]  # ABI for ERC20 token
        #         # token_contract = self.web3_provider.eth.contract(address=token_address, abi=erc20_abi)
        #         # balance = token_contract.functions.balanceOf(self.metamask_address).call()
        #         # return balance
        #         print(f"get_web3_balance for token {token_address} - Placeholder.")
        #         return 100 # Mock token balance
        #     else:
        #         # balance = self.web3_provider.eth.get_balance(self.metamask_address)
        #         # return self.web3_provider.from_wei(balance, 'ether')
        #         print("get_web3_balance for ETH - Placeholder.")
        #         return 1.5 # Mock ETH balance
        # else:
        #     print("Metamask not connected.")
        #     return 0
        print(f"get_web3_balance called (token: {token_address}) - Placeholder.")
        return 5.0 if token_address else 1.5 # Mock balances

if __name__ == '__main__':
    raise SystemExit('Run tests or import BinanceTrader instead of executing this module directly.')
