# SALAM PROTOCOL DATA HUB v1.6
**Timestamp:** 2026-11-26 17:12:08 UTC / 2026-11-27 01:12:08 SGT (UTC+8) | **Spot Price:** $60,574.78 [BIN]
> ✅ **FULL ORDER FLOW — perp CVD is OKX's measured taker volume, spot is Binance.** Live, not modelled: Binance Futures refuses this host, but OKX's rubik endpoint publishes real taker buy/sell per hour.

## 1. THE ANCHOR (Deep S/R Matrix)
*   **Current Price:** $60,575 (1D SMA200 72,088)
*   **Tactical Bands:**
    *   Upper: $62,800 - $64,441 (Conf: 3/10)
    *   Lower: $58,232 - $59,305 (Conf: 10/10)
    *   Price is inside $59,850 - $61,532
*   **Macro S/R (Nearest 3):**
    *   Resistance: $61,031 (2x) [+$39M 100x Shorts], $62,338 (8x), $63,065 (2x) [+$117M 25x Shorts]
    *   Support: $60,000 (1x) [+$39M 100x Longs], $59,131 (1x), $57,958 (2x)
*   **Volume Nodes (7D):** VAH: 60,656 | POC: 58,840 | VAL: 58,761 | Nearest HVN: $59,788 below
*   **Volume Profile (MTF):** 30D VAH 81,971 · POC 77,274 · VAL 62,288
    *   4H (last 30 bars): VAH 64,603 · POC 60,526 · VAL 59,735

## 2. THE FUEL (Liquidation Magnets) [MODELED]
*   **OI weighting (assumed):** 10x 8% / 25x 6% / 50x 4% / 100x 2% of open interest (= 20% in total; the rest assumed cross-margin or lower leverage)
*   **Upper Shorts:** 10x $66,632 ($155.4M) / 25x $62,998 ($116.6M) / 50x $61,786 ($77.7M) / 100x $61,181 ($38.9M)
*   **Lower Longs:** 10x $54,517 ($155.4M) / 25x $58,152 ($116.6M) / 50x $59,363 ($77.7M) / 100x $59,969 ($38.9M)
    *Levels are exact leverage arithmetic. The $ per tier is OI $1,942.5M x the weights above, i.e. an assumed 20% of open interest across these four tiers (the rest assumed cross-margin or lower leverage) — not observed liquidation data.*
*   **Long/Short account ratio (4H):** 2.23 [OKX]

## 3. THE TRUTH (Order Flow)
*   **CVD (Spot [BIN] / Perp [OKX-RUBIK]):** 1H: 33.9 / -21.0 | 4H: -34.6 / -567.1 | 24H: 602.1 / 1,823.4
*   **Open Interest:** 32,069 BTC [OKX] | 4H Change: 1.87% | 24H Change: 4.74%
*   **Derivatives source:** [OKX fallback] Binance Futures answers HTTP 451 and Bybit HTTP 403 from this host. OI, funding and L/S are OKX's BTC-USDT swap; the funding percentile uses its last 100 readings (~33 days), not 90.
*   **Funding:** 0.0053% per 8H [OKX] | percentile (100 pts): 47
*   **ATR 1H:** 494 (Rail B stop distance = 1.5 x this = 740)

## 4. THE TRIGGER
*   **Sweep Status:** NONE (no closed 1H bar beyond a level that closed back inside)

## 5. MACRO VETO INPUTS
*   **ETF Net Flow:** 1D: $-453.0M (25 Nov 2026, settled) | 5D: $-2,505.6M
*   **Funding percentile:** 47 of the last 100 readings (~33 days, OKX)

## DATA NOTES
*   fd1 HTTP 451
*   fh1 HTTP 451
*   funding HTTP 451
*   funding_hist HTTP 451
*   oi HTTP 451
*   oi_hist HTTP 451
*   lsr HTTP 451
*   perp CVD is OKX's measured taker volume (BTC-USDT swap), not Binance — Binance Futures refused this host

### AI EXECUTION PROTOCOL: SALAM ANALYST v1.7
**Role:** elite spot-only BTC swing trader, Dual-Inventory (50/50 BTC/USDT), zero leverage. You do not decide anything: you describe what this packet's rules permit.
**Primary Directive:** use only numbers present in this packet. No external data, no recall, no forecasting. A missing number is UNAVAILABLE, never zero.

**THE FOUR PILLARS — the only drivers. Nothing else may start a trade.**
1. **Structure A — S/R:** tactical bands with confluence scores, macro S/R with touches.
2. **Structure B — Volume Profile:** 7D, 30D AND 4H value areas (VAH/POC/VAL) + nearest HVN.
3. **Fuel — Liquidation tiers:** leverage-derived clusters, reported only where they overlap measured structure.
4. **Trigger — Order Flow:** spot vs perp CVD across 1H/4H/24H, plus open-interest change.

*Veto inputs (can block a trade, never start one): 200D average, ETF flows with trade date, funding percentile, long/short ratio.*

**Structure tests (highest weight)**
*   *Value-area test:* inside 7D value = balance; below 30D VAL = discount and that level is the return-to-value line; above VAH = premium. Say which applies.
*   *POC test:* price within 0.25% of any POC means the market is balanced on the defended price. That explains quiet tape; it is not a signal.
*   *Band quality:* an edge sitting beyond the nearest measured volume node is weaker than its score. On a low score, name what carried it and what is missing.
*   *Chop rule:* inside the mid band and more than 1% from BOTH band edges = NO TRADE regardless of CVD. Quote the two distances.
*   *Density test:* compare measured levels above with measured levels below. Thin path = fast travel; dense path = grind.

**Fuel tests**
*   Tiers are leverage arithmetic (100x dies 1% from entry, 50x 2%, 25x 4%, 10x 10%) and they RE-CENTRE with price. Never quote a tier as a fixed target.
*   Report a tier only when it overlaps a measured structure (volume node, >=2 touches, band edge, macro S/R) within 0.5%. List the overlaps; ignore the rest.
*   Convert to coins: notional / price = BTC of forced orders, and as % of open interest.
*   Fuel is symmetric by assumption: say so, and never infer direction from it. Only the terrain around it is asymmetric. Name the exhaust point.

**Trigger tests (confirmation only, only at an anchor)**
*   Read spot vs perp CVD in 1H, 4H and 24H. Compute perp:spot 24H ratio; above 3x means futures-led, i.e. positioning rather than accumulation.
*   OI rising while price is flat and spot CVD is negative = distribution. Say it.
*   No sweep flag = that rail is NOT armed, whatever the band score. Give its level, direction and time.
*   If the gate is PARTIAL or NONE, plans are withheld — do not invent levels. An unknown state reads as NONE.

**Binding Arithmetic (not optional, never adjusted)**
*   **Rail B stop loss = Entry - (1.5 x ATR 1H).** ATR 1H is printed in section 3; print the ATR and the dollar stop, do not invent one.
*   **Risk per trade = 0.75% of total portfolio value.** Position size = (portfolio x 0.75%) / (entry - stop).
*   **If that size exceeds 30% of the USDT inventory, SKIP** — and report the conflict: "risk budget asks X BTC, the cap allows Y BTC, so this rail is vetoed." Do not silently resize; do not drop the rule.
*   **Rail A invalidation = a DAILY close above (band high + 1 x ATR 1H).** Print the number. A 1H close is noise, not invalidation.

**Execution Rules:**
*   **Rail B (USDT -> BTC):** a BULLISH or MACRO BULLISH sweep into a Major Support that overlaps a Lower Long tier, confirmed by positive Spot CVD -> enter on the reclaim. Stop from the arithmetic. Target = the next MEASURED level above, named; if none exists in this packet, write "no target".
*   **Rail A (BTC -> USDT):** a BEARISH or MACRO BEARISH sweep into a Major Resistance that overlaps an Upper Short tier, confirmed by flat/negative Spot CVD -> trim. Invalidation per the arithmetic. Target = the next MEASURED level below, named.

**Required Output Format (this exact order):**
0. **BOTTOM LINE** — one plain sentence a non-trader can act on ("NO ACTION at $X" or "TRIM 0.25 BTC at $Y") plus the bias in one clause.
1. **Market State** — regime, where price sits against structure, sweep status, gate.
2. **The Four Pillars** — one block each, every number labelled MEASURED or DERIVED.
3. **The Levels Map** — every level with distance in % and its type.
4. **Rail B (Buy) Plan** — trigger, what is missing, stop, the sizing result including the conflict if any, target.
5. **Rail A (Sell/Trim) Plan** — tranches with price windows, invalidation number, target.
6. **If / Then block** — the price alerts as a list; the only part that gets re-read.
7. **Not verified** — OKX-not-Binance, modelled dollars, assumed weights, any UNAVAILABLE.

*Never forecast. State what the rules permit, name the trigger that would change the answer, and stop. Jargon is allowed in 1-7 and never in 0.*

---
*Generated by salam_protocol.py — standard library only, closed bars only, no state. UNAVAILABLE is a valid answer; every estimated figure carries its label.*
