"""FloofyChain V4 mainnet constants mirrored from the Core source.

Source: https://github.com/andyd1986/floofychain/blob/main/src/chainparams.cpp

These are for *address and network identification only*. This module does not
implement key storage, transaction construction, networking, or signing.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkParams:
    name: str
    ticker: str
    p2pkh_prefix: int
    p2sh_prefix: int
    wif_prefix: int
    xpub_version: bytes
    xprv_version: bytes
    p2p_port: int
    coinbase_maturity: int
    genesis_hash: str


MAINNET = NetworkParams(
    name="main",
    ticker="FLOOF",
    p2pkh_prefix=35,
    p2sh_prefix=22,
    wif_prefix=163,
    xpub_version=bytes.fromhex("02facafd"),
    xprv_version=bytes.fromhex("02fac398"),
    p2p_port=6661,
    coinbase_maturity=10,
    genesis_hash="d4c3cabcae34cbf79a2f5198806e16d5176c097973c6b0305ddd8b9e9d139ad0",
)
