import base64
import unittest
from unittest.mock import MagicMock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.client.binance_api import BinanceAPI


class TestBinanceAPISigning(unittest.TestCase):
    def setUp(self) -> None:
        self.session = MagicMock()

    def test_hmac_signature_present(self):
        api = BinanceAPI(api_key='a', api_secret='b', session=self.session)
        signed = api._sign_payload({'timestamp': 1})
        self.assertIn('signature', signed)
        self.assertIsInstance(signed['signature'], str)

    def test_rsa_signature_is_base64_encoded(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        api = BinanceAPI(api_key='test', session=self.session, rsa_private_key=pem)
        payload = {'timestamp': 1234567890, 'symbol': 'BTCUSDT'}
        signed = api._sign_payload(payload)
        self.assertIn('signature', signed)
        decoded = base64.b64decode(signed['signature'])
        self.assertIsInstance(decoded, bytes)


if __name__ == '__main__':
    unittest.main()
