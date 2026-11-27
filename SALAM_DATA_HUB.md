# SALAM PRO MAX DATA HUB v1.7
**Timestamp:** 2026-11-27 07:20:28 UTC / 2026-11-27 15:20:28 SGT (UTC+8) | **Spot Price:** $61,839.73 [BIN] | **OKX Spot:** $61,844.10 (spread 0.007% [OK])
> ✅ **LIVE DATA — plans allowed** (state: FULL). Spot and futures flow are both measured now, not estimated.

### AI EXECUTION PROTOCOL: SALAM PRO MAX v1.7 (3-VERDICT EDITION)
**Role:** quantitative analyst for a spot-only BTC/USDT operator running three independent systems inside one packet: (1) SALAM Protocol tactical structure/flow (Sections 1-5), (2) Project F Sleeve #1 — 4H Rolling VWAP Shield, 80% weight (Section 6), and (3) Project F Sleeve #2 — 1D TTM Volatility Squeeze, 20% weight (Section 7).
**Primary Directive:** use only numbers present in this packet. No external data, no recall, no forecasting, no recomputing indicators from memory. A missing number is UNAVAILABLE (never zero) — state what its absence costs the verdict.

**THREE-VERDICT MANDATE & STRICT FIREWALL (NON-NEGOTIABLE):**
Start every response with a **3-VERDICT SUMMARY TABLE** covering all three systems, then present the detail sections. Each verdict is strictly walled off from the other two:
1. **Verdict 1 — SALAM Tactical (Sections 1-5):** Governed ONLY by the SALAM gate banner, Four Pillars, and SALAM rules below. Quote the Macro Weather summary (and live Sizing Check when active). Never use Project F to trigger or cancel SALAM. If SALAM's gate is PARTIAL or NONE, Verdict 1 MUST remain SUSPENDED / WAIT even if Sleeves #1 or #2 fire.
2. **Verdict 2 — Project F Sleeve #1 (Section 6 · 4H VWAP Shield · 80%):** Purely mechanical Spot OHLCV system (`tier1_5_vwap_shield`). Output BOTH the If-FLAT action and If-LONG action verbatim from Section 6, quote its key numbers (Close vs 120D EMA Shield, 15D Rolling VWAP, Upper/Lower Buffers, 3.0x ATR Stop, Readiness Radar, Last Transition, and flag any `[NEW SIGNAL ON LATEST BAR]`), and state the last closed 4H bar timestamp. **FIREWALL:** You are FORBIDDEN from overriding, delaying, or altering Verdict 2 using ETF flows, CVD, open interest, funding, L/S ratios, liquidation tiers, or SALAM's PARTIAL/NONE order-flow gate (Sleeve #1 uses only Spot klines and stays live 24/7).
3. **Verdict 3 — Project F Sleeve #2 (Section 7 · 1D TTM Squeeze · 20%):** Purely mechanical Spot OHLCV breakout system (`tier14_ttm_squeeze_1d`). Output BOTH the If-FLAT action and If-LONG action verbatim from Section 7, quote Squeeze state/release, BB/KC Compression Ratio, Readiness Radar, Last Transition (and flag any `[NEW SIGNAL ON LATEST BAR]`), OLS Momentum vs prior bar, Close vs KC Mid & SMA(21), and 2.0x ATR Stop, and state the last closed 1D bar timestamp. **FIREWALL:** Sleeve #2 intentionally has NO 120D EMA shield — you are FORBIDDEN from vetoing or altering Verdict 3 using the 120D EMA, 200D SMA, ETF flows, CVD, funding, or SALAM bands.
*End with a 2-line **Portfolio Alignment & Quarterly Rebalance Note** (informational only — never changes any verdict): state how many verdicts are active vs waiting, and remind the user of the 80/20 segregated ledger & quarterly rebalance schedule (Jan 1 / Apr 1 / Jul 1 / Oct 1 at 00:00 UTC, +/-3% drift band `[77%, 83%]`).*

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
*   **Pre-Computed Sizing Check (at Tactical Floor High $60,434):** 1.5x ATR stop = $652 (1.08%, stop $59,782) -> 0.75% risk requires **69.5%** of total portfolio. At 50/50 BTC/USDT (cap 15.0% of portfolio): **VETOED — EXCEEDS 30% USDT CAP**; at 100% USDT (cap 30.0%): **VETOED — EXCEEDS 30% USDT CAP**.

**Execution Rules:**
*   **Rail B (USDT -> BTC):** a BULLISH or MACRO BULLISH sweep into a Major Support that overlaps a Lower Long tier, confirmed by positive Spot CVD -> enter on the reclaim. Stop from the arithmetic. Target = the next MEASURED level above, named; if none exists in this packet, write "no target".
*   **Rail A (BTC -> USDT):** a BEARISH or MACRO BEARISH sweep into a Major Resistance that overlaps an Upper Short tier, confirmed by flat/negative Spot CVD -> trim. Invalidation per the arithmetic. Target = the next MEASURED level below, named; if none exists in this packet, write "no target".

**Required Output Format (present the 3-VERDICT SUMMARY TABLE first, followed by Verdict 1 details 0-7 and Verdict 2/3 summaries):**
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
*   **Current Price:** $61,840 (1D SMA200 71,980)
*   **Tactical Bands:**
    *   Upper: $62,791 - $64,424 (Conf: 3/10, round-1k) [+$246M 50x Shorts]
    *   Lower: $59,069 - $60,434 (Conf: 3/10, round-1k) [+$369M 25x Longs]
    *   Price is inside $60,771 - $62,344 [+$123M 100x Longs]
*   **Macro S/R (Nearest 3):**
    *   Resistance: $62,338 (8x) [+$123M 100x Shorts], $63,065 (2x) [+$246M 50x Shorts], $64,584 (7x) [+$369M 25x Shorts]
    *   Support: $61,031 (2x) [+$123M 100x Longs], $60,000 (1x), $59,131 (1x)
*   **Volume Nodes (7D):** VAH: 60,656 | POC: 58,840 | VAL: 58,761 | Nearest HVN: $59,788 below
*   **Volume Profile (MTF):** 30D VAH 81,971 · POC 77,274 · VAL 61,840
    *   4H (last 30 bars): VAH 64,603 · POC 60,526 · VAL 59,978

## 2. THE FUEL (Liquidation Magnets) [ESTIMATED]
*   **OI weighting (assumed):** 10x 8% / 25x 6% / 50x 4% / 100x 2% of open interest (= 20% in total; the rest assumed cross-margin or lower leverage)
*   **Upper Shorts:** 10x $68,024 ($492.2M) / 25x $64,313 ($369.2M) / 50x $63,077 ($246.1M) / 100x $62,458 ($123.1M)
*   **Lower Longs:** 10x $55,656 ($492.2M) / 25x $59,366 ($369.2M) / 50x $60,603 ($246.1M) / 100x $61,221 ($123.1M)
    *Levels are exact leverage arithmetic. The $ per tier is OI $6,152.9M x the weights above, i.e. an assumed 20% of open interest across these four tiers (the rest assumed cross-margin or lower leverage) — not observed liquidation data. A tier is tagged as overlapping a level when it sits within 0.5% of it.*
*   **Long/Short account ratio (4H):** 2.45 [BIN]

## 3. THE TRUTH (Order Flow)
*   **Price Change (closed 1H [BIN]):** 1H: -0.11% | 4H: +0.64% | 24H: +1.91%
*   **CVD (Spot [BIN] / Perp [BIN]):** 1H: 40.4 / -653.0 | 4H: 222.8 / 39.5 | 24H: 507.2 / 3,459.5
*   **Open Interest:** 99,498 BTC [BIN] | 4H Change: 0.88% | 24H Change: 2.75%
*   **Funding:** 0.0055% per 8H [BIN] | 90-day percentile: 53
*   **ATR 1H:** 435 (Rail B stop distance = 1.5 x this = 652)

## 4. THE TRIGGER
*   **Sweep Status:** NONE (no closed 1H bar beyond a level that closed back inside)

## 5. MACRO VETO INPUTS
*   **ETF Net Flow:** 1D: $-453.0M (25 Nov 2026, settled) | 5D: $-2,505.6M
*   **Funding percentile:** 53 of 90 days
*   **Macro Weather (Veto Summary, never a trigger):** HEADWIND (Price -14.1% vs 200D SMA · 5D ETF -2,505.6M · Funding pctile 53)

## 6. PROJECT F — SLEEVE #1 (4H Rolling VWAP Shield · 80% Weight)
*   **Strategy:** `tier1_5_vwap_shield` (Spot BTC/USDT, zero leverage, 4H closed bars)
*   **Last Closed 4H Bar:** 2026-11-27 00:00Z -> 2026-11-27 04:00Z / 2026-11-27 12:00 SGT (999 closed 4H bars)
*   **Indicators:** Close $61,411.00 | 120D EMA Shield $73,205.19 | 15D Rolling VWAP (90b) $62,767.14 (12b Slope -1,264.00) | Band +/-0.50 ATR: $62,202.25 to $63,332.04 | 4H ATR(14) $1,129.79
*   **Checks:** [FAIL] Close > 120D EMA | [FAIL] Close > Upper Buffer | [FAIL] 12b VWAP Slope > 0 | [TRIGGERED] Exit Rule
*   **Readiness Radar:** 0/3 Buy Gates Passed | vs 120D EMA: -16.11% | vs Upper Buffer: -3.03% | Clear-Both Hurdle: $73,205.19 (+19.21% needed)
*   **Signal & Simulated State:** raw_signal = -1 | Sim Prior Pos = USDT -> Action: HOLD USDT | Reference 3.0x ATR Stop: $58,021.62
*   **Transition Memory:** Last Flip: SELL @ $82,820.00 on 2026-10-11 04:00Z (47.0d / 281 bars ago) | Window BTC Exposure: 35.9%
*   **Action by Actual Account State:** If currently FLAT (USDT): HOLD USDT (wait for BUY +1) | If currently LONG (BTC): SELL BTC at next bar open

## 7. PROJECT F — SLEEVE #2 (1D TTM Volatility Squeeze · 20% Weight)
*   **Strategy:** `tier14_ttm_squeeze_1d` (Spot BTC/USDT, zero leverage, NO 120D EMA shield, 1D closed bars)
*   **Last Closed 1D Bar:** 2026-11-26 00:00Z -> 2026-11-27 00:00Z / 2026-11-27 08:00 SGT (499 closed 1D bars)
*   **Indicators:** Close $60,577.18 | BB(20,2.0) $54,364.86 to $77,698.68 | KC(20,1.5) $61,214.08 to $69,697.07 (Mid $65,455.58) | Squeeze Now: OFF (Prior 3D: 0/3, Release: NO) | OLS Mom(20): -8,824.16 (Prev -9,427.30) | Exit SMA(21): $66,499.02 | 1D ATR(14): $2,967.85
*   **Checks:** [FAIL] Squeeze Release (after >=3d) | [FAIL] Mom > 0 | [PASS] Mom Rising | [FAIL] Close > KC Mid | [TRIGGERED] Exit (Close < SMA21 or Mom < 0)
*   **Readiness Radar:** 1/5 Buy Gates Passed | BB/KC Compression: 2.75x (WIDE >=1.00) | Active Squeeze Streak: 0d | vs KC Mid: -7.45% | vs SMA21: -8.91%
*   **Signal & Simulated State:** raw_signal = -1 | Sim Prior Pos = USDT -> Action: HOLD USDT | Reference 2.0x ATR Stop: $54,641.49
*   **Transition Memory:** Last Flip: SELL @ $78,306.43 on 2026-09-10 00:00Z (78.0d / 77 bars ago) | Window BTC Exposure: 20.0%
*   **Action by Actual Account State:** If currently FLAT (USDT): HOLD USDT (wait for BUY +1) | If currently LONG (BTC): SELL BTC at next bar open
*   **Portfolio Rule:** Segregated virtual ledgers (80% Sleeve #1 / 20% Sleeve #2, hard cap 15%-20% on #2); quarterly rebalance on Jan 1 / Apr 1 / Jul 1 / Oct 1 at 00:00 UTC if drift exceeds +/-3% ([77%, 83%]). Models 0.30% RT friction.

---
*Generated by salam_protocol.py — standard library only, closed bars only, no state. UNAVAILABLE is a valid answer; every estimated figure carries its label.*
