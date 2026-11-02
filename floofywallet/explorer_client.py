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
        """Return untrusted JSON; schema validation awaits a real sample."""
        return self._get_address_endpoint(address, "/txs")

    def get_address_utxos(self, address):
        """Return untrusted JSON; never use directly for signing/spending."""
        return self._get_address_endpoint(address, "/utxos")
