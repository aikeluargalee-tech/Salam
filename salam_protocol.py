#!/usr/bin/env python3
"""Salam Data Packet Protocol (SDPP) v1.0 — single file, standard library only.

Fetch -> compute -> write SALAM_DATA_HUB.md. No state, no database, no dependencies.

    python3 salam_protocol.py                 # writes ./SALAM_DATA_HUB.md
    python3 salam_protocol.py --out dir/      # writes elsewhere
    python3 salam_protocol.py --stdout        # print instead of write
    python3 salam_protocol.py --json          # also write SALAM_DATA_HUB.json
    python3 salam_protocol.py --check         # endpoint health only

Discipline:
  * closed bars only — a bar is used only when its close time is in the past
  * a failed endpoint prints UNAVAILABLE; it never falls back to stale data, zero or null
  * every estimated figure is labelled [MODELED] or [PROXY]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

SPOT = "https://data-api.binance.vision/api/v3"
FAPI = "https://fapi.binance.com"
OKX = "https://www.okx.com"
FARSIDE = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BAND_WIDTH_ATR = 0.35      # tactical band width, in 1D ATR
MACRO_LOOKBACK = 500       # 1D bars for macro S/R
MACRO_PIVOT_K = 2          # fractal width for macro pivots
MACRO_CLUSTER_PCT = 0.01   # 1% clustering width
LIQ_SHARE = 0.05           # [MODELED] assumed share of OI sitting in one leverage cluster


# ─────────────────────────────── transport ────────────────────────────────
def get_json(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def get_text(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def safe(fn, label: str):
    """Run a fetch, return (value, None) or (None, reason). Never raises."""
    try:
        return fn(), None
    except urllib.error.HTTPError as e:
        return None, f"{label} HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"{label} unreachable ({e.reason})"
    except (ValueError, KeyError, IndexError, TypeError) as e:
        return None, f"{label} parse error ({type(e).__name__})"
    except Exception as e:                                    # noqa: BLE001
        return None, f"{label} failed ({type(e).__name__})"


# ─────────────────────────────── indicators ───────────────────────────────
def closed(bars: list[dict], now_ms: float) -> list[dict]:
    return [b for b in bars if b["close_time"] < now_ms]


def to_bars(raw: list) -> list[dict]:
    out = []
    for r in raw:
        out.append({
            "open_time": int(r[0]), "o": float(r[1]), "h": float(r[2]), "l": float(r[3]),
            "c": float(r[4]), "v": float(r[5]), "close_time": int(r[6]),
            "taker_buy": float(r[9]),
        })
    return out


def atr_wilder(bars: list[dict], n: int = 14):
    if len(bars) < n + 2:
        return None
    trs = []
    for i in range(1, len(bars)):
        pc, b = bars[i - 1]["c"], bars[i]
        trs.append(max(b["h"] - b["l"], abs(b["h"] - pc), abs(b["l"] - pc)))
    a = sum(trs[:n]) / n
    for tr in trs[n:]:
        a = (a * (n - 1) + tr) / n
    return a


def sma(closes: list[float], n: int):
    return sum(closes[-n:]) / n if len(closes) >= n else None


def pivots(bars: list[dict], k: int) -> tuple[list[float], list[float]]:
    """k=2 means a swing high is higher than the 2 bars either side."""
    highs, lows = [], []
    for i in range(k, len(bars) - k):
        window = bars[i - k:i + k + 1]
        if bars[i]["h"] >= max(b["h"] for b in window) and bars[i]["h"] > bars[i - 1]["h"]:
            highs.append(bars[i]["h"])
        if bars[i]["l"] <= min(b["l"] for b in window) and bars[i]["l"] < bars[i - 1]["l"]:
            lows.append(bars[i]["l"])
    return highs, lows


def cluster(levels: list[float], pct: float) -> list[dict]:
    """Greedy 1%-width clustering; returns [{low, high, center, touches}] sorted asc."""
    out: list[dict] = []
    for px in sorted(levels):
        if out and abs(px - out[-1]["center"]) / out[-1]["center"] <= pct:
            c = out[-1]
            c["center"] = (c["center"] * c["touches"] + px) / (c["touches"] + 1)
            c["touches"] += 1
            c["low"], c["high"] = min(c["low"], px), max(c["high"], px)
        else:
            out.append({"low": px, "high": px, "center": px, "touches": 1})
    return out


def volume_profile(bars: list[dict], bins: int = 60, value_area: float = 0.70) -> dict | None:
    if len(bars) < 5:
        return None
    lo = min(b["l"] for b in bars)
    hi = max(b["h"] for b in bars)
    if hi <= lo:
        return None
    step = (hi - lo) / bins
    hist = [0.0] * bins
    for b in bars:
        idx = min(bins - 1, max(0, int(((b["h"] + b["l"] + b["c"]) / 3 - lo) / step)))
        hist[idx] += b["v"]
    total = sum(hist)
    if total <= 0:
        return None
    poc_i = max(range(bins), key=lambda i: hist[i])
    covered, span = hist[poc_i], [poc_i, poc_i]
    while covered < total * value_area and (span[0] > 0 or span[1] < bins - 1):
        left = hist[span[0] - 1] if span[0] > 0 else -1
        right = hist[span[1] + 1] if span[1] < bins - 1 else -1
        if right >= left:
            span[1] += 1
            covered += right
        else:
            span[0] -= 1
            covered += left
    return {"poc": lo + (poc_i + 0.5) * step,
            "val": lo + span[0] * step,
            "vah": lo + (span[1] + 1) * step}


def tactical_bands(h4: list[dict], atr1d: float, price: float) -> tuple[list[dict], dict | None]:
    highs, lows = pivots(h4, 2)
    width = BAND_WIDTH_ATR * atr1d
    raw = [{"low": p - width / 2, "high": p + width / 2, "touches": 1} for p in highs + lows]
    raw.sort(key=lambda b: b["low"])
    merged: list[dict] = []
    for b in raw:
        if merged:
            m = merged[-1]
            grown = max(m["high"], b["high"]) - min(m["low"], b["low"])
            if b["low"] <= m["high"] and grown <= 1.6 * width:
                m["high"] = max(m["high"], b["high"])
                m["low"] = min(m["low"], b["low"])
                m["touches"] += 1
                m["center"] = (m["low"] + m["high"]) / 2
                continue
        b["center"] = (b["low"] + b["high"]) / 2
        merged.append(b)
    inside = next((b for b in merged if b["low"] <= price <= b["high"]), None)
    return [b for b in merged if b is not inside], inside


def confluence(band: dict, vp: dict | None) -> tuple[int, list[str]]:
    """Max 10: +4 POC, +3 VAH or VAL, +3 round-1000 level."""
    score, why = 0, []
    if vp:
        if band["low"] <= vp["poc"] <= band["high"]:
            score += 4
            why.append("POC")
        if band["low"] <= vp["vah"] <= band["high"] or band["low"] <= vp["val"] <= band["high"]:
            score += 3
            why.append("VAH/VAL")
    round_levels = [math.ceil(band["low"] / 1000) * 1000, math.floor(band["high"] / 1000) * 1000]
    if any(band["low"] <= r <= band["high"] for r in set(round_levels)):
        score += 3
        why.append("round-1k")
    return score, why


def cvd(bars: list[dict], n_bars: int) -> float | None:
    if len(bars) < n_bars:
        return None
    return sum(2 * b["taker_buy"] - b["v"] for b in bars[-n_bars:])


def sweep(h1: list[dict], support: dict | None, resistance: dict | None) -> dict:
    """Last 6 closed 1H bars against the nearest band on each side."""
    recent = h1[-6:]
    for b in reversed(recent):
        if support and b["l"] < support["low"] and b["c"] > support["low"]:
            return {"flag": "BULLISH SWEEP", "level": support["low"],
                    "at": datetime.fromtimestamp(b["open_time"] / 1000, timezone.utc)
                            .strftime("%Y-%m-%d %H:%MZ")}
        if resistance and b["h"] > resistance["high"] and b["c"] < resistance["high"]:
            return {"flag": "BEARISH SWEEP", "level": resistance["high"],
                    "at": datetime.fromtimestamp(b["open_time"] / 1000, timezone.utc)
                            .strftime("%Y-%m-%d %H:%MZ")}
    return {"flag": "NONE", "level": None, "at": None}


def percentile(values: list[float], x: float) -> float | None:
    if not values:
        return None
    return 100.0 * sum(1 for v in values if v <= x) / len(values)


# ───────────────────────────────── ETF ────────────────────────────────────
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def _num(cell: str):
    """Farside numbers: 1,234.5 · (95.1) means -95.1 · '-' means not settled."""
    import re
    c = cell.replace("$", "").replace(",", "").replace("\u2212", "-").strip()
    neg = c.startswith("(") and c.endswith(")")
    c = c.strip("()").strip()
    if not re.fullmatch(r"-?\d+(\.\d+)?", c):
        return None
    v = float(c)
    return -v if neg else v


def etf_flows():
    """Farside table. A day counts only when its Total cell parses as a number.

    The newest row is often still filling even when its Total is present, so both the
    newest numeric day and the last completed day are reported.
    """
    import re
    html = get_text(FARSIDE)
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    cells_of = lambda tr: [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
                           for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]

    total_idx = None
    for tr in trs:
        cs = cells_of(tr)
        if "Total" in cs:
            total_idx = cs.index("Total")
            break
    if total_idx is None:
        raise ValueError("Total column not found")

    rows: list[tuple[tuple[int, int, int], float]] = []
    for tr in trs:
        cs = cells_of(tr)
        if len(cs) <= total_idx:
            continue
        m = re.fullmatch(r"(\d{1,2}) (\w{3}) (\d{4})", cs[0])
        if not m or m.group(2) not in MONTHS:
            continue
        val = _num(cs[total_idx])
        if val is None:
            continue                                    # dash / blank = not settled yet
        rows.append(((int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))), val))
    if not rows:
        raise ValueError("no settled rows parsed")
    rows.sort()
    today = datetime.now(timezone.utc).date()
    y, mo, d = rows[-1][0]
    newest_is_today = (y, mo, d) == (today.year, today.month, today.day)
    prev = rows[-1] if not newest_is_today else (rows[-2] if len(rows) > 1 else rows[-1])
    last5 = rows[-5:]
    return {
        "latest_date": f"{d} {[k for k, v in MONTHS.items() if v == mo][0]} {y}",
        "one_day_m": rows[-1][1],
        "one_day_settling": newest_is_today,
        "prev_date": f"{prev[0][2]} {[k for k, v in MONTHS.items() if v == prev[0][1]][0]} {prev[0][0]}",
        "prev_day_m": prev[1],
        "five_day_m": sum(v for _, v in last5),
        "five_day_days": len(last5),
        "twenty_day_m": sum(v for _, v in rows[-20:]) if len(rows) >= 20 else None,
    }


# ─────────────────────────────── collection ───────────────────────────────
def collect() -> tuple[dict, list[str]]:
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    jobs = {
        "d1": f"{SPOT}/klines?symbol=BTCUSDT&interval=1d&limit={MACRO_LOOKBACK}",
        "h4": f"{SPOT}/klines?symbol=BTCUSDT&interval=4h&limit=500",
        "h1": f"{SPOT}/klines?symbol=BTCUSDT&interval=1h&limit=200",
        "fd1": f"{FAPI}/fapi/v1/klines?symbol=BTCUSDT&interval=1d&limit=200",
        "fh1": f"{FAPI}/fapi/v1/klines?symbol=BTCUSDT&interval=1h&limit=200",
        "px": f"{SPOT}/ticker/price?symbol=BTCUSDT",
        "funding": f"{FAPI}/fapi/v1/premiumIndex?symbol=BTCUSDT",
        "funding_hist": f"{FAPI}/fapi/v1/fundingRate?symbol=BTCUSDT&limit=270",
        "oi": f"{FAPI}/fapi/v1/openInterest?symbol=BTCUSDT",
        "oi_hist": f"{FAPI}/futures/data/openInterestHist?symbol=BTCUSDT&period=4h&limit=7",
        "lsr": f"{FAPI}/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=4h&limit=1",
    }
    raw: dict = {}
    problems: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {k: pool.submit(safe, (lambda u=u: get_json(u)), k) for k, u in jobs.items()}
        futures["etf"] = pool.submit(safe, etf_flows, "etf")
        for k, f in futures.items():
            val, err = f.result()
            raw[k] = val
            if err:
                problems.append(err)

    # Measured from a US GitHub runner: fapi.binance.com = HTTP 451, api.bybit.com = HTTP 403,
    # api.deribit.com = unreachable; www.okx.com / bitget / gate.io / kraken / coingecko = 200.
    # OKX is the one venue that serves both a CI runner and a home machine, so it is the fallback.
    fb: dict = {}
    deriv_src = "BINANCE"
    if any(raw.get(k) is None for k in ("funding", "oi", "oi_hist", "lsr")):
        jobs2 = {
            "fund": f"{OKX}/api/v5/public/funding-rate?instId=BTC-USDT-SWAP",
            "oi": f"{OKX}/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP",
            "oi_hist": f"{OKX}/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=1H",
            "lsr": f"{OKX}/api/v5/rubik/stat/contracts/long-short-account-ratio-contract?instId=BTC-USDT-SWAP&period=4H",
            "fund_hist": f"{OKX}/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=100",
        }
        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = {k: pool.submit(safe, (lambda u=u: get_json(u)), f"okx:{k}") for k, u in jobs2.items()}
            for k, f in futs.items():
                val, err = f.result()
                fb[k] = val
                if err:
                    problems.append(err)
        if any(fb.get(k) for k in ("fund", "oi", "oi_hist", "lsr")):
            deriv_src = "OKX"

    def okx_data(key):
        return ((fb.get(key) or {}).get("data")) or []

    data = {"now": datetime.now(timezone.utc), "problems": problems, "deriv_src": deriv_src}
    for key in ("d1", "h4", "h1", "fd1", "fh1"):
        data[key] = closed(to_bars(raw[key]), now_ms) if raw.get(key) else []
    data["price"] = float(raw["px"]["price"]) if raw.get("px") else (
        data["d1"][-1]["c"] if data["d1"] else None)
    okx_fund = (okx_data("fund") or [{}])[0]
    if raw.get("funding"):
        data["funding"] = float(raw["funding"]["lastFundingRate"]) * 100
        data["mark"] = float(raw["funding"]["markPrice"])
    elif okx_fund.get("fundingRate") not in (None, ""):
        data["funding"] = float(okx_fund["fundingRate"]) * 100
        data["mark"] = None
    else:
        data["funding"] = data["mark"] = None

    okx_oi = (okx_data("oi") or [{}])[0]
    if raw.get("oi"):
        data["oi_btc"] = float(raw["oi"]["openInterest"])
    elif okx_oi.get("oiCcy") not in (None, ""):
        data["oi_btc"] = float(okx_oi["oiCcy"])
    else:
        data["oi_btc"] = None

    oi_series: list[float] = []
    oi_step_h = None
    if raw.get("oi_hist"):
        oi_series = [float(r["sumOpenInterest"]) for r in raw["oi_hist"]]
        oi_step_h = 4
    elif okx_data("oi_hist"):
        rows = okx_data("oi_hist")[:25]                  # hourly, newest first
        oi_series = [float(r[1]) for r in reversed(rows)]
        oi_step_h = 1

    def chg(series: list[float], step_h: int | None, hours: int):
        if not series or not step_h:
            return None
        back = hours // step_h
        if back < 1 or len(series) <= back:
            return None
        a, b = series[-1 - back], series[-1]
        return (b / a - 1) * 100 if a else None

    data["oi_4h_chg"] = chg(oi_series, oi_step_h, 4)
    data["oi_24h_chg"] = chg(oi_series, oi_step_h, 24)
    fh = [float(r["fundingRate"]) * 100 for r in (raw.get("funding_hist") or [])]
    if not fh:
        fh = [float(r["fundingRate"]) * 100 for r in okx_data("fund_hist")
              if r.get("fundingRate") not in (None, "")]
    data["funding_pct90"] = percentile(fh, data["funding"]) if (fh and data["funding"] is not None) else None
    lsr = raw.get("lsr") or []
    if lsr:
        data["ls_ratio"] = float(lsr[0]["longShortRatio"])
    else:
        blsr = okx_data("lsr")
        data["ls_ratio"] = float(blsr[0][1]) if blsr else None
    data["etf"] = raw.get("etf")
    if not data["fh1"]:
        problems.append("perp klines: Binance Futures unreachable here; Bybit/OKX klines carry no "
                        "taker split, so perp CVD needs a Binance-reachable host")
    return data, problems


# ──────────────────────────────── compute ─────────────────────────────────
def analyse(d: dict) -> dict:
    out: dict = {"problems": d["problems"]}
    price = d["price"]
    out["price"] = price
    if not d["d1"] or price is None:
        out["fatal"] = "no closed 1D bars or no price"
        return out

    closes = [b["c"] for b in d["d1"]]
    atr1d = atr_wilder(d["d1"], 14)
    out["atr1d"] = atr1d
    out["sma200"] = sma(closes, 200)
    out["vp30"] = volume_profile(d["d1"][-30:])

    highs, lows = pivots(d["d1"], MACRO_PIVOT_K)
    clusters = cluster(highs + lows, MACRO_CLUSTER_PCT)
    res = sorted([c for c in clusters if c["center"] > price], key=lambda c: -c["touches"])[:3]
    sup = sorted([c for c in clusters if c["center"] < price], key=lambda c: -c["touches"])[:3]
    out["macro_res"] = sorted(res, key=lambda c: c["center"])
    out["macro_sup"] = sorted(sup, key=lambda c: -c["center"])

    bands, inside = tactical_bands(d["h4"], atr1d, price) if (d["h4"] and atr1d) else ([], None)
    if inside:                      # never offer a "next" band that overlaps the one we are in
        below = [b for b in bands if b["high"] < inside["low"]]
        above = [b for b in bands if b["low"] > inside["high"]]
    else:
        below = [b for b in bands if b["high"] < price]
        above = [b for b in bands if b["low"] > price]
    sup_band = max(below, key=lambda b: b["high"]) if below else None
    res_band = min(above, key=lambda b: b["low"]) if above else None
    for b in (sup_band, res_band):
        if b:
            b["score"], b["why"] = confluence(b, out["vp30"])
    out["sup_band"], out["res_band"], out["inside_band"] = sup_band, res_band, inside
    out["bands"] = bands

    out["sweep"] = sweep(d["h1"], sup_band, res_band) if d["h1"] else {"flag": "UNAVAILABLE"}

    out["cvd_spot"] = {"1h": cvd(d["h1"], 1), "4h": cvd(d["h1"], 4), "24h": cvd(d["h1"], 24)}
    out["cvd_perp"] = {"1h": cvd(d["fh1"], 1), "4h": cvd(d["fh1"], 4), "24h": cvd(d["fh1"], 24)}
    out["oi_btc"], out["oi_4h_chg"], out["oi_24h_chg"] = d["oi_btc"], d["oi_4h_chg"], d["oi_24h_chg"]
    out["funding"], out["funding_pct90"], out["ls_ratio"] = d["funding"], d["funding_pct90"], d["ls_ratio"]
    out["etf"] = d["etf"]

    if d["oi_btc"] and price:
        oi_usd_m = d["oi_btc"] * price / 1e6
        pool = oi_usd_m * LIQ_SHARE
        out["oi_usd_m"] = oi_usd_m
        out["liq_upper"] = [{"lev": lev, "price": price * (1 + 1 / lev), "usd_m": pool}
                            for lev in (10, 25, 50, 100)]
        out["liq_lower"] = [{"lev": lev, "price": price * (1 - 1 / lev), "usd_m": pool}
                            for lev in (10, 25, 50, 100)]
    return out


# ───────────────────────────────── render ─────────────────────────────────
def f(x, dp=2, dash="UNAVAILABLE"):
    return dash if x is None else f"{x:,.{dp}f}"


def band_txt(b: dict | None) -> str:
    if not b:
        return "UNAVAILABLE"
    return f"{b['low']:,.0f}-{b['high']:,.0f}"


def render(a: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if a.get("fatal"):
        return f"# SALAM PROTOCOL DATA HUB v1.0\n**Timestamp:** {now} | **FATAL:** {a['fatal']}\n"
    p = a["price"]
    sb, rb = a.get("sup_band"), a.get("res_band")
    sw = a.get("sweep") or {}
    vp = a.get("vp30") or {}
    etf = a.get("etf") or {}
    up, lo = a.get("liq_upper") or [], a.get("liq_lower") or []

    L: list[str] = []
    L.append("# SALAM PROTOCOL DATA HUB v1.0")
    L.append(f"**Timestamp:** {now} | **Spot Price:** ${f(p)}")
    L.append("")

    L.append("## 1. THE ANCHOR (S/R & Volume)")
    inside = a.get("inside_band")
    L.append("*   **Tactical Bands:** Current: "
             + (f"inside {band_txt(inside)}" if inside else "between bands")
             + f" | Next Upper: {band_txt(rb)} (Conf: {rb['score'] if rb else 'UNAVAILABLE'})"
             + f" | Next Lower: {band_txt(sb)} (Conf: {sb['score'] if sb else 'UNAVAILABLE'})")
    mr = a.get("macro_res") or []
    ms = a.get("macro_sup") or []
    L.append("*   **Macro S/R (500-bar):** 1D Resistance: "
             + (", ".join(f"${c['center']:,.0f} ({c['touches']}x)" for c in mr) or "UNAVAILABLE")
             + " | 1D Support: "
             + (", ".join(f"${c['center']:,.0f} ({c['touches']}x)" for c in ms) or "UNAVAILABLE"))
    L.append(f"*   **Volume Profile (30D):** VAH: {f(vp.get('vah'), 0)} | POC: {f(vp.get('poc'), 0)}"
             f" | VAL: {f(vp.get('val'), 0)}")
    L.append(f"*   **200 SMA:** 1D: {f(a.get('sma200'), 0)}")
    L.append("")

    L.append("## 2. THE FUEL (Liquidation Magnets) [MODELED]")
    if up and lo:
        L.append("*   **Upper Shorts (10x/25x/50-100x):** "
                 + " / ".join(f"{c['lev']}x ${c['price']:,.0f} (${c['usd_m']:.1f}M)" for c in up))
        L.append("*   **Lower Longs (10x/25x/50-100x):** "
                 + " / ".join(f"{c['lev']}x ${c['price']:,.0f} (${c['usd_m']:.1f}M)" for c in lo))
        L.append(f"    *Levels are exact leverage arithmetic; the $M is OI ${a['oi_usd_m']:.1f}M "
                 f"x {LIQ_SHARE:.0%} assumed share per tier — not observed liquidation data.*")
    else:
        L.append("*   **Upper Shorts:** UNAVAILABLE (no open interest)")
        L.append("*   **Lower Longs:** UNAVAILABLE (no open interest)")
    if a.get("ls_ratio") is not None:
        L.append(f"*   **Long/Short account ratio (4H):** {a['ls_ratio']:.2f}")
    L.append("")

    L.append("## 3. THE TRUTH (Order Flow)")
    cs, cp = a.get("cvd_spot") or {}, a.get("cvd_perp") or {}
    L.append(f"*   **CVD (Spot/Perp):** 1H: {f(cs.get('1h'), 1)} / {f(cp.get('1h'), 1)}"
             f" | 4H: {f(cs.get('4h'), 1)} / {f(cp.get('4h'), 1)}"
             f" | 24H: {f(cs.get('24h'), 1)} / {f(cp.get('24h'), 1)}")
    L.append(f"*   **Open Interest:** {f(a.get('oi_btc'), 0)} BTC"
             f" | 4H Change: {f(a.get('oi_4h_chg'), 2)}% | 24H Change: {f(a.get('oi_24h_chg'), 2)}%")
    if a.get("deriv_src") == "OKX":
        L.append("*   **Derivatives source:** [OKX fallback] Binance Futures answers HTTP 451 and "
                 "Bybit HTTP 403 from this host. OI, funding and L/S are OKX's BTC-USDT swap; the "
                 "funding percentile uses OKX's last 100 readings (~33 days), not 90.")
    L.append(f"*   **Funding:** {f(a.get('funding'), 4)}% per 8H"
             f" | 90-day percentile: {f(a.get('funding_pct90'), 0)}")
    L.append("")

    L.append("## 4. THE TRIGGER")
    if sw.get("flag") == "NONE":
        L.append("*   **Sweep Status:** NONE (last 6 closed 1H bars stayed inside the bands)")
    elif sw.get("flag") == "UNAVAILABLE":
        L.append("*   **Sweep Status:** UNAVAILABLE (no 1H bars)")
    else:
        L.append(f"*   **Sweep Status:** {sw['flag']} at ${sw['level']:,.0f} ({sw['at']})")
    L.append("")

    L.append("## 5. MACRO VETO INPUTS")
    if etf:
        L.append(f"*   **ETF Net Flow:** 1D: ${etf['one_day_m']:,.1f}M ({etf['latest_date']}, settled)"
                 f" | 5D: ${etf['five_day_m']:,.1f}M")
    else:
        L.append("*   **ETF Net Flow:** UNAVAILABLE (Farside unreachable or no settled row)")
    L.append(f"*   **Funding percentile:** {f(a.get('funding_pct90'), 0)} of 90 days"
             + ("  <- tail" if (a.get("funding_pct90") or 0) >= 95 else ""))
    L.append("")

    if a["problems"]:
        L.append("## DATA NOTES")
        for pr in a["problems"]:
            L.append(f"*   {pr}")
        L.append("")

    L.append("### AI EXECUTION PROTOCOL: SALAM PROTOCOL v1.0")
    L.append("**Role:** Act as an elite Spot-Only Crypto Swing Trader using a Dual-Inventory "
             "(50/50 BTC/USDT) strategy.")
    L.append("**Primary Directive:** Analyze this data packet using S/R-First logic.")
    L.append("")
    L.append("**Core Methodology:**")
    L.append("1. **The Anchor (S/R):** Extract tactical bands, Confluence Scores, and Macro S/R.")
    L.append("2. **The Fuel (Liquidity):** Extract liquidation magnets. Overlap with S/R bands.")
    L.append("3. **The Trigger (Order Flow):** Confirm trades using Spot vs Perp CVD, OI, and the "
             "Sweep Detector.")
    L.append("")
    L.append("**Execution Rules:**")
    L.append("*   **Rail B (USDT -> BTC):** Wait for price to sweep a Lower Long Liquidation Cluster "
             "that overlaps with a Major Support Band. Confirm with a BULLISH SWEEP flag and positive "
             "Spot CVD. Enter on the reclaim.")
    L.append("*   **Rail A (BTC -> USDT):** Wait for price to rally into an Upper Short Liquidation "
             "Cluster that overlaps with a Major Resistance Band. Confirm with a BEARISH SWEEP flag and "
             "flat/negative Spot CVD. Trim BTC into USDT.")
    L.append("")
    L.append("**Required Output Format:**")
    L.append("1. **Current Market State**")
    L.append("2. **The Levels Map**")
    L.append("3. **Rail B (Buy) Plan** (Entry, Trigger, Stop Loss, Target)")
    L.append("4. **Rail A (Sell/Trim) Plan** (Entry, Trigger, Invalidation Stop, Target)")
    L.append("5. **Actionable Verdict** (What to do right now with the 50/50 portfolio).")
    L.append("")
    L.append("---")
    L.append("*Generated by salam_protocol.py — standard library only, closed bars only, no state. "
             "UNAVAILABLE is a valid answer; every estimated figure carries its label.*")
    return "\n".join(L) + "\n"


# ────────────────────────────────── main ──────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Salam Data Packet Protocol v1.0")
    ap.add_argument("--out", default=".", help="output directory (default: current)")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    ap.add_argument("--json", action="store_true", help="also write SALAM_DATA_HUB.json")
    ap.add_argument("--check", action="store_true", help="endpoint health only")
    args = ap.parse_args(argv)

    data, problems = collect()
    if args.check:
        rows = len(data["d1"])
        print(f"closed 1D bars: {rows} | 4H: {len(data['h4'])} | 1H: {len(data['h1'])} | "
              f"perp 1H: {len(data['fh1'])} | price: {data['price']}")
        print("ETF:", data["etf"] if data["etf"] else "UNAVAILABLE")
        for p in problems:
            print("  !", p)
        return 0 if not problems else 1

    a = analyse(data)
    md = render(a)
    if args.stdout:
        sys.stdout.write(md)
    else:
        import pathlib
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "SALAM_DATA_HUB.md"
        path.write_text(md, encoding="utf-8")
        print(f"wrote {path}  ({len(md):,} chars)")
        if args.json:
            jp = out / "SALAM_DATA_HUB.json"
            jp.write_text(json.dumps(a, indent=1, default=str), encoding="utf-8")
            print(f"wrote {jp}")
    for p in a.get("problems", []):
        print(f"  ! {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
