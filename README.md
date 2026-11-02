# FloofyWallet 🐾

**FloofyWallet** is an experimental, lightweight, non-custodial desktop wallet project for FloofyChain (FLOOF).

## Goal

A simple Windows wallet to **receive**, **send**, and **view FLOOF transactions** without requiring each user to download the blockchain or run FloofyChain Core.

## Status: early development — not for real funds

Only initial FloofyChain V4 network constants, Base58Check utilities and legacy-address format checks are implemented. **There is no working wallet, no key storage, no network synchronization, and no transaction signing or broadcasting.** Do not store or send real FLOOF with this code.

### Scope

- Create or import a wallet; secure local recovery and encrypted storage (planned)
- View balance and transaction history (planned)
- Receive FLOOF with an address and QR code (planned)
- Send FLOOF with local signing and transaction review (planned)
- Simple Windows desktop interface (planned)

No mining, burning, leaderboard, or full-node download.

### Architecture

The desktop wallet will keep private keys local. It will contact a **FloofyChain V4-compatible, read-focused indexer/server** to retrieve UTXOs, confirmed history and balances, and to broadcast *locally signed* transactions. We still need to validate and select that indexer/server. Never expose a raw FloofyChain Core RPC endpoint to the public internet.

## First milestone: chain compatibility

The initial module mirrors parameters in [FloofyChain Core V4 `src/chainparams.cpp`](https://github.com/andyd1986/floofychain/blob/main/src/chainparams.cpp):

| Parameter | Mainnet value |
| --- | --- |
| P2PKH address prefix | 35 |
| P2SH address prefix | 22 |
| WIF prefix | 163 |
| BIP32 public version | `02facafd` |
| BIP32 private version | `02fac398` |
| P2P port | 6661 |
| Coinbase maturity | 10 blocks |

This stage can only check address formatting. Next we must verify generated addresses, key derivation, transaction serialization, dust/fee handling and signatures against independent FloofyChain Core test vectors **before enabling sending**.

## Run tests

Requires Python 3.10+; no third-party dependencies for this milestone.

```bash
python -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).
