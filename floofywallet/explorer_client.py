"""Read-only FloofyChain explorer client.

No private keys are ever sent to the explorer. Explorer responses are untrusted:
balances are decimal strings, and callers must not treat them as verified consensus.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://explorer.floofychain.com"
MAX_RESPONSE_BYTES = 1_000_000


class ExplorerError(Exception):
    """Explorer request or response could not be trusted."""


@dataclass(frozen=True)
class AddressSummary:
    address: str
    balance: Decimal
    received: Decimal
    sent: Decimal
    txcount: int
    source: str


def parse_address_summary(data, requested_address):
    if not isinstance(data, dict) or data.get("address") != requested_address:
        raise ExplorerError("Explorer returned a different address")
    amounts = []
    for field in ("balance", "received", "sent"):
        raw = data.get(field)
        if not isinstance(raw, str):
            raise ExplorerError(f"Invalid {field} format")
        try:
            value = Decimal(raw)
        except InvalidOperation as exc:
            raise ExplorerError(f"Invalid {field} amount") from exc
        if not value.is_finite() or value < 0 or value.as_tuple().exponent < -8:
            raise ExplorerError(f"Invalid {field} amount")
        amounts.append(value)
    txcount = data.get("txcount")
    if type(txcount) is not int or txcount < 0:
        raise ExplorerError("Invalid transaction count")
    source = data.get("source")
    if not isinstance(source, str):
        raise ExplorerError("Invalid explorer source")
    return AddressSummary(requested_address, *amounts, txcount, source)



def _amount(raw, *, allow_negative=False):
    if not isinstance(raw, str):
        raise ExplorerError("Amount must be a decimal string")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ExplorerError("Invalid decimal amount") from exc
    if not value.is_finite() or (value < 0 and not allow_negative) or value.as_tuple().exponent < -8:
        raise ExplorerError("Invalid decimal amount")
    return value


def _nonnegative_int(value, field):
    if type(value) is not int or value < 0:
        raise ExplorerError(f"Invalid {field}")
    return value


def _txid(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ExplorerError("Invalid transaction ID")
    return value


@dataclass(frozen=True)
class AddressTransaction:
    txid: str
    block_height: int
    timestamp: int
    amount: Decimal
    received: Decimal
    sent: Decimal


@dataclass(frozen=True)
class AddressUtxo:
    txid: str
    vout: int
    height: int
    amount: Decimal


def parse_address_transactions(data, address):
    if not isinstance(data, dict) or data.get("address") != address:
        raise ExplorerError("Mismatched address in transaction history")
    _nonnegative_int(data.get("page"), "page")
    _nonnegative_int(data.get("limit"), "limit")
    items = data.get("transactions")
    if not isinstance(items, list) or len(items) > 10000:
        raise ExplorerError("Invalid transactions list")
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise ExplorerError("Invalid transaction")
        result.append(AddressTransaction(
            _txid(item.get("txid")),
            _nonnegative_int(item.get("blockindex"), "blockindex"),
            _nonnegative_int(item.get("time"), "time"),
            _amount(item.get("amount"), allow_negative=True),
            _amount(item.get("received")),
            _amount(item.get("sent")),
        ))
    return result


def parse_address_utxos(data, address):
    if not isinstance(data, dict) or data.get("address") != address:
        raise ExplorerError("Mismatched address in UTXO response")
    _nonnegative_int(data.get("page"), "page")
    if type(data.get("has_more")) is not bool:
        raise ExplorerError("Invalid pagination flag")
    items = data.get("utxos")
    if not isinstance(items, list) or len(items) > 10000:
        raise ExplorerError("Invalid UTXO list")
    result = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ExplorerError("Invalid UTXO")
        utxo = AddressUtxo(
            _txid(item.get("txid")),
            _nonnegative_int(item.get("vout"), "vout"),
            _nonnegative_int(item.get("height"), "height"),
            _amount(item.get("amount")),
        )
        if (utxo.txid, utxo.vout) in seen:
            raise ExplorerError("Duplicate UTXO")
        seen.add((utxo.txid, utxo.vout))
        result.append(utxo)
    return result


class ExplorerClient:
    def __init__(self, base_url=DEFAULT_BASE_URL, timeout=10):
        if not isinstance(base_url, str) or not base_url.startswith("https://"):
            raise ValueError("Explorer URL must use HTTPS")
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError("Timeout must be between 0 and 60 seconds")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get_address_endpoint(self, address, suffix=""):

        # Validate the address before using it in a URL.
        from .addresses import validate_address
        if not validate_address(address):
            raise ValueError("Invalid FloofyChain address")
        path = "/api/v1/address/" + quote(address, safe="") + suffix
        req = Request(self.base_url + path, headers={"Accept": "application/json", "User-Agent": "FloofyWallet/0.1"})
        try:
            with urlopen(req, timeout=self.timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ExplorerError("Explorer request failed") from exc
        if len(body) > MAX_RESPONSE_BYTES:
            raise ExplorerError("Explorer response too large")
        try:
            data = json.loads(body)
        except (ValueError, UnicodeError) as exc:
            raise ExplorerError("Explorer returned invalid JSON") from exc
        return data

    def get_address(self, address):
        return parse_address_summary(self._get_address_endpoint(address), address)

    def get_address_transactions(self, address):
        """Read and validate a page of address transactions."""
        return parse_address_transactions(self._get_address_endpoint(address, "/txs"), address)

    def get_address_utxo_snapshot(self, address):
        """Return validated first-page UTXOs and explicit pagination status.

        A complete explorer response is still NOT proof of spendability.
        """
        data = self._get_address_endpoint(address, "/utxos")
        utxos = parse_address_utxos(data, address)
        return utxos, data["has_more"]

    def get_address_utxos(self, address):
        """Legacy first-page API; spendability is NOT established."""
        return self.get_address_utxo_snapshot(address)[0]
