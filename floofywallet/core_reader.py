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

    def check_outpoint(self, txid, vout, expected_amount=None):
        if not isinstance(txid, str) or len(txid) != 64 or any(c not in "0123456789abcdefABCDEF" for c in txid):
            raise ValueError("Invalid txid")
        if type(vout) is not int or vout < 0:
            raise ValueError("Invalid vout")
        # include_mempool=True avoids presenting a mempool-spent output as unspent.
        return parse_gettxout(self._call("gettxout", [txid, vout, True]), expected_amount)
