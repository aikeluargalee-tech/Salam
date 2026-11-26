#!/usr/bin/env python3
"""Salam Data Packet Protocol (SDPP) v1.6 — single file, standard library only.

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
from datetime import datetime, timedelta, timezone

SPOT = "https://data-api.binance.vision/api/v3"
FAPI = "https://fapi.binance.com"
OKX = "https://www.okx.com"
DUMP = "https://data.binance.vision/data/futures/um/daily/klines"   # official archive, not geo-blocked
FARSIDE = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BAND_WIDTH_ATR = 0.35      # tactical band width, in 1D ATR
MACRO_LOOKBACK = 500       # 1D bars for macro S/R
MACRO_PIVOT_K = 2          # fractal width for macro pivots
MACRO_CLUSTER_PCT = 0.01   # 1% clustering width
LIQ_WEIGHTS = ((10, 0.08), (25, 0.06), (50, 0.04), (100, 0.02))   # [MODELED] 20% of OI in total
LIQ_OVERLAY_PCT = 0.0025   # a liq cluster "overlaps" a level when within 0.25%
MANUAL_MAX_AGE_H = 2
LIQ_OVERLAY_MIN_LEV = 25   # low-leverage tiers are not explosive enough to tag
RISK_PCT = 0.0075          # binding arithmetic handed to the execution prompt
MAX_POS_PCT_OF_USDT = 0.30


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


def get_bytes(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def dump_bars(csv_lines: list[str]) -> list[dict]:
    """Parse a Binance kline CSV. The daily files ship a header row; older ones do not."""
    rows = [ln.split(",") for ln in csv_lines if ln.strip()]
    if rows and not rows[0][0].strip().lstrip("-").isdigit():
        rows = rows[1:]                       # drop the header
    if not rows or len(rows[0]) < 10:
        raise ValueError(f"unexpected column count {len(rows[0]) if rows else 0}")
    return [{"t": int(float(r[0])), "v": float(r[5]), "taker_buy": float(r[9])}
            for r in rows]


def okx_perp_cvd():
    """Live perp CVD from OKX's Rubik taker-volume endpoint — measured, not modelled.

    OKX klines carry no taker split, but rubik/stat/taker-volume-contract does:
    data rows are [ts, sellVolume, buyVolume] in coin units, newest first.
    """
    url = (f"{OKX}/api/v5/rubik/stat/taker-volume-contract"
           f"?instId=BTC-USDT-SWAP&period=1H&unit=0&limit=100")
    rows = (get_json(url) or {}).get("data") or []
    if len(rows) < 24:
        raise ValueError(f"only {len(rows)} taker-volume rows")
    bars = [{"v": float(r[1]) + float(r[2]), "taker_buy": float(r[2])}
            for r in reversed(rows)]                    # oldest -> newest
    return {"cvd_1h": cvd(bars, 1), "cvd_4h": cvd(bars, 4), "cvd_24h": cvd(bars, 24),
            "bars": len(bars)}


def dump_day_problem(bars: list[dict], day) -> str | None:
    """None if these bars are exactly one closed UTC day; otherwise the reason they are not.

    A row count is not a day: twenty-four copies of one hour, or twenty-four hours pulled from
    two different dates, both pass a `>= 24` test and would be published as a complete day.
    """
    if len(bars) != 24:
        return f"{len(bars)} rows, expected 24"
    stamps = [b.get("t") for b in bars]
    if any(t is None for t in stamps):
        return "rows carry no timestamp"
    if len(set(stamps)) != 24:
        return f"{len(set(stamps))} unique hours, expected 24"
    days = {datetime.fromtimestamp(t / 1000, timezone.utc).date() for t in stamps}
    if days != {day}:
        return f"rows span {sorted(str(x) for x in days)}, expected {day}"
    hours = sorted(datetime.fromtimestamp(t / 1000, timezone.utc).hour for t in stamps)
    if hours != list(range(24)):
        return f"hours {hours} are not 00–23"
    return None


def perp_cvd_from_dump(days_back: int = 3, fetch=None):
    """Perp CVD from Binance's public daily archive (no API, no geo-block, T+1 lag).

    The 1h files carry 12 columns; column 9 is takerBuyBaseVolume — the field the live
    futures API refuses a US runner. Returns a complete closed day, never "now".
    """
    import io
    import zipfile
    from datetime import timedelta

    fetch = fetch or get_bytes
    today = datetime.now(timezone.utc).date()
    last_err = "no published daily dump in the last %d days" % days_back
    for back in range(1, days_back + 1):
        d = today - timedelta(days=back)
        url = f"{DUMP}/BTCUSDT/1h/BTCUSDT-1h-{d.isoformat()}.zip"
        try:
            blob = fetch(url)
            z = zipfile.ZipFile(io.BytesIO(blob))
            bars = dump_bars(z.read(z.namelist()[0]).decode().strip().splitlines())
            if len(bars) < 24:
                last_err = f"dump {d} only {len(bars)} bars"
                continue
            why = dump_day_problem(bars, d)
            if why:
                last_err = f"dump {d} unusable: {why}"
                continue
            return ({"date": d.isoformat(), "bars": len(bars),
                     "cvd_4h": cvd(bars, 4), "cvd_24h": cvd(bars, 24)}, None)
        except urllib.error.HTTPError as e:
            if e.code == 404:                      # not published yet -> try the day before
                last_err = f"dump {d} 404 (not published)"
                continue
            return None, f"dump {d} HTTP {e.code}"
        except Exception as e:                     # noqa: BLE001
            return None, f"dump {d} {type(e).__name__}"
    return None, last_err


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
    centers = [lo + (i + 0.5) * step for i in range(bins)]
    return {"poc": lo + (poc_i + 0.5) * step,
            "val": lo + span[0] * step,
            "vah": lo + (span[1] + 1) * step,
            "hist": hist, "centers": centers, "peak": max(hist), "bars": len(bars)}


def hvn_nearest(vp: dict | None, price: float, share: float = 0.60):
    """Nearest high-volume node: a bin holding >= share of the POC's volume."""
    if not vp or not vp.get("peak"):
        return None
    hits = [c for c, h in zip(vp["centers"], vp["hist"]) if h >= share * vp["peak"]]
    above = [c for c in hits if c > price]
    below = [c for c in hits if c < price]
    return {"above": min(above) if above else None,
            "below": max(below) if below else None}


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
    """Max 10: +4 POC, +3 VAH or VAL, +3 round-1000 level. vp must be the 7D profile."""
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


def sweep(h1: list[dict], support: dict | None, resistance: dict | None,
          macro_sup: list | None = None, macro_res: list | None = None) -> dict:
    """Last 6 closed 1H bars, newest first: macro levels are checked before tactical bands."""
    def stamp(b):
        return datetime.fromtimestamp(b["open_time"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%MZ")

    for b in reversed(h1[-6:]):
        for c in (macro_sup or []):                       # macro support swept and reclaimed
            if c["touches"] < 2:
                continue
            lv = c["center"]
            if b["l"] < lv and b["c"] > lv:
                return {"flag": "MACRO BULLISH SWEEP", "level": lv, "at": stamp(b),
                        "touches": c["touches"]}
        for c in (macro_res or []):
            if c["touches"] < 2:
                continue
            lv = c["center"]
            if b["h"] > lv and b["c"] < lv:
                return {"flag": "MACRO BEARISH SWEEP", "level": lv, "at": stamp(b),
                        "touches": c["touches"]}
        if support and b["l"] < support["low"] and b["c"] > support["low"]:
            return {"flag": "BULLISH SWEEP", "level": support["low"], "at": stamp(b)}
        if resistance and b["h"] > resistance["high"] and b["c"] < resistance["high"]:
            return {"flag": "BEARISH SWEEP", "level": resistance["high"], "at": stamp(b)}
    return {"flag": "NONE", "level": None, "at": None}


def parse_manual(s: str | None) -> tuple[dict, bool]:
    """A manual reading unlocks execution ONLY if it carries a number and a UTC time.

    "perp_cvd_24h=+2663,at=04:05Z" unlocks. "perp_cvd=falling" does not — an adjective is not
    evidence, and a gate that any sentence can open is not a gate.
    """
    parts: dict[str, str] = {}
    for chunk in (s or "").split(","):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip()] = v.strip()
    ok = False
    try:
        float(parts.get("perp_cvd_24h", ""))
        at_raw = (parts.get("at") or "").strip().upper()
        if at_raw.endswith("Z"):
            when = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%H:%M"):
                try:
                    when = datetime.strptime(at_raw[:-1].strip(), fmt)
                    break
                except ValueError:
                    continue
            if when is not None:
                now = datetime.now(timezone.utc)
                if when.year == 1900:                      # time-only: anchor to today
                    when = when.replace(year=now.year, month=now.month, day=now.day)
                when = when.replace(tzinfo=timezone.utc)
                if when > now + timedelta(minutes=5):      # 23:50Z typed just after midnight
                    when -= timedelta(days=1)
                ok = (now - when) <= timedelta(hours=MANUAL_MAX_AGE_H)
    except (TypeError, ValueError):
        ok = False
    return parts, ok


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
    if raw.get("px"):
        data["price"] = float(raw["px"]["price"])
        data["price_src"] = "TICKER"
    elif data["d1"]:
        data["price"] = data["d1"][-1]["c"]
        data["price_src"] = "CLOSE-1D"          # last closed daily candle, not a live quote
    else:
        data["price"] = None
        data["price_src"] = None
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
    oi_stamps: list[int] = []
    if raw.get("oi_hist"):
        oi_series = [float(r["sumOpenInterest"]) for r in raw["oi_hist"]]
        oi_stamps = [int(r["timestamp"]) for r in raw["oi_hist"]]
    elif okx_data("oi_hist"):
        rows = list(reversed(okx_data("oi_hist")[:25]))   # hourly, newest first -> oldest first
        oi_series = [float(r[1]) for r in rows]
        oi_stamps = [int(r[0]) for r in rows]

    data["oi_4h_chg"] = oi_change(oi_series, oi_stamps, 4)
    data["oi_24h_chg"] = oi_change(oi_series, oi_stamps, 24)
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
    data["perp_dump"] = None
    data["perp_src"] = "BINANCE" if data["fh1"] else None
    if not data["fh1"]:
        try:
            data["okx_perp"] = okx_perp_cvd()
            data["perp_src"] = "OKX-RUBIK"
            problems.append("perp CVD is OKX's measured taker volume (BTC-USDT swap), "
                            "not Binance — Binance Futures refused this host")
        except Exception as e:                          # noqa: BLE001
            data["okx_perp"] = None
            problems.append(f"okx taker-volume unavailable ({type(e).__name__})")
    if not data["fh1"] and not data.get("okx_perp"):
        dump, derr = perp_cvd_from_dump()
        data["perp_dump"] = dump
        if dump:
            data["perp_src"] = "ARCHIVE"
        if dump:
            problems.append(f"perp CVD is from Binance's daily archive for {dump['date']} "
                            f"(T+1, {dump['bars']} bars) — not live")
        else:
            problems.append(f"perp klines unavailable ({derr}); no taker split from OKX/Bybit")
    return data, problems


# ──────────────────────────────── compute ─────────────────────────────────
def oi_change(series: list[float], stamps: list[int], hours: int) -> float | None:
    """Percent change over `hours`, matched by timestamp rather than by position.

    A positional offset assumes the samples are contiguous: one missing hour silently shifts
    the window and reports a different interval as "4H". If no sample sits within 30 minutes of
    the requested horizon, the change is unavailable rather than approximate.
    """
    if not series or not stamps or len(series) != len(stamps):
        return None
    target = stamps[-1] - hours * 3600_000
    idx = min(range(len(stamps) - 1), key=lambda i: abs(stamps[i] - target))
    if abs(stamps[idx] - target) > 1800_000:
        return None
    a, b = series[idx], series[-1]
    return (b / a - 1) * 100 if a else None


def analyse(d: dict) -> dict:
    out: dict = {"problems": d["problems"], "deriv_src": d.get("deriv_src", "BINANCE"),
                 "price_src": d.get("price_src")}
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
    out["vp7"] = volume_profile(d["d1"][-7:])
    out["vp4h"] = volume_profile(d["h4"][-30:]) if len(d["h4"]) >= 30 else None
    out["hvn7"] = hvn_nearest(out["vp7"], price)
    out["atr1h"] = atr_wilder(d["h1"], 14) if len(d["h1"]) > 16 else None

    highs, lows = pivots(d["d1"], MACRO_PIVOT_K)
    clusters = cluster(highs + lows, MACRO_CLUSTER_PCT)
    # nearest 3 by distance — touch count is kept as context but no longer ranks the list
    noise = price * 0.0025          # a cluster this close is "at price", not a level to trade
    out["macro_res"] = sorted([c for c in clusters if c["center"] > price + noise],
                              key=lambda c: c["center"])[:3]
    out["macro_sup"] = sorted([c for c in clusters if c["center"] < price - noise],
                              key=lambda c: -c["center"])[:3]

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
            b["score"], b["why"] = confluence(b, out["vp7"])
    out["sup_band"], out["res_band"], out["inside_band"] = sup_band, res_band, inside
    out["bands"] = bands

    out["sweep"] = sweep(d["h1"], sup_band, res_band, out["macro_sup"], out["macro_res"]) \
        if d["h1"] else {"flag": "UNAVAILABLE"}

    out["cvd_spot"] = {"1h": cvd(d["h1"], 1), "4h": cvd(d["h1"], 4), "24h": cvd(d["h1"], 24)}
    out["cvd_perp"] = {"1h": cvd(d["fh1"], 1), "4h": cvd(d["fh1"], 4), "24h": cvd(d["fh1"], 24)}
    if d.get("okx_perp"):
        op = d["okx_perp"]
        out["cvd_perp"] = {"1h": op["cvd_1h"], "4h": op["cvd_4h"], "24h": op["cvd_24h"]}
    out["perp_src"] = d.get("perp_src")
    out["perp_cvd_ok"] = all(v is not None for v in out["cvd_perp"].values())
    out["perp_dump"] = d.get("perp_dump")
    out["oi_btc"], out["oi_4h_chg"], out["oi_24h_chg"] = d["oi_btc"], d["oi_4h_chg"], d["oi_24h_chg"]
    out["funding"], out["funding_pct90"], out["ls_ratio"] = d["funding"], d["funding_pct90"], d["ls_ratio"]
    out["etf"] = d["etf"]

    if d.get("liq_upper") is not None:
        pass

    if d["oi_btc"] and price:
        oi_usd_m = d["oi_btc"] * price / 1e6
        out["oi_usd_m"] = oi_usd_m
        out["liq_upper"] = [{"lev": lev, "price": price * (1 + 1 / lev), "usd_m": oi_usd_m * w}
                            for lev, w in LIQ_WEIGHTS]
        out["liq_lower"] = [{"lev": lev, "price": price * (1 - 1 / lev), "usd_m": oi_usd_m * w}
                            for lev, w in LIQ_WEIGHTS]
    # ── layer 4: liquidation overlay on every level we publish ──
    def overlay(target: float):
        """One tag at most: the single nearest cluster, and only if it is 25x or higher."""
        if not target:
            return None
        cands = [("Shorts", c) for c in out.get("liq_upper") or []] + \
                [("Longs", c) for c in out.get("liq_lower") or []]
        if not cands:
            return None
        side, c = min(cands, key=lambda sc: abs(sc[1]["price"] - target))
        if abs(c["price"] - target) / target > LIQ_OVERLAY_PCT:
            return None
        if c["lev"] < LIQ_OVERLAY_MIN_LEV:
            return None
        return (side, c["usd_m"], c["lev"])

    for b in (out.get("sup_band"), out.get("res_band")):
        if b:
            b["liq"] = overlay(b["center"])
    for c in out.get("macro_res", []) + out.get("macro_sup", []):
        c["liq"] = overlay(c["center"])
    return out


# ───────────────────────────────── render ─────────────────────────────────
def f(x, dp=2, dash="UNAVAILABLE"):
    return dash if x is None else f"{x:,.{dp}f}"


def band_txt(b: dict | None) -> str:
    if not b:
        return "UNAVAILABLE"
    return f"{b['low']:,.0f}-{b['high']:,.0f}"


def fmt_dual(ts: str | None) -> str:
    """Render a 'YYYY-MM-DD HH:MMZ' stamp as UTC and SGT (UTC+8)."""
    if not ts:
        return ""
    try:
        d = datetime.strptime(str(ts), "%Y-%m-%d %H:%MZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return str(ts)
    return f"{ts} / {(d + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')} SGT"


def tag(a: dict) -> str:
    return "[OKX]" if a.get("deriv_src") == "OKX" else "[BIN]"


def liq_txt(x) -> str:
    if not x:
        return ""
    side, usd, lev = x
    return f" [+${usd:,.0f}M {lev}x {side}]"


def vp_txt(vp: dict | None, style: str) -> str:
    if not vp:
        return "UNAVAILABLE"
    if style == "full":
        return f"VAH {vp['vah']:,.0f} · POC {vp['poc']:,.0f} · VAL {vp['val']:,.0f}"
    return f"VAH: {vp['vah']:,.0f} | POC: {vp['poc']:,.0f} | VAL: {vp['val']:,.0f}"


def render(a: dict) -> str:
    stamp = a.get("generated_at_utc")
    if stamp:
        _n = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    else:
        _n = datetime.now(timezone.utc)
    now = (_n.strftime("%Y-%m-%d %H:%M:%S UTC")
           + " / " + (_n + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S SGT (UTC+8)"))
    if a.get("fatal"):
        return f"# SALAM PROTOCOL DATA HUB v1.6\n**Timestamp:** {now} | **FATAL:** {a['fatal']}\n"
    p = a["price"]
    sb, rb = a.get("sup_band"), a.get("res_band")
    inside = a.get("inside_band")
    sw = a.get("sweep") or {}
    etf = a.get("etf") or {}
    up, lo = a.get("liq_upper") or [], a.get("liq_lower") or []
    hvn = a.get("hvn7") or {}
    V = tag(a)
    PV = ("[OKX-RUBIK]" if a.get("perp_src") == "OKX-RUBIK" else "[BIN]")

    L: list[str] = []
    L.append("# SALAM PROTOCOL DATA HUB v1.6")
    PT = "[BIN-CLOSE 1D]" if a.get("price_src") == "CLOSE-1D" else "[BIN]"
    L.append(f"**Timestamp:** {now} | **Spot Price:** ${p:,.2f} {PT}")
    dump = a.get("perp_dump")
    state = a.get("exec_state", "FULL")
    if state == "FULL" and a.get("perp_src") == "OKX-RUBIK":
        L.append("> ✅ **FULL ORDER FLOW — perp CVD is OKX's measured taker volume, spot is Binance.** "
                 "Live, not modelled: Binance Futures refuses this host, but OKX's rubik endpoint "
                 "publishes real taker buy/sell per hour.")
    elif state == "FULL":
        L.append("> ✅ **FULL ORDER FLOW: Binance spot + perp. Execution-grade.**")
    elif state == "MANUAL":
        L.append(f"> ✅ **FULL ORDER FLOW — PERP CVD IS MANUAL @ {a.get('manual_at')}.** "
                 f"Human-supplied from a screenshot, not machine-verified. "
                 f"Perp CVD 24H = {a['manual'].get('perp_cvd_24h')} BTC.")
    elif dump:
        L.append(f"> ⚠️ **PARTIAL ORDER FLOW — perp CVD is Binance's archive for {dump['date']} "
                 f"(T+1), not live.** Live perp klines are blocked on this host. Intraday perp "
                 f"reads are one day old; spot and levels are live.")
    else:
        why = ("CI host: Binance Futures refused this runner (HTTP 451)"
               if a.get("deriv_src") == "OKX" else
               "this run produced no usable perp klines")
        L.append(f"> ⚠️ **PERP CVD UNAVAILABLE — {why}.** This packet is a levels map, "
                 f"not an execution packet. Run locally before acting.")
    L.append("")

    # ── 1. Deep S/R matrix ──
    L.append("## 1. THE ANCHOR (Deep S/R Matrix)")
    L.append(f"*   **Current Price:** ${p:,.0f} (1D SMA200 {f(a.get('sma200'), 0)})")
    L.append("*   **Tactical Bands:**")
    if rb:
        L.append(f"    *   Upper: ${rb['low']:,.0f} - ${rb['high']:,.0f} "
                 f"(Conf: {rb.get('score', 0)}/10){liq_txt(rb.get('liq'))}")
    else:
        L.append("    *   Upper: UNAVAILABLE")
    if sb:
        L.append(f"    *   Lower: ${sb['low']:,.0f} - ${sb['high']:,.0f} "
                 f"(Conf: {sb.get('score', 0)}/10){liq_txt(sb.get('liq'))}")
    else:
        L.append("    *   Lower: UNAVAILABLE")
    if inside:
        L.append(f"    *   Price is inside ${inside['low']:,.0f} - ${inside['high']:,.0f}"
                 f"{liq_txt(inside.get('liq'))}")

    L.append("*   **Macro S/R (Nearest 3):**")
    mr, ms = a.get("macro_res") or [], a.get("macro_sup") or []
    L.append("    *   Resistance: " + (", ".join(
        f"${c['center']:,.0f} ({c['touches']}x){liq_txt(c.get('liq'))}" for c in mr) or "UNAVAILABLE"))
    L.append("    *   Support: " + (", ".join(
        f"${c['center']:,.0f} ({c['touches']}x){liq_txt(c.get('liq'))}" for c in ms) or "UNAVAILABLE"))

    hvn_bit = "UNAVAILABLE"
    if hvn.get("above") or hvn.get("below"):
        parts = []
        if hvn.get("below"):
            parts.append(f"${hvn['below']:,.0f} below")
        if hvn.get("above"):
            parts.append(f"${hvn['above']:,.0f} above")
        hvn_bit = " · ".join(parts)
    L.append(f"*   **Volume Nodes (7D):** {vp_txt(a.get('vp7'), 'inline')} | Nearest HVN: {hvn_bit}")
    L.append(f"*   **Volume Profile (MTF):** 30D {vp_txt(a.get('vp30'), 'full')}")
    L.append(f"    *   4H (last 30 bars): {vp_txt(a.get('vp4h'), 'full')}")
    L.append("")

    # ── 2. Liq magnets, weighted tiers ──
    L.append("## 2. THE FUEL (Liquidation Magnets) [MODELED]")
    if up and lo:
        wdesc = " / ".join(f"{lev}x {w:.0%}" for lev, w in LIQ_WEIGHTS)
        total_w = sum(w for _, w in LIQ_WEIGHTS)
        L.append(f"*   **OI weighting (assumed):** {wdesc} of open interest "
                 f"(= {total_w:.0%} in total; the rest assumed cross-margin or lower leverage)")
        L.append("*   **Upper Shorts:** " + " / ".join(
            f"{c['lev']}x ${c['price']:,.0f} (${c['usd_m']:,.1f}M)" for c in up))
        L.append("*   **Lower Longs:** " + " / ".join(
            f"{c['lev']}x ${c['price']:,.0f} (${c['usd_m']:,.1f}M)" for c in lo))
        L.append(f"    *Levels are exact leverage arithmetic. The $ per tier is OI "
                 f"${a['oi_usd_m']:,.1f}M x the weights above, i.e. an assumed "
                 f"{sum(w for _, w in LIQ_WEIGHTS):.0%} of open interest across these four tiers "
                 f"(the rest assumed cross-margin or lower leverage) — not observed liquidation data.*")
    else:
        L.append("*   **Upper Shorts:** UNAVAILABLE (no open interest)")
        L.append("*   **Lower Longs:** UNAVAILABLE (no open interest)")
    if a.get("ls_ratio") is not None:
        L.append(f"*   **Long/Short account ratio (4H):** {a['ls_ratio']:.2f} {V}")
    L.append("")

    # ── 3. Order flow ──
    L.append("## 3. THE TRUTH (Order Flow)")
    cs, cp = a.get("cvd_spot") or {}, a.get("cvd_perp") or {}
    L.append(f"*   **CVD (Spot [BIN] / Perp {PV}):** "
             f"1H: {f(cs.get('1h'), 1)} / {f(cp.get('1h'), 1)}"
             f" | 4H: {f(cs.get('4h'), 1)} / {f(cp.get('4h'), 1)}"
             f" | 24H: {f(cs.get('24h'), 1)} / {f(cp.get('24h'), 1)}")
    L.append(f"*   **Open Interest:** {f(a.get('oi_btc'), 0)} BTC {V}"
             f" | 4H Change: {f(a.get('oi_4h_chg'), 2)}% | 24H Change: {f(a.get('oi_24h_chg'), 2)}%")
    if a.get("deriv_src") == "OKX":
        L.append("*   **Derivatives source:** [OKX fallback] Binance Futures answers HTTP 451 and "
                 "Bybit HTTP 403 from this host. OI, funding and L/S are OKX's BTC-USDT swap; the "
                 "funding percentile uses its last 100 readings (~33 days), not 90.")
    L.append(f"*   **Funding:** {f(a.get('funding'), 4)}% per 8H {V}"
             + (f" | percentile (100 pts): {f(a.get('funding_pct90'), 0)}"
                if a.get("deriv_src") == "OKX"
                else f" | 90-day percentile: {f(a.get('funding_pct90'), 0)}"))
    if dump and not a.get("perp_cvd_ok"):
        L.append(f"*   **Perp CVD [BIN-DUMP {dump['date']}]:** 4H {f(dump.get('cvd_4h'), 1)}"
                 f" | 24H {f(dump.get('cvd_24h'), 1)} (complete closed day, {dump['bars']} bars"
                 f" — one day old, not live)")
    if a.get("manual"):
        man = a["manual"]
        L.append(f"*   **Manual override [MANUAL {man.get('at', '?')}]:** "
                 + ", ".join(f"{k}={v}" for k, v in man.items() if k != "at")
                 + ("" if a.get("manual_ok") else
                    "  (no numeric perp CVD + timestamp — does NOT unlock execution)"))
    _atr = a.get("atr1h")
    _stop = f"1.5 x this = {f(_atr * 1.5, 0)})" if _atr is not None else "UNAVAILABLE)"
    L.append(f"*   **ATR 1H:** {f(_atr, 0)} (Rail B stop distance = {_stop}")
    L.append("")

    # ── 4. Trigger ──
    L.append("## 4. THE TRIGGER")
    if sw.get("flag") == "NONE":
        L.append("*   **Sweep Status:** NONE (no closed 1H bar beyond a level that closed back inside)")
    elif sw.get("flag") == "UNAVAILABLE":
        L.append("*   **Sweep Status:** UNAVAILABLE (no 1H bars)")
    else:
        extra = f" ({sw['touches']}x level)" if sw.get("touches") else ""
        L.append(f"*   **Sweep Status:** {sw.get('flag', 'UNAVAILABLE')} at "
                 f"${(sw.get('level') or 0):,.0f}{extra} · {fmt_dual(sw.get('at'))}")
    L.append("")

    # ── 5. Macro veto ──
    L.append("## 5. MACRO VETO INPUTS")
    if etf:
        _settled = "settling" if etf.get("one_day_settling") else "settled"
        L.append(f"*   **ETF Net Flow:** 1D: ${etf['one_day_m']:,.1f}M "
                 f"({etf['latest_date']}, {_settled})"
                 f" | 5D: ${etf['five_day_m']:,.1f}M")
    else:
        L.append("*   **ETF Net Flow:** UNAVAILABLE (Farside unreachable or no settled row)")
    okx_src = a.get("deriv_src") == "OKX"
    L.append(f"*   **Funding percentile:** {f(a.get('funding_pct90'), 0)}"
             + (" of the last 100 readings (~33 days, OKX)" if okx_src else " of 90 days")
             + ("  <- tail" if ((a.get("funding_pct90") or 0) >= 95 and not okx_src) else ""))
    L.append("")

    if a["problems"]:
        L.append("## DATA NOTES")
        for pr in a["problems"]:
            L.append(f"*   {pr}")
        L.append("")

    L.append("### AI EXECUTION PROTOCOL: SALAM ANALYST v1.7")
    L.append("**Role:** elite spot-only BTC swing trader, Dual-Inventory (50/50 BTC/USDT), zero "
             "leverage. You do not decide anything: you describe what this packet's rules permit.")
    L.append("**Primary Directive:** use only numbers present in this packet. No external data, no "
             "recall, no forecasting. A missing number is UNAVAILABLE, never zero.")
    L.append("")
    L.append("**THE FOUR PILLARS — the only drivers. Nothing else may start a trade.**")
    L.append("1. **Structure A — S/R:** tactical bands with confluence scores, macro S/R with touches.")
    L.append("2. **Structure B — Volume Profile:** 7D, 30D AND 4H value areas (VAH/POC/VAL) + nearest HVN.")
    L.append("3. **Fuel — Liquidation tiers:** leverage-derived clusters, reported only where they "
             "overlap measured structure.")
    L.append("4. **Trigger — Order Flow:** spot vs perp CVD across 1H/4H/24H, plus open-interest change.")
    L.append("")
    L.append("*Veto inputs (can block a trade, never start one): 200D average, ETF flows with trade "
             "date, funding percentile, long/short ratio.*")
    L.append("")
    L.append("**Structure tests (highest weight)**")
    L.append("*   *Value-area test:* inside 7D value = balance; below 30D VAL = discount and that "
             "level is the return-to-value line; above VAH = premium. Say which applies.")
    L.append("*   *POC test:* price within 0.25% of any POC means the market is balanced on the "
             "defended price. That explains quiet tape; it is not a signal.")
    L.append("*   *Band quality:* an edge sitting beyond the nearest measured volume node is weaker "
             "than its score. On a low score, name what carried it and what is missing.")
    L.append("*   *Chop rule:* inside the mid band and more than 1% from BOTH band edges = NO TRADE "
             "regardless of CVD. Quote the two distances.")
    L.append("*   *Density test:* compare measured levels above with measured levels below. Thin path "
             "= fast travel; dense path = grind.")
    L.append("")
    L.append("**Fuel tests**")
    L.append("*   Tiers are leverage arithmetic (100x dies 1% from entry, 50x 2%, 25x 4%, 10x 10%) and "
             "they RE-CENTRE with price. Never quote a tier as a fixed target.")
    L.append("*   Report a tier only when it overlaps a measured structure (volume node, >=2 touches, "
             "band edge, macro S/R) within 0.5%. List the overlaps; ignore the rest.")
    L.append("*   Convert to coins: notional / price = BTC of forced orders, and as % of open interest.")
    L.append("*   Fuel is symmetric by assumption: say so, and never infer direction from it. Only "
             "the terrain around it is asymmetric. Name the exhaust point.")
    L.append("")
    L.append("**Trigger tests (confirmation only, only at an anchor)**")
    L.append("*   Read spot vs perp CVD in 1H, 4H and 24H. Compute perp:spot 24H ratio; above 3x means "
             "futures-led, i.e. positioning rather than accumulation.")
    L.append("*   OI rising while price is flat and spot CVD is negative = distribution. Say it.")
    L.append("*   No sweep flag = that rail is NOT armed, whatever the band score. Give its level, "
             "direction and time.")
    L.append("*   If the gate is PARTIAL or NONE, plans are withheld — do not invent levels. An "
             "unknown state reads as NONE.")
    L.append("")
    L.append("**Binding Arithmetic (not optional, never adjusted)**")
    L.append(f"*   **Rail B stop loss = Entry - (1.5 x ATR 1H).** ATR 1H is printed in section 3; "
             f"print the ATR and the dollar stop, do not invent one.")
    L.append(f"*   **Risk per trade = {RISK_PCT:.2%} of total portfolio value.** Position size = "
             f"(portfolio x {RISK_PCT:.2%}) / (entry - stop).")
    L.append(f"*   **If that size exceeds {MAX_POS_PCT_OF_USDT:.0%} of the USDT inventory, SKIP** — and "
             f"report the conflict: \"risk budget asks X BTC, the cap allows Y BTC, so this rail is "
             f"vetoed.\" Do not silently resize; do not drop the rule.")
    L.append("*   **Rail A invalidation = a DAILY close above (band high + 1 x ATR 1H).** Print the "
             "number. A 1H close is noise, not invalidation.")
    L.append("")
    if state in ("PARTIAL", "NONE"):
        L.append("## ❌ EXECUTION SUSPENDED")
        L.append(f"*   **State: {state}.** Perp CVD is "
                 + ("the archive figure for " + dump["date"] + " (T+1)" if dump else "unavailable")
                 + ". Rail A and Rail B plans are withheld by design — a lagged or missing flow "
                   "figure is not a basis for an order, and a model reading one beside a plan will "
                   "use it as if it were live.")
        L.append("*   **To lift the gate, either:** run this script on a Binance-reachable host "
                 "(full live perp), or record a screenshot reading with a number and a UTC time:")
        L.append('    *   `python3 salam_protocol.py --manual "perp_cvd_24h=+2663,at=04:05Z"`')
        L.append("*   An adjective does not unlock it. `perp_cvd=falling` will print under [MANUAL] "
                 "and leave execution suspended.")
    else:
        L.append("**Execution Rules:**")
        L.append("*   **Rail B (USDT -> BTC):** a BULLISH or MACRO BULLISH sweep into a Major Support "
                 "that overlaps a Lower Long tier, confirmed by positive Spot CVD -> enter on the "
                 "reclaim. Stop from the arithmetic. Target = the next MEASURED level above, named; "
                 "if none exists in this packet, write \"no target\".")
        L.append("*   **Rail A (BTC -> USDT):** a BEARISH or MACRO BEARISH sweep into a Major Resistance "
                 "that overlaps an Upper Short tier, confirmed by flat/negative Spot CVD -> trim. "
                 "Invalidation per the arithmetic. Target = the next MEASURED level below, named.")
        L.append("")
        L.append("**Required Output Format (this exact order):**")
        L.append("0. **BOTTOM LINE** — one plain sentence a non-trader can act on "
                 "(\"NO ACTION at $X\" or \"TRIM 0.25 BTC at $Y\") plus the bias in one clause.")
        L.append("1. **Market State** — regime, where price sits against structure, sweep status, gate.")
        L.append("2. **The Four Pillars** — one block each, every number labelled MEASURED or DERIVED.")
        L.append("3. **The Levels Map** — every level with distance in % and its type.")
        L.append("4. **Rail B (Buy) Plan** — trigger, what is missing, stop, the sizing result "
                 "including the conflict if any, target.")
        L.append("5. **Rail A (Sell/Trim) Plan** — tranches with price windows, invalidation number, "
                 "target.")
        L.append("6. **If / Then block** — the price alerts as a list; the only part that gets re-read.")
        L.append("7. **Not verified** — OKX-not-Binance, modelled dollars, assumed weights, "
                 "any UNAVAILABLE.")
        L.append("")
        L.append("*Never forecast. State what the rules permit, name the trigger that would change the "
                 "answer, and stop. Jargon is allowed in 1-7 and never in 0.*")
    L.append("")
    L.append("---")
    L.append("*Generated by salam_protocol.py — standard library only, closed bars only, no state. "
             "UNAVAILABLE is a valid answer; every estimated figure carries its label.*")
    return "\n".join(L) + "\n"


# ────────────────────────────────── main ──────────────────────────────────
def selftest() -> int:
    """Offline maths assertions + one live cross-venue consistency check."""
    fails: list[str] = []

    def check(name: str, cond: bool, detail: str = ""):
        print(("  PASS  " if cond else "  FAIL  ") + name + (f"  ({detail})" if detail else ""))
        if not cond:
            fails.append(name)

    now = datetime.now(timezone.utc).timestamp() * 1000
    bars = []
    for i in range(60):                       # zig-zag so pivots exist, base near a round 1000
        c = 1000.0 + i + (14.0 if i % 4 == 2 else -9.0 if i % 4 == 0 else 0.0)
        bars.append({"open_time": int(now) - (40 - i) * 3_600_000, "o": c - 0.5, "h": c + 1.0,
                     "l": c - 1.0, "c": c, "v": 10.0, "close_time": int(now) - (39 - i) * 3_600_000,
                     "taker_buy": 6.0})
    print("offline")
    check("ATR is positive", (atr_wilder(bars, 14) or 0) > 0)
    check("CVD = sum(2*taker_buy - volume)",
          abs((cvd(bars, 4) or 0) - 4 * (2 * 6.0 - 10.0)) < 1e-9, f"{cvd(bars, 4)}")
    vp = volume_profile(bars)
    check("volume profile has POC/VAH/VAL", bool(vp) and vp["val"] <= vp["poc"] <= vp["vah"])
    check("HVN returns a level", hvn_nearest(vp, vp["poc"]) is not None)
    band = {"low": min(b["l"] for b in bars) - 5, "high": max(b["h"] for b in bars) + 5,
            "center": vp["poc"]}
    check("confluence maxes at 10 with POC+VA+round", confluence(band, vp)[0] == 10,
          f"{confluence(band, vp)}")
    cl = cluster([100.0, 100.5, 130.0], 0.01)
    check("clustering merges within 1%", len(cl) == 2, f"{len(cl)} clusters")
    hi, lo_ = pivots(bars, 2)
    check("pivots found", len(hi) >= 1 and len(lo_) >= 1, f"{len(hi)} highs / {len(lo_)} lows")

    base = {"price": 1000.0, "problems": [], "cvd_spot": {}, "cvd_perp": {},
            "sweep": {"flag": "NONE"}, "deriv_src": "BINANCE"}
    _now = datetime.now(timezone.utc)
    fresh = (_now - timedelta(minutes=4)).strftime("%H:%M") + "Z"
    stale = (_now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M") + "Z"
    full = dict(base, perp_cvd_ok=True, exec_state="FULL")
    check("FULL state prints execution rules", "Execution Rules" in render(full))
    part = dict(base, perp_cvd_ok=False, exec_state="PARTIAL",
                perp_dump={"date": "2026-11-24", "bars": 24, "cvd_4h": 1.0, "cvd_24h": 2.0})
    part_md = render(part)
    check("PARTIAL state suspends execution", "EXECUTION SUSPENDED" in part_md)
    check("PARTIAL state withholds the rails",
          "Rail B (USDT -> BTC)" not in part_md and "Rail A (BTC -> USDT)" not in part_md)
    check("PARTIAL state still names the archive day", "PARTIAL ORDER FLOW" in part_md)
    none_md = render(dict(base, perp_cvd_ok=False, exec_state="NONE"))
    check("NONE state warns plainly", "PERP CVD UNAVAILABLE" in none_md)
    man_md = render(dict(base, perp_cvd_ok=False, exec_state="MANUAL", manual_at=fresh,
                         manual={"perp_cvd_24h": "+2663", "at": fresh}))
    check("MANUAL state unlocks the rails", "Execution Rules" in man_md and "MANUAL" in man_md)

    import datetime as _dt
    _day = _dt.date(2026, 11, 24)
    _base_ms = int(_dt.datetime(2026, 11, 24, tzinfo=timezone.utc).timestamp() * 1000)
    good = [{"t": _base_ms + h * 3600_000, "v": 1.0, "taker_buy": 0.6} for h in range(24)]
    dup = [{"t": _base_ms, "v": 1.0, "taker_buy": 0.6} for _ in range(24)]
    split = [{"t": _base_ms + h * 3600_000, "v": 1.0, "taker_buy": 0.6} for h in range(12)] + \
            [{"t": _base_ms + 86_400_000 + h * 3600_000, "v": 1.0, "taker_buy": 0.6}
             for h in range(12)]
    _h = 3600_000
    _t0 = 1_700_000_000_000
    _reg = list(range(0, 24))                      # 24 contiguous hourly samples
    _treg = [_t0 + h * _h for h in _reg]
    # index 20 is the 4-hour mark: 90 -> 95 is +5.56%. The first version of this fixture put
    # 90 at index 21 and asserted against index 20, so the test failed against correct code.
    # 24 samples, index 23 is newest; the 4H mark is index 19. 90 -> 95 = +5.56%.
    # Two earlier fixtures put the 90 one or two slots late and asserted against the wrong
    # index, which failed against correct code — the fixture was wrong, not the function.
    _sreg = [100.0] * 19 + [90.0, 91.0, 92.0, 93.0, 95.0]
    check("OI change matches the horizon by timestamp",
          oi_change(_sreg, _treg, 4) is not None
          and abs(oi_change(_sreg, _treg, 4) - (95.0 / 90.0 - 1) * 100) < 1e-9,
          f"{oi_change(_sreg, _treg, 4)}")
    _gap_t = [t for i, t in enumerate(_treg) if not (19 <= i <= 21)]   # drop 3 hours at the mark
    _gap_s = [v for i, v in enumerate(_sreg) if not (19 <= i <= 21)]
    check("a gap at the horizon returns UNAVAILABLE, not a shifted window",
          oi_change(_gap_s, _gap_t, 4) is None, f"{oi_change(_gap_s, _gap_t, 4)}")
    check("mismatched series and stamps return UNAVAILABLE",
          oi_change(_sreg, _treg[:-1], 4) is None)

    import io as _io
    import zipfile as _zip

    def _z(rows):
        buf = _io.BytesIO()
        with _zip.ZipFile(buf, "w") as z:
            z.writestr("BTCUSDT-1h.csv", "\n".join(rows))
        return buf.getvalue()

    _yday = _dt.datetime.now(timezone.utc).date() - _dt.timedelta(days=1)
    _b = int(_dt.datetime(_yday.year, _yday.month, _yday.day, tzinfo=timezone.utc).timestamp() * 1000)
    _real = [f"{_b + h * 3600000},1,1,1,1,1.0,0,0,1,0.6,0,0" for h in range(24)]
    _d, _e = perp_cvd_from_dump(1, fetch=lambda _u: _z(_real))
    check("the loader accepts a genuine 24-hour dump", _d is not None, str(_e))
    _d2, _e2 = perp_cvd_from_dump(1, fetch=lambda _u: _z([_real[0]] * 24))
    check("the loader refuses 24 copies of one hour",
          _d2 is None and "unusable" in (_e2 or ""), str(_e2))

    check("a complete 24-hour archive day is accepted", dump_day_problem(good, _day) is None)
    check("24 copies of one hour are rejected", dump_day_problem(dup, _day) is not None,
          str(dump_day_problem(dup, _day)))
    check("a day split across two dates is rejected", dump_day_problem(split, _day) is not None,
          str(dump_day_problem(split, _day)))
    check("23 rows are rejected", dump_day_problem(good[:23], _day) is not None)

    _noatr = render(dict(base, perp_cvd_ok=True, exec_state="FULL", atr1h=None))
    check("missing ATR never prints a zero stop distance",
          "UNAVAILABLE)" in _noatr and "= 0)" not in _noatr)
    _settling = render(dict(base, perp_cvd_ok=True, exec_state="FULL", etf={
        "latest_date": "26 Nov 2026", "one_day_m": -100.0, "one_day_settling": True,
        "five_day_m": -200.0}))
    check("a settling ETF row is labelled settling", "settling" in _settling)

    check("a candle-close price is never labelled as a ticker",
          "[BIN-CLOSE 1D]" in render(dict(base, perp_cvd_ok=True, exec_state="FULL",
                                          price_src="CLOSE-1D")))
    check("a ticker price still reads [BIN]",
          "[BIN]" in render(dict(base, perp_cvd_ok=True, exec_state="FULL", price_src="TICKER")))

    okx_md = render(dict(base, perp_cvd_ok=True, exec_state="FULL", perp_src="OKX-RUBIK"))
    check("OKX perp CVD is labelled and still execution-grade",
          "OKX-RUBIK" in okx_md and "Execution Rules" in okx_md)
    _, ok_num = parse_manual(f"perp_cvd_24h=+2663,at={fresh}")
    _, ok_adj = parse_manual(f"perp_cvd=falling,spot_cvd=flat,at={fresh}")
    _, ok_junk = parse_manual("perp_cvd_24h=+2663,at=garbageZ")
    _, ok_stale = parse_manual(f"perp_cvd_24h=+2663,at={stale}")
    _, ok_noat = parse_manual("perp_cvd_24h=+2663")
    check("manual with a number + fresh time unlocks", ok_num is True)
    check("manual adjective does NOT unlock", ok_adj is False)
    check("manual with an unparseable time does NOT unlock", ok_junk is False)
    check("manual older than the freshness ceiling does NOT unlock", ok_stale is False)
    check("manual with no time does NOT unlock", ok_noat is False)

    print("live")
    try:
        binance = float(get_json(f"{SPOT}/ticker/price?symbol=BTCUSDT")["price"])
        okx = float(get_json(f"{OKX}/api/v5/market/ticker?instId=BTC-USDT")["data"][0]["last"])
        div = abs(binance - okx) / binance * 100
        check("spot BIN vs OKX within 0.50%", div <= 0.5,
              f"{binance:,.1f} vs {okx:,.1f} = {div:.3f}%")
    except Exception as e:                                     # noqa: BLE001
        print(f"  SKIP  spot cross-venue ({type(e).__name__})")

    try:
        oi, err = safe(lambda: float(get_json(
            f"{FAPI}/fapi/v1/openInterest?symbol=BTCUSDT")["openInterest"]), "oi")
        if err:
            oi, err = safe(lambda: float(get_json(
                f"{OKX}/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP"
            )["data"][0]["oiCcy"]), "okx_oi")
        check("open interest > 0", bool(oi) and oi > 0, f"{oi or 0:,.0f} BTC")
    except Exception as e:                                     # noqa: BLE001
        print(f"  SKIP  open interest ({type(e).__name__})")

    print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Salam Data Packet Protocol v1.0")
    ap.add_argument("--out", default=".", help="output directory (default: current)")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    ap.add_argument("--json", action="store_true", help="also write SALAM_DATA_HUB.json")
    ap.add_argument("--check", action="store_true", help="endpoint health only")
    ap.add_argument("--selftest", action="store_true", help="assert maths + cross-venue agreement")
    ap.add_argument("--manual", default=None,
                    help='screenshot reading, e.g. "perp_cvd=falling,spot_cvd=flat,at=14:32Z" '
                         '— printed verbatim, tagged [MANUAL], never merged into a live field')
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

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
    _g = datetime.now(timezone.utc)
    a["generated_at_utc"] = _g.strftime("%Y-%m-%dT%H:%M:%SZ")
    a["generated_at_sgt"] = (_g + timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    man, man_ok = parse_manual(args.manual)
    a["manual"], a["manual_ok"], a["manual_at"] = (man or None), man_ok, man.get("at")
    if a.get("perp_cvd_ok"):
        a["exec_state"] = "FULL"
    elif man_ok:
        a["exec_state"] = "MANUAL"
    elif a.get("perp_dump"):
        a["exec_state"] = "PARTIAL"
    else:
        a["exec_state"] = "NONE"
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
