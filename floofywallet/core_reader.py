"""Read-only local FloofyChain Core RPC checks.

This module never sends wallet secrets, signs, or broadcasts transactions.
Use only a local Core RPC endpoint; never expose RPC to the internet.
"""
import base64
import json
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from .base58check import decode as decode_base58check
from .network_params import MAINNET

class CoreReadError(Exception):
    pass

def parse_gettxout(data, expected_amount=None):
    """None means Core does not report the outpoint as unspent."""
    if data is None:
        return None
    if not isinstance(data, dict):
        raise CoreReadError("Invalid gettxout response")
    confirmations = data.get("confirmations")
    if type(confirmations) is not int or confirmations < 0:
        raise CoreReadError("Invalid confirmation count")
    raw = data.get("value")
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise CoreReadError("Invalid output value")
    try:
        amount = Decimal(str(raw))
    except InvalidOperation as exc:
        raise CoreReadError("Invalid output amount") from exc
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.00000001")):
        raise CoreReadError("Invalid output amount")
    if expected_amount is not None and amount != Decimal(str(expected_amount)):
        raise CoreReadError("Explorer and Core output amounts differ")
    script = data.get("scriptPubKey")
    if not isinstance(script, dict) or not isinstance(script.get("hex"), str):
        raise CoreReadError("Missing output script")
    return {"amount": amount, "confirmations": confirmations,
            "coinbase": data.get("coinbase") is True, "script_hex": script["hex"]}

def verify_p2pkh_outpoint(data, expected_address, expected_amount=None, *, min_confirmations=1):
    """Verify Core's UTXO script locks to the requested mainnet P2PKH address.

    This checks the Core-reported outpoint, not possession of a private key.
    It does not establish that the explorer's full UTXO list is complete.
    """
    if type(min_confirmations) is not int or min_confirmations < 1:
        raise ValueError("Minimum confirmations must be a positive integer")
    try:
        payload = decode_base58check(expected_address)
    except (ValueError, TypeError) as exc:
        raise CoreReadError("Invalid expected address") from exc
    if len(payload) != 21 or payload[0] != MAINNET.p2pkh_prefix:
        raise CoreReadError("Expected a mainnet P2PKH address")
    result = parse_gettxout(data, expected_amount)
    if result is None:
        raise CoreReadError("Outpoint is spent, absent, or unavailable in Core")
    if result["confirmations"] < min_confirmations:
        raise CoreReadError("Outpoint has insufficient confirmations")
    if result["coinbase"] and result["confirmations"] < 100:
        raise CoreReadError("Coinbase output is not mature")
    expected_script = "76a914" + payload[1:].hex() + "88ac"
    if result["script_hex"].lower() != expected_script:
        raise CoreReadError("Output script does not match the wallet address")
    return result


class LocalCoreReader:
    def __init__(self, url, username, password, timeout=5):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost")
                or parsed.port is None or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise ValueError("Core RPC must be a local HTTP address with an explicit port")
        if not isinstance(username, str) or not username or not isinstance(password, str) or not password:
            raise ValueError("Core RPC credentials are required")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 15:
            raise ValueError("Invalid Core RPC timeout")
        self.url, self.username, self.password, self.timeout = url, username, password, timeout

    def _call(self, method, params):
        if method not in ("getblockchaininfo", "gettxout"):
            raise CoreReadError("RPC method not allowed")
        payload = json.dumps({"jsonrpc": "1.0", "id": "floofywallet-readonly",
                              "method": method, "params": params}).encode("utf-8")
        auth = base64.b64encode((self.username + ":" + self.password).encode()).decode()
        req = Request(self.url, data=payload, headers={
            "Content-Type": "application/json", "Authorization": "Basic " + auth}, method="POST")
        try:
            with urlopen(req, timeout=self.timeout) as response:
                body = response.read(262145)
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise CoreReadError("Local Core RPC request failed") from exc
        if len(body) > 262144:
            raise CoreReadError("Core RPC response too large")
        try:
            data = json.loads(body)
        except (ValueError, UnicodeError) as exc:
            raise CoreReadError("Invalid Core RPC JSON") from exc
        if not isinstance(data, dict) or data.get("error") is not None:
            raise CoreReadError("Core RPC returned an error")
        return data.get("result")

    def blockchain_info(self):
        result = self._call("getblockchaininfo", [])
        if not isinstance(result, dict):
            raise CoreReadError("Invalid blockchain information")
        return result

    def verify_address_outpoint(self, txid, vout, expected_address, expected_amount=None):
        """Verify an unspent output belongs to the expected P2PKH address.

        Read-only: confirms the locking script, not control of private keys.
        """
        if not isinstance(txid, str) or len(txid) != 64 or any(
                c not in "0123456789abcdefABCDEF" for c in txid):
            raise ValueError("Invalid txid")
        if type(vout) is not int or vout < 0:
            raise ValueError("Invalid vout")
        raw = self._call("gettxout", [txid, vout, True])
        return verify_p2pkh_outpoint(raw, expected_address, expected_amount)

    def check_outpoint(self, txid, vout, expected_amount=None):
        if not isinstance(txid, str) or len(txid) != 64 or any(c not in "0123456789abcdefABCDEF" for c in txid):
            raise ValueError("Invalid txid")
        if type(vout) is not int or vout < 0:
            raise ValueError("Invalid vout")
        # include_mempool=True avoids presenting a mempool-spent output as unspent.
        return parse_gettxout(self._call("gettxout", [txid, vout, True]), expected_amount)
