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

## Pinned definitions

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
