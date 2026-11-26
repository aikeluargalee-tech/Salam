# Salam Data Packet Protocol (SDPP) v1.0

One file. Standard library only. No database, no state, no dependencies.

```bash
python3 salam_protocol.py            # writes ./SALAM_DATA_HUB.md
python3 salam_protocol.py --json     # also writes SALAM_DATA_HUB.json
python3 salam_protocol.py --stdout   # print instead of write
python3 salam_protocol.py --check    # endpoint health only
```

Runs in ~2 s. On GitHub: **Actions → Salam Protocol → Run workflow**, then read
`SALAM_DATA_HUB.md` (or the Pages copy) on your phone.

## Pinned definitions (v1.1)

| Item | Definition |
|---|---|
| Confluence score (max 10) | scored on the **7D** profile: +4 if 7D POC inside the band · +3 if 7D VAH or VAL inside · +3 if a round-1000 level inside |
| Tactical bands | 4H `k=2` fractal pivots, width `0.35 × ATR(14) 1D`, merged up to 1.6 widths |
| Sweep detector | last 6 **closed** 1H bars, newest first: macro levels (2+ touches) checked before tactical bands; a reclaim of a macro level reads **MACRO BULLISH/BEARISH SWEEP** |
| Macro S/R | 500 closed 1D bars, `k=2` pivots, 1% clustering, **nearest 3 by distance** each side (clusters within 0.25% of spot excluded as "at price") |
| Liq ladder [MODELED] | levels exact: `price × (1 ± 1/leverage)`; $ per tier = OI$ × **10x 8% / 25x 6% / 50x 4% / 100x 2%** (= 20% of OI in total; the rest assumed cross-margin or lower leverage) |
| Liq overlay | at most one tag per level: the **single nearest** cluster, only if it is **25x or higher**, within **0.25%** — rendered `[+$X M 25x Shorts]`. Strictly a tie-breaker; the confluence score and the sweep flag are the primary signals |
| Volume nodes | 30D, 7D and 4H profiles; **nearest HVN** = nearest bin holding ≥60% of the POC's volume |
| CVD | `Σ (2 × takerBuyBase − volume)` over the last 1/4/24 **closed** 1H bars, spot and perp separately |
| Venue tags | every derivative value carries `[BIN]` or `[OKX]`; the venue is part of the number, not a footnote |
| ETF flows | Farside table; a day counts only when its Total cell parses as a number |
| Binding arithmetic | Rail B stop = entry − 1.5 × ATR 1H · risk 0.75% of portfolio · skip if size > 30% of USDT inventory |

## Host banner

The first line under the timestamp states which host produced the packet:

```
CI (Binance Futures blocked)  > ⚠️ CI HOST DETECTED: PERP CVD UNAVAILABLE. Run locally ...
Binance reachable             > ✅ LOCAL HOST: Full Binance data. Execution-grade.
```

A reason to read it: the CI packet is a levels map, the local packet is an execution packet.

## Tests

```bash
python3 salam_protocol.py --selftest
```

Seven offline assertions (ATR, CVD formula, POC/VAH/VAL ordering, HVN, confluence = 10, 1%
clustering, pivot detection) plus two live ones: **Binance vs OKX spot must agree within 0.50%**,
and **open interest must be > 0**. Runs on every workflow dispatch before the packet is built.

## Older definitions (v1.0, kept for reference)

| Item | Definition |
|---|---|
| Confluence score (max 10) | +4 if 30D POC inside the band · +3 if 30D VAH or VAL inside · +3 if a round-1000 level inside |
| Tactical bands | 4H `k=2` fractal pivots, width `0.35 × ATR(14) 1D`, merged up to 1.6 widths |
| Sweep detector | last 6 **closed** 1H bars against the nearest band each side: `Low < band.low AND Close > band.low` = BULLISH SWEEP; `High > band.high AND Close < band.high` = BEARISH SWEEP |
| Macro S/R | 500 closed 1D bars, `k=2` pivots, 1% clustering, top 3 clusters each side by touch count |
| Liq ladder [MODELED] | levels are exact: `price × (1 ± 1/leverage)`; the $M is `OI$ × 5%` per tier — an assumption, never observed liquidation data |
| CVD | `Σ (2 × takerBuyBase − volume)` over the last 1/4/24 **closed** 1H bars, spot and perp separately |
| ETF flows | Farside table; a day counts only when its Total cell parses as a number |

## Rules the script obeys

- closed bars only — a bar is used only after its close time has passed
- a failed endpoint prints `UNAVAILABLE`; never a stale value, never `0`, never `null`
- every estimate is labelled `[MODELED]` or `[PROXY]`
- no leverage, no shorts: Rail A trims BTC into USDT, Rail B buys BTC with USDT

## Hosting reality (measured from a GitHub Actions runner)

```
451   fapi.binance.com          Binance Futures — blocked by geo
403   api.bybit.com             Bybit — blocked by geo
000   api.deribit.com           unreachable
200   data-api.binance.vision   Binance Spot  <- primary
200   www.okx.com               OKX            <- derivatives fallback
200   api.bitget.com · api.gateio.ws · futures.kraken.com · api.coingecko.com
```

Consequence: on CI the packet takes **spot from Binance** and **OI / funding / L-S from OKX**,
and says so in the packet. **Perp CVD is UNAVAILABLE on CI and cannot be restored** — only Binance
publishes taker-buy volume inside klines, and its futures API refuses the runner. Run the script
from a Binance-reachable machine (your own PC, in Malaysia) for the full packet.
