# SALAM PROTOCOL DATA HUB v1.7
**Timestamp:** 2026-11-27 04:37:15 UTC / 2026-11-27 12:37:15 SGT (UTC+8) | **Spot Price:** $61,542.26 [BIN]
> ✅ **LIVE DATA — plans allowed** (state: FULL). Spot comes from Binance; futures flow is OKX's measured taker volume, not Binance's (this host is blocked). Live, not modelled: Binance Futures refuses this host, but OKX's rubik endpoint publishes real taker buy/sell per hour.

### AI EXECUTION PROTOCOL: SALAM ANALYST v1.7
**Role:** elite spot-only BTC swing trader, Dual-Inventory (50/50 BTC/USDT), zero leverage. You do not decide anything: you describe what this packet's rules permit.
**Primary Directive:** use only numbers present in this packet. No external data, no recall, no forecasting. A missing number is UNAVAILABLE (never zero) — state what its absence costs the verdict.

**THE FOUR PILLARS — the only drivers. Nothing else may start a trade.**
1. **Structure A — S/R:** tactical bands with confluence scores, macro S/R with touches.
2. **Structure B — Volume Profile:** 7D, 30D AND 4H value areas (VAH/POC/VAL) + nearest HVN.
3. **Fuel — Liquidation tiers:** leverage-derived clusters, reported only where they overlap measured structure.
4. **Trigger — Order Flow:** spot vs perp CVD across 1H/4H/24H, plus open-interest change.

*Veto inputs (can block a trade, never start one): 200D average, ETF flows with trade date, funding percentile, long/short ratio.*

**Structure tests (highest weight)**
*   *Value-area test:* evaluate 7D (inside = balance; above 7D VAH = breakout/premium; below 7D VAL = breakdown/discount) and 30D (below 30D VAL = HTF discount and the return-to-value line) separately.
*   *POC test:* price within 0.25% of any POC means the market is balanced on the defended price. That explains quiet tape; it is not a signal.
*   *Band quality:* an edge sitting beyond the nearest measured volume node is weaker than its score. On a low score, name what carried it and what is missing.
*   *Chop rule:* inside the mid band and more than 1% from BOTH band edges = NO TRADE regardless of CVD. Quote the two distances.
*   *Density test:* compare measured levels above with measured levels below. Thin path = fast travel; dense path = grind.

**Fuel tests**
*   Tiers are leverage arithmetic (100x dies 1% from entry, 50x 2%, 25x 4%, 10x 10%) and they RE-CENTRE with price. Never quote a tier as a fixed target.
*   Report a tier only when it overlaps a measured structure (volume node, >=2 touches, band edge, macro S/R) within 0.5%. List the overlaps; ignore the rest.
*   Convert to coins: notional / price = BTC of forced orders, and as % of open interest.
*   Fuel is symmetric by assumption: say so, and never infer direction from it. Only the terrain around it is asymmetric. Name the exhaust point.
*   In your output, tag every DERIVED figure `estimated` and every venue-specific figure with its venue (`[BIN]` / `[OKX]`). This is a labelling rule for what you write, not a reason to discard a packet figure.

**Trigger tests (confirmation only, only at an anchor)**
*   Read spot vs perp CVD in 1H, 4H and 24H. Compute perp:spot 24H ratio; above 3x means futures-led, i.e. positioning rather than accumulation.
*   OI rising while price is flat and spot CVD is negative = distribution. Say it.
*   No sweep flag = that rail is NOT armed, whatever the band score. When a sweep is present, state its level, direction and time.
*   If ## DATA NOTES lists HTTP 451s, state that perp data is OKX, not Binance — measured, different venue.
*   If the gate is PARTIAL or NONE, plans are withheld — do not invent levels. An unknown state reads as NONE.

**Binding Arithmetic (not optional, never adjusted)**
*   **Rail B stop loss = Entry - (1.5 x ATR 1H).** ATR 1H is printed in section 3; print the ATR and the dollar stop, do not invent one.
*   **Risk per trade = 0.75% of total portfolio value.** Position size = (portfolio x 0.75%) / (entry - stop).
*   **If that size exceeds 30% of the USDT inventory, SKIP** — and report the conflict: "risk budget asks X BTC, the cap allows Y BTC, so this rail is vetoed." Do not silently resize; do not drop the rule.
*   **Rail A invalidation = a DAILY close above (band high + 1 x ATR 1H).** Print the number. A 1H close is noise, not invalidation.

**Execution Rules:**
*   **Rail B (USDT -> BTC):** a BULLISH or MACRO BULLISH sweep into a Major Support that overlaps a Lower Long tier, confirmed by positive Spot CVD -> enter on the reclaim. Stop from the arithmetic. Target = the next MEASURED level above, named; if none exists in this packet, write "no target".
*   **Rail A (BTC -> USDT):** a BEARISH or MACRO BEARISH sweep into a Major Resistance that overlaps an Upper Short tier, confirmed by flat/negative Spot CVD -> trim. Invalidation per the arithmetic. Target = the next MEASURED level below, named; if none exists in this packet, write "no target".

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

## 1. THE ANCHOR (Deep S/R Matrix)
*   **Current Price:** $61,542 (1D SMA200 71,980)
*   **Tactical Bands:**
    *   Upper: $62,817 - $64,424 (Conf: 3/10, round-1k) [+$119M 25x Shorts]
    *   Lower: $58,249 - $59,288 (Conf: 10/10, POC+VAH/VAL+round-1k) [+$119M 25x Longs]
    *   Price is inside $60,477 - $61,810 [+$40M 100x Longs]
*   **Macro S/R (Nearest 3):**
    *   Resistance: $62,338 (8x) [+$40M 100x Shorts], $63,065 (2x) [+$79M 50x Shorts], $64,584 (7x)
    *   Support: $61,031 (2x) [+$40M 100x Longs], $60,000 (1x), $59,131 (1x)
*   **Volume Nodes (7D):** VAH: 60,656 | POC: 58,840 | VAL: 58,761 | Nearest HVN: $59,788 below
*   **Volume Profile (MTF):** 30D VAH 81,971 · POC 77,274 · VAL 61,840
    *   4H (last 30 bars): VAH 64,603 · POC 60,526 · VAL 59,978

## 2. THE FUEL (Liquidation Magnets) [ESTIMATED]
*   **OI weighting (assumed):** 10x 8% / 25x 6% / 50x 4% / 100x 2% of open interest (= 20% in total; the rest assumed cross-margin or lower leverage)
*   **Upper Shorts:** 10x $67,696 ($158.9M) / 25x $64,004 ($119.2M) / 50x $62,773 ($79.4M) / 100x $62,158 ($39.7M)
*   **Lower Longs:** 10x $55,388 ($158.9M) / 25x $59,081 ($119.2M) / 50x $60,311 ($79.4M) / 100x $60,927 ($39.7M)
    *Levels are exact leverage arithmetic. The $ per tier is OI $1,986.0M x the weights above, i.e. an assumed 20% of open interest across these four tiers (the rest assumed cross-margin or lower leverage) — not observed liquidation data. A tier is tagged as overlapping a level when it sits within 0.5% of it.*
*   **Long/Short account ratio (4H):** 2.30 [OKX]

## 3. THE TRUTH (Order Flow)
*   **Price Change (closed 1H [BIN]):** 1H: +0.15% | 4H: +1.38% | 24H: +1.04%
*   **CVD (Spot [BIN] / Perp [OKX-RUBIK]):** 1H: 126.8 / 62.6 | 4H: 496.0 / 1,866.2 | 24H: 1,037.5 / 1,253.6
*   **Open Interest:** 32,270 BTC [OKX] | 4H Change: 0.97% | 24H Change: 2.61%
*   **Derivatives source:** [OKX fallback] Binance Futures answers HTTP 451 and Bybit HTTP 403 from this host. OI, funding and L/S are OKX's BTC-USDT swap; the funding percentile uses its last 100 readings (~33 days), not 90.
*   **Funding:** 0.0098% per 8H [OKX] | percentile (100 pts): 74
*   **ATR 1H:** 436 (Rail B stop distance = 1.5 x this = 654)

## 4. THE TRIGGER
*   **Sweep Status:** NONE (no closed 1H bar beyond a level that closed back inside)

## 5. MACRO VETO INPUTS
*   **ETF Net Flow:** 1D: $-453.0M (25 Nov 2026, settled) | 5D: $-2,505.6M
*   **Funding percentile:** 74 of the last 100 readings (~33 days, OKX)

## DATA NOTES
*   fd1 HTTP 451
*   fh1 HTTP 451
*   funding HTTP 451
*   funding_hist HTTP 451
*   oi HTTP 451
*   oi_hist HTTP 451
*   lsr HTTP 451
*   perp CVD is OKX's measured taker volume (BTC-USDT swap), not Binance — Binance Futures refused this host

---
*Generated by salam_protocol.py — standard library only, closed bars only, no state. UNAVAILABLE is a valid answer; every estimated figure carries its label.*
