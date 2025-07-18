from typing import Any
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import requests


def connect_bitcoin_rpc(config: dict) -> Any:
    """
    Connects to Bitcoin Core RPC using the provided config dict.
    If 'proxy' is in config, uses requests with SOCKS proxy for .onion addresses.
    Returns an AuthServiceProxy instance or a RequestsBitcoinRPC instance.
    Raises on error (invalid config, connection failure).
    Story 4.2.
    """
    url = f"http://{config['user']}:{config['password']}@{config['host']}:{int(config['port'])}"
    proxy = config.get("proxy")
    if proxy:
        # Use requests for .onion via SOCKS proxy
        return RequestsBitcoinRPC(url, proxy)
    else:
        rpc = AuthServiceProxy(url)
        # Test connection
        rpc.getblockchaininfo()
        return rpc


class RequestsBitcoinRPC:
    def __init__(self, url, proxy):
        self.url = url
        self.proxies = {"http": proxy, "https": proxy}
        self.auth = None
        # Parse user:pass@host:port from url
        import re

        m = re.match(r"http://([^:]+):([^@]+)@([^:]+):(\d+)", url)
        if m:
            self.auth = (m.group(1), m.group(2))
            self.rpc_url = f"http://{m.group(3)}:{m.group(4)}"
        else:
            raise ValueError(f"Invalid RPC URL: {url}")

    def _call(self, method, params=None):
        if params is None:
            params = []
        payload = {
            "jsonrpc": "1.0",
            "id": "btcmesh",
            "method": method,
            "params": params,
        }
        resp = requests.post(
            self.rpc_url, json=payload, auth=self.auth, proxies=self.proxies, timeout=30
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("error"):
            raise Exception(result["error"])
        return result["result"]

    def getblockchaininfo(self):
        return self._call("getblockchaininfo")

    def sendrawtransaction(self, raw_tx_hex, max_fee_rate=0.0):
        # Bitcoin Core RPC sendrawtransaction takes an optional maxfeerate.
        # Setting to 0.0 means no limit.
        return self._call("sendrawtransaction", [raw_tx_hex, max_fee_rate])


def broadcast_transaction_via_rpc(rpc, raw_tx_hex: str):
    """
    Broadcasts a raw transaction hex via Bitcoin Core RPC sendrawtransaction.
    Returns (txid, None) on success, (None, error_message) on failure.
    Story 4.3.
    """
    if rpc is None:
        return None, "No RPC connection"
    try:
        # For AuthServiceProxy, python-bitcoinrpc supports maxfeerate as a keyword or positional.
        # For RequestsBitcoinRPC, we've modified its sendrawtransaction to accept it.
        if isinstance(rpc, RequestsBitcoinRPC):
            txid = rpc.sendrawtransaction(
                raw_tx_hex, 0.0
            )  # Pass 0.0 for no feerate limit
        else:  # AuthServiceProxy
            txid = rpc.sendrawtransaction(
                raw_tx_hex, 0.0
            )  # Pass 0.0 for no feerate limit
        return txid, None
    except JSONRPCException as e:
        msg = e.error.get("message", str(e))
        return None, msg
    except Exception as e:
        return None, str(e)
