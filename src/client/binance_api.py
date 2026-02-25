import base64
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key


class BinanceAPIException(Exception):
    """Represents an error returned by the Binance REST API."""

    def __init__(self, status_code: int, error_code: Optional[int], message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class BinanceAPI:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: str = 'https://api.binance.com',
        futures_base_url: str = 'https://fapi.binance.com',
        request_timeout: int = 10,
        session: Optional[requests.Session] = None,
        recv_window: int = 5000,
        rsa_private_key: Optional[bytes] = None,
        rsa_private_key_path: Optional[str] = None,
        rsa_private_key_password: Optional[bytes] = None,
    ) -> None:
        self.base_url = base_url
        self.futures_base_url = futures_base_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.request_timeout = request_timeout
        self.session = session or requests.Session()
        self.recv_window = recv_window
        self._spot_time_offset = 0
        self._futures_time_offset = 0
        self._rsa_private_key = None

        if rsa_private_key and rsa_private_key_path:
            raise ValueError('Provide either rsa_private_key or rsa_private_key_path, not both.')
        if rsa_private_key_path:
            with open(rsa_private_key_path, 'rb') as handle:
                rsa_private_key = handle.read()
        if isinstance(rsa_private_key_password, str):
            rsa_private_key_password = rsa_private_key_password.encode('utf-8')
        if rsa_private_key:
            self._rsa_private_key = load_pem_private_key(
                rsa_private_key,
                password=rsa_private_key_password,
            )

    # ------------------------------------------------------------------
    # Public market data endpoints
    # ------------------------------------------------------------------

    def get_symbols(self) -> list:
        url = f'{self.base_url}/api/v3/exchangeInfo'
        response = self.session.get(url=url, timeout=self.request_timeout)
        if response.status_code == 200:
            data = response.json()
            symbols = [symbol['symbol'] for symbol in data['symbols']]
            return symbols
        else:
            print("Error:", response.status_code)
            return []
        
    # TODO: take care the exceptiion of return data more than 1000 counts.
    def get_klines(self, symbol='BTCUSDT', interval='1m', startTime=None, endTime=None, timeZone='8', limit=1440):
        url = f'{self.base_url}/api/v3/klines'
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': startTime,
            'endTime': endTime,
            'timeZone': timeZone,
            'limit': limit
        }
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        if response.status_code == 200:
            return response.json()
        else:
            print("Error:", response.status_code)
            return None

    def get_earliest_kline_timestamp(self, symbol, interval="1d"):
        # Start from 2017-01-01 00:00:00 UTC (Binance start date)
        start_time = int(datetime(2017, 1, 1).timestamp() * 1000)
        end_time = int(time.time() * 1000)

        earliest = None

        # Binary search to find earliest available Kline
        while start_time <= end_time:
            mid_time = (start_time + end_time) // 2
            url = f"{self.base_url}/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": mid_time,
                "limit": 1
            }
            r = self.session.get(url, params=params, timeout=self.request_timeout)
            data = r.json()

            if isinstance(data, list) and len(data) > 0:
                # Data found, move end_time left
                earliest = data[0][0]
                end_time = mid_time - 1
            else:
                # No data, move start_time right
                start_time = mid_time + 1
            time.sleep(0.2)  # Avoid rate limit

        if earliest:
            dt_utc = datetime.fromtimestamp(earliest / 1000, tz=timezone.utc)
            dt_local = dt_utc.astimezone(timezone(timedelta(hours=8)))
            return dt_local
            # 假設 earliest 是毫秒時間戳
        else:
            return None
        
    def get_ticker_price(self, symbol: str = None, symbols: List = None):
        url = f'{self.base_url}/api/v3/ticker/price'
        params = {
            'symbol': symbol,
            'symbols': symbols,
        }
        # if symbols is not None:
        #     url = f'{self.base_url}/api/v3/ticker/price?symbols={symbols}'
        # elif symbol is not None:
        #     url = f'{self.base_url}/api/v3/ticker/price?symbol={symbol}'
        # else:
        #     url = f'{self.base_url}/api/v3/ticker/price'
        response = self.session.get(url, params=params, timeout=self.request_timeout)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code}")
            return None

    def rolling_window_price_change_stats(self, symbols, windowSize='1m'):
        symbols_string = self._get_symbols_string(symbols, maxlen=len(symbols), max_num_coins=len(symbols))
        symbols_string = symbols_string[0]
        url = f'{self.base_url}/api/v3/ticker?symbols={symbols_string}&windowSize={windowSize}'
        response = self.session.get(url, timeout=self.request_timeout)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code}")
            return None

    def get_usdt_ticker(self, symbols=None, bridge=None):
        new_ticker_price = []
        ticker_price = self.get_ticker_price(symbols=symbols)
        for coin in ticker_price:
            if coin['symbol'].endswith(bridge):
                new_ticker_price.append(coin)
        return new_ticker_price

    @staticmethod
    def _get_symbols_string(symbols: List, maxlen, max_num_coins, exclude_keys=None) -> List:
        if exclude_keys is not None:
            new_symbols = []
            for symbol in symbols:
                exclude_judge = []
                for key in exclude_keys:
                    exclude_judge.append(key not in symbol)
                if all(exclude_judge):
                    new_symbols.append(symbol)
            symbols = new_symbols

        symbol_groups = []
        maxlen = maxlen or len(symbols)
        max_num_coins = min(max_num_coins, len(symbols))
        for i in range(0, max_num_coins, maxlen):
            symbol_str = []
            for symbol in symbols[i:i+maxlen]:
                symbol_str.append(f'"{symbol}"')
            symbol_str = ','.join(symbol_str)
            symbol_str: str = f'[{symbol_str}]'
            symbol_groups.append(symbol_str)
        return symbol_groups

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        return headers

    def _sign_payload(self, params: Dict) -> Dict:
        # Ensure numeric values are properly formatted as strings
        formatted_params = {}
        for key, value in params.items():
            if isinstance(value, float):
                # Format floats consistently to avoid signature issues
                formatted_params[key] = f"{value:.8f}".rstrip('0').rstrip('.')
            elif isinstance(value, bool):
                formatted_params[key] = str(value).lower()
            else:
                formatted_params[key] = str(value)
        
        query_string = '&'.join([f"{key}={formatted_params[key]}" for key in sorted(formatted_params.keys())])
        
        if self._rsa_private_key is not None:
            signature_bytes = self._rsa_private_key.sign(
                query_string.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            formatted_params['signature'] = base64.b64encode(signature_bytes).decode('ascii')
            return formatted_params  # Return formatted params!

        if not self.api_secret:
            raise BinanceAPIException(401, None, 'API secret is required for signed endpoints.')

        signature = hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        formatted_params['signature'] = signature
        return formatted_params  # Return formatted params!

    def _signed_request(self, method: str, endpoint: str, params: Optional[Dict] = None, futures: bool = False, _retry: bool = True) -> Dict:
        base_params = dict(params or {})
        payload = dict(base_params)
        payload.setdefault('recvWindow', self.recv_window)
        payload['timestamp'] = self._current_timestamp(futures)
        signed_params = self._sign_payload(payload)
        base = self.futures_base_url if futures else self.base_url
        
        # Build URL with query string directly (don't use params parameter)
        # to avoid requests library reformatting our parameters
        # IMPORTANT: signature must be last, other params should be sorted as they were when signed
        signature = signed_params.pop('signature')
        query_pairs = [f"{k}={v}" for k, v in sorted(signed_params.items())]
        query_string = '&'.join(query_pairs) + f'&signature={signature}'
        url = f'{base}{endpoint}?{query_string}'
        
        # For Binance API, all signed endpoints use query parameters
        response = self.session.request(
            method=method,
            url=url,
            headers=self._get_headers(),
            timeout=self.request_timeout,
        )
        try:
            return self._handle_response(response)
        except BinanceAPIException as exc:
            if exc.error_code == -1021 and _retry:
                self._sync_time(futures)
                return self._signed_request(
                    method,
                    endpoint,
                    base_params,
                    futures=futures,
                    _retry=False,
                )
            raise

    def _public_request(self, method: str, endpoint: str, params: Optional[Dict] = None, futures: bool = False) -> Dict:
        params = params or {}
        base = self.futures_base_url if futures else self.base_url
        url = f'{base}{endpoint}'
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            headers=self._get_headers() if futures else None,
            timeout=self.request_timeout,
        )
        return self._handle_response(response)

    @staticmethod
    def _handle_response(response: requests.Response) -> Dict:
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise BinanceAPIException(response.status_code, None, 'Empty response from Binance.')

        # Only print on error
        if response.status_code < 200 or response.status_code >= 300:
            print(f"API Error: {response.status_code}, {data}")
            
        if 200 <= response.status_code < 300:
            return data

        error_code = data.get('code') if isinstance(data, dict) else None
        message = data.get('msg') if isinstance(data, dict) else str(data)
        raise BinanceAPIException(response.status_code, error_code, message)

    def _current_timestamp(self, futures: bool) -> int:
        offset = self._futures_time_offset if futures else self._spot_time_offset
        return int(time.time() * 1000) + offset

    def _sync_time(self, futures: bool) -> None:
        endpoint = '/fapi/v1/time' if futures else '/api/v3/time'
        response = self._public_request('GET', endpoint, futures=futures)
        server_time = int(response.get('serverTime'))
        current = int(time.time() * 1000)
        offset = server_time - current
        if futures:
            self._futures_time_offset = offset
        else:
            self._spot_time_offset = offset

    # ------------------------------------------------------------------
    # Spot trading endpoints
    # ------------------------------------------------------------------

    def create_spot_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[float] = None,
        quote_order_qty: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[str] = None,
        **extra,
    ) -> Dict:
        payload: Dict = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
        }
        if quantity is not None:
            payload['quantity'] = quantity
        if quote_order_qty is not None:
            payload['quoteOrderQty'] = quote_order_qty
        if price is not None:
            payload['price'] = price
        if time_in_force is not None:
            payload['timeInForce'] = time_in_force
        payload.update(extra)
        return self._signed_request('POST', '/api/v3/order', payload)

    def get_spot_account_info(self) -> Dict:
        return self._signed_request('GET', '/api/v3/account')

    def get_spot_balances(self, min_free: float = 0.0) -> Dict[str, float]:
        account = self.get_spot_account_info()
        balances: Dict[str, float] = {}
        for asset in account.get('balances', []):
            free = float(asset.get('free', 0))
            locked = float(asset.get('locked', 0))
            total = free + locked
            if total > min_free:
                balances[asset['asset']] = total
        return balances

    def get_spot_positions(self, min_free: float = 0.0, exclude_assets: Optional[List[str]] = None) -> Dict[str, float]:
        exclude_assets = exclude_assets or []
        balances = self.get_spot_balances(min_free=min_free)
        return {asset: amount for asset, amount in balances.items() if asset not in exclude_assets}

    # ------------------------------------------------------------------
    # Futures trading endpoints
    # ------------------------------------------------------------------

    def create_futures_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        position_side: Optional[str] = None,
        reduce_only: Optional[bool] = None,
        time_in_force: Optional[str] = None,
        **extra,
    ) -> Dict:
        payload: Dict = {
            'symbol': symbol,
            'side': side.upper(),
            'type': order_type.upper(),
            'quantity': quantity,
        }
        if price is not None:
            payload['price'] = price
        if position_side is not None:
            payload['positionSide'] = position_side
        if reduce_only is not None:
            payload['reduceOnly'] = str(reduce_only).lower()
        if time_in_force is not None:
            payload['timeInForce'] = time_in_force
        payload.update(extra)
        return self._signed_request('POST', '/fapi/v1/order', payload, futures=True)

    def get_futures_account_balance(self) -> Dict:
        balances = self._signed_request('GET', '/fapi/v2/balance', futures=True)
        return {entry['asset']: float(entry['balance']) for entry in balances}

    def get_futures_positions(self) -> List[Dict]:
        return self._signed_request('GET', '/fapi/v2/positionRisk', futures=True)


if __name__ == '__main__':
        
    # Example usage
    binance_api = BinanceAPI()
    # klines_data = binance_api.get_klines(symbol='BTCUSDT', startTime=1710832400000, endTime=1710839400000)
    klines_data = binance_api.get_klines(symbol='BTCUSDT')
    print(klines_data)

    # symbols_string = binance_api.get_symbols_string(symbols=['BTCUSDT', 'ETHUSDT'], maxlen=2, max_num_coins=2)
    # print(symbols_string)
    rolling_window_price = binance_api.rolling_window_price_change_stats(symbols=['BTCUSDT', 'ETHUSDT'])
    print(rolling_window_price)

    # binance_api.get_ticker_price(symbol='BTCUSDT')

