"""5-year retest of the SOXL · LABU · DPST pattern study (the claude.ai page "SOXL · LABU · DPST Patterns").

The page tested two years (Sep 2024 - Sep 2026). This script re-runs the same tests on five years of
daily bars (Oct 7, 2021 - Oct 6, 2026) and on all the hourly bars Yahoo keeps (Nov 2023 - Oct 2026).
Definitions follow the page: Wilder RSI, Bollinger 20-day +/-2 sd, a 2-sigma day is a move beyond twice
the trailing 60-day standard deviation, costs 0.05% per side, trades at the close.

Input:  data/soxl-labu-dpst/raw/*.json (run fetch_prices.py first)
Output: data/soxl-labu-dpst/results_5y.json, and a text report on screen.
Run from the repo root:  python3 backtests/soxl-labu-dpst/analyze.py
Uses only the Python standard library.
"""
import collections
import datetime as dt
import json
import math
import pathlib
import random
import statistics
import zoneinfo

RAW = pathlib.Path("data/soxl-labu-dpst/raw")
OUT = pathlib.Path("data/soxl-labu-dpst/results_5y.json")
FUNDS = ["SOXL", "LABU", "DPST"]
START, END = dt.date(2021, 10, 7), dt.date(2026, 10, 6)
YEAR_STARTS = [dt.date(2021 + k, 10, 7) for k in range(5)]  # year k+1 runs Oct 7 to the next Oct 6
COST = 0.0005  # per side
NY = zoneinfo.ZoneInfo("America/New_York")

# FOMC decision days (statement released at 2:00 pm ET)
FOMC = [dt.date.fromisoformat(s) for s in """
2021-11-03 2021-12-15 2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13 2024-01-31 2024-03-20
2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18
2025-07-30 2025-09-17 2025-10-29 2025-12-10 2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16
""".split()]


# ---------------------------------------------------------------- statistics (stdlib only)

def mean(x):
    return sum(x) / len(x) if x else float("nan")


def _betacf(a, b, x):
    tiny, qab, qap, qam = 1e-300, a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 3e-14:
            break
    return h


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def t_pvalue(t, df):
    """Two-sided p-value of Student's t with df degrees of freedom."""
    return betainc(df / 2, 0.5, df / (df + t * t))


def welch_p(a, b):
    """Two-sided p-value of Welch's t-test (do the two groups have different means?)."""
    if len(a) < 3 or len(b) < 3:
        return None
    va, vb = statistics.variance(a) / len(a), statistics.variance(b) / len(b)
    if va + vb == 0:
        return None
    t = (mean(a) - mean(b)) / math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    return t_pvalue(t, df)


def binom_p(k, n, p0):
    """Two-sided normal-approximation test of k successes in n tries against chance p0."""
    if n == 0:
        return None
    z = (k - n * p0) / math.sqrt(n * p0 * (1 - p0))
    return math.erfc(abs(z) / math.sqrt(2))


def bh_qvalues(ps):
    """Benjamini-Hochberg false-discovery q-values, same order as ps."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    q, running = [0.0] * len(ps), 1.0
    for rank in range(len(ps), 0, -1):
        i = order[rank - 1]
        running = min(running, ps[i] * len(ps) / rank)
        q[i] = running
    return q


def pct(x, nd=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(100 * x, nd)


def quantile(x, q):
    s = sorted(x)
    return s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))]


def year_of(d):
    return sum(d >= y for y in YEAR_STARTS)  # 1..5 inside the window


# ---------------------------------------------------------------- data

def load_chart(path):
    r = json.loads(path.read_text())["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    rows = []
    for i, t in enumerate(r["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c) or c <= 0:
            continue
        f = adj[i] / c if adj and adj[i] else 1.0  # dividend adjustment factor (prices are already split-adjusted)
        rows.append({"t": dt.datetime.fromtimestamp(t, NY), "o": o * f, "h": h * f, "l": l * f, "c": c * f, "f": f})
    return rows


def wilder_rsi(closes, n):
    out, ag, al = [None] * len(closes), None, None
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0), max(-ch, 0)
        if i < n:
            continue
        if ag is None:
            chs = [closes[k] - closes[k - 1] for k in range(1, n + 1)]
            ag, al = mean([max(c, 0) for c in chs]), mean([max(-c, 0) for c in chs])
        else:
            ag, al = (ag * (n - 1) + g) / n, (al * (n - 1) + l) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def daily_table(sym, vix):
    rows = {}
    for r in load_chart(RAW / f"daily_{sym}.json"):
        rows[r["t"].date()] = r  # last row of a date wins
    D = [dict(date=d, **{k: v for k, v in r.items() if k != "t"}) for d, r in sorted(rows.items())]
    closes = [d["c"] for d in D]
    rsi2, rsi14 = wilder_rsi(closes, 2), wilder_rsi(closes, 14)
    streak = 0
    for i, d in enumerate(D):
        d["rsi2"], d["rsi14"], d["vix"] = rsi2[i], rsi14[i], vix.get(d["date"])
        if i == 0:
            continue
        p = D[i - 1]
        d["ret"], d["gap"], d["intra"] = d["c"] / p["c"] - 1, d["o"] / p["c"] - 1, d["c"] / d["o"] - 1
        streak = (streak + 1 if streak > 0 else 1) if d["ret"] > 0 else (streak - 1 if streak < 0 else -1) if d["ret"] < 0 else 0
        d["streak"] = streak
        if i >= 20:
            w = closes[i - 19:i + 1]
            m, sd = mean(w), statistics.pstdev(w)
            d["sma20"], d["z20"] = m, (d["c"] - m) / sd if sd else 0
            d["dd20"] = d["c"] / max(w) - 1
        if i >= 5:
            d["sma5"] = mean(closes[i - 4:i + 1])
        if i >= 61:
            d["sd60"] = statistics.stdev([D[k]["ret"] for k in range(i - 60, i)])  # the 60 returns before today
    for i, d in enumerate(D):
        d["fwd1"] = D[i + 1]["ret"] if i + 1 < len(D) else None
        d["fwd5"] = D[i + 5]["c"] / d["c"] - 1 if i + 5 < len(D) else None
    return D


def hourly_days(sym, D):
    """Per day: prev close, official open, the price at each half-hour mark from the hourly bars, close."""
    by_date = {d["date"]: (i, d) for i, d in enumerate(D)}
    bars = collections.defaultdict(list)
    for r in load_chart(RAW / f"hourly_{sym}.json"):
        if r["t"].hour < 16:
            bars[r["t"].date()].append(r)
    out = []
    for day, bs in sorted(bars.items()):
        times = [b["t"].strftime("%H:%M") for b in bs]
        if times != ["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"] or day not in by_date:
            continue  # half days and incomplete days are left out
        i, d = by_date[day]
        if i == 0 or not (START <= day <= END):
            continue
        f = d["f"]  # put the hourly prices on the same dividend-adjusted basis as the daily bars
        marks = [b["c"] * f for b in bs[:6]]  # prices at 10:30, 11:30, 12:30, 1:30, 2:30, 3:30
        if abs(bs[6]["c"] * f / d["c"] - 1) > 0.01:
            continue  # hourly data disagrees with the official close: skip the day
        pc, o, c = D[i - 1]["c"], d["o"], d["c"]
        path = [o] + marks + [c]
        segs = [o / pc - 1] + [path[k + 1] / path[k] - 1 for k in range(7)]
        lows = [b["l"] * f for b in bs]
        out.append(dict(date=day, pc=pc, o=o, c=c, ret=c / pc - 1, gap=o / pc - 1, segs=segs, p1030=marks[0],
                        p330=marks[5], low_bar=lows.index(min(lows)), nxt_gap=D[i + 1]["gap"] if i + 1 < len(D) else None))
    return out


# ---------------------------------------------------------------- tests

TESTS = []  # (fund, family, name, p) for the false-discovery check


def record(fund, family, name, p):
    if p is not None:
        TESTS.append([fund, family, name, p])


def by_year(days, key):
    """Mean of `key` in each of the 5 years (None when fewer than 3 days)."""
    ys = collections.defaultdict(list)
    for d in days:
        if d.get(key) is not None:
            ys[year_of(d["date"])].append(d[key])
    return [pct(mean(ys[y])) if len(ys[y]) >= 3 else None for y in range(1, 6)]


def consistency(yearly, overall):
    vals = [v for v in yearly if v is not None]
    return f"{sum((v > 0) == (overall > 0) for v in vals)} of {len(vals)}"


def non_overlapping(idx, gap=5):
    out, last = [], -10 ** 9
    for i in idx:
        if i - last >= gap:
            out.append(i)
            last = i
    return out


def signal_table(sym, D, W):
    rets = [d["ret"] for d in W]
    p10, p90 = quantile(rets, 0.10), quantile(rets, 0.90)
    sigs = {
        f"After a bottom-10% day (<= {pct(p10, 1)}%)": lambda d: d["ret"] <= p10,
        f"After a top-10% day (>= +{pct(p90, 1)}%)": lambda d: d["ret"] >= p90,
        "After a 2-sigma drop": lambda d: d["ret"] < -2 * d["sd60"],
        "RSI(2) below 10": lambda d: d["rsi2"] < 10,
        "RSI(2) above 90": lambda d: d["rsi2"] > 90,
        "RSI(14) below 30": lambda d: d["rsi14"] < 30,
        "RSI(14) above 70": lambda d: d["rsi14"] > 70,
        "Close below lower Bollinger band": lambda d: d["z20"] < -2,
        "Close above upper Bollinger band": lambda d: d["z20"] > 2,
        "30%+ below 20-day high": lambda d: d["dd20"] <= -0.30,
        "3+ down days in a row": lambda d: d["streak"] <= -3,
        "3+ up days in a row": lambda d: d["streak"] >= 3,
        "Gap down 5%+, closes below open": lambda d: d["gap"] <= -0.05 and d["c"] < d["o"],
    }
    base1 = [d["fwd1"] for d in W if d["fwd1"] is not None]
    pos = {id(d): i for i, d in enumerate(W)}
    base5 = [W[i]["fwd5"] for i in range(0, len(W), 5) if W[i]["fwd5"] is not None]
    rows = []
    for name, fn in sigs.items():
        hit = [d for d in W if fn(d)]
        f1 = [d["fwd1"] for d in hit if d["fwd1"] is not None]
        rest1 = [d["fwd1"] for d in W if d["fwd1"] is not None and not fn(d)]
        nov = [W[i] for i in non_overlapping([pos[id(d)] for d in hit]) if W[i]["fwd5"] is not None]
        f5 = [d["fwd5"] for d in nov]
        p1, p5 = welch_p(f1, rest1), welch_p(f5, base5)
        record(sym, "signal", name + " (next day)", p1)
        record(sym, "signal", name + " (next 5 days)", p5)
        y1 = by_year(hit, "fwd1")
        rows.append(dict(name=name, n=len(hit), d1=pct(mean(f1)), hit1=pct(mean([x > 0 for x in f1]), 1) if f1 else None,
                         d5=pct(mean([d["fwd5"] for d in hit if d["fwd5"] is not None])),
                         hit5=pct(mean([d["fwd5"] > 0 for d in hit if d["fwd5"] is not None]), 1) if hit else None,
                         p1=p1, p5=p5, years_d1=y1, same_sign_years=consistency(y1, mean(f1)) if f1 else None))
    return dict(base1=pct(mean(base1)), base5=pct(mean([d["fwd5"] for d in W if d["fwd5"] is not None])),
                hit1_all=pct(mean([x > 0 for x in base1]), 1), rows=rows)


def weekday_table(sym, W):
    out = []
    for wd, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]):
        a = [d for d in W if d["date"].weekday() == wd]
        b = [d for d in W if d["date"].weekday() != wd]
        p = welch_p([d["ret"] for d in a], [d["ret"] for d in b])
        pg = welch_p([d["gap"] for d in a], [d["gap"] for d in b])
        record(sym, "weekday", name, p)
        record(sym, "weekday", name + " overnight gap", pg)
        yr = by_year(a, "ret")
        out.append(dict(day=name, n=len(a), mean=pct(mean([d["ret"] for d in a])), median=pct(statistics.median([d["ret"] for d in a])),
                        pct_up=pct(mean([d["ret"] > 0 for d in a]), 1), overnight=pct(mean([d["gap"] for d in a])),
                        intraday=pct(mean([d["intra"] for d in a])), p=p, p_gap=pg, years=yr,
                        years_gap=by_year(a, "gap")))
    return out


def event_table(sym, W, D):
    fomc = set(FOMC)
    idx = {d["date"]: i for i, d in enumerate(D)}
    day = [d for d in W if d["date"] in fomc]
    nxt = [D[idx[d["date"]] + 1] for d in day if idx[d["date"]] + 1 < len(D)]
    nxt_dates = {d["date"] for d in nxt}
    rest = [d["ret"] for d in W if d["date"] not in fomc]
    rest2 = [d["ret"] for d in W if d["date"] not in nxt_dates]
    p_day, p_next = welch_p([d["ret"] for d in day], rest), welch_p([d["ret"] for d in nxt], rest2)
    record(sym, "fed", "FOMC decision day", p_day)
    record(sym, "fed", "Day after FOMC", p_next)
    out = dict(fomc_day=dict(n=len(day), mean=pct(mean([d["ret"] for d in day])), pct_up=pct(mean([d["ret"] > 0 for d in day]), 1), p=p_day, years=by_year(day, "ret")),
               fomc_next=dict(n=len(nxt), mean=pct(mean([d["ret"] for d in nxt])), pct_up=pct(mean([d["ret"] > 0 for d in nxt]), 1), p=p_next, years=by_year(nxt, "ret")))
    # calendar: turn of month (last day + first 3 days), monthly options expiration (3rd Friday)
    dates = [d["date"] for d in D]
    tom = set()
    for i in range(1, len(dates)):
        if dates[i].month != dates[i - 1].month:
            tom.update(dates[max(0, i - 1):i + 3])
    opex = set()
    for y in range(2021, 2027):
        for m in range(1, 13):
            fri = [dt.date(y, m, k) for k in range(15, 22) if dt.date(y, m, k).weekday() == 4][0]
            while fri not in idx and fri.day > 1:
                fri -= dt.timedelta(days=1)  # holiday: expiration moves to the day before
            if fri in idx:
                opex.add(fri)
    opex_week = {d for d in dates if any(0 <= (o - d).days <= 4 and o.isocalendar()[1] == d.isocalendar()[1] for o in opex)}
    after = {D[idx[o] + 1]["date"] for o in opex if idx[o] + 1 < len(D)}
    for name, s in [("Turn of the month", tom), ("Options-expiration Friday", opex), ("Options-expiration week", opex_week), ("Day after expiration", after)]:
        a = [d["ret"] for d in W if d["date"] in s]
        b = [d["ret"] for d in W if d["date"] not in s]
        p = welch_p(a, b)
        record(sym, "calendar", name, p)
        out[name] = dict(n=len(a), mean=pct(mean(a)), rest=pct(mean(b)), p=p)
    return out


def vix_table(sym, W):
    edges = [(0, 15, "Under 15"), (15, 20, "15-20"), (20, 25, "20-25"), (25, 30, "25-30"), (30, 999, "30+")]
    out = []
    days = [d for d in W if d["vix"] is not None and d["fwd5"] is not None]
    for lo, hi, name in edges:
        a = [d for d in days if lo <= d["vix"] < hi]
        b = [d["fwd5"] for d in days if not lo <= d["vix"] < hi]
        runs, prev = 0, False
        for d in days:
            inb = lo <= d["vix"] < hi
            runs += inb and not prev
            prev = inb
        p = welch_p([W_d["fwd5"] for W_d in non_overlap_days(a)], b[::5])
        record(sym, "vix", "VIX " + name, p)
        out.append(dict(vix=name, n=len(a), episodes=runs, fwd5=pct(mean([d["fwd5"] for d in a])),
                        hit=pct(mean([d["fwd5"] > 0 for d in a]), 1) if a else None, p=p, years=by_year(a, "fwd5")))
    return out


def non_overlap_days(days, gap=5):
    out, last = [], None
    for d in days:
        if last is None or (d["date"] - last).days >= gap + 2:
            out.append(d)
            last = d["date"]
    return out


def structure(sym, W, D):
    rets = [d["ret"] for d in W]
    gaps = []
    for lo, hi, name in [(-9, -0.05, "gap <= -5%"), (-0.05, -0.02, "gap -5% to -2%"), (-0.02, 0, "gap -2% to 0"),
                         (0, 0.02, "gap 0 to +2%"), (0.02, 0.05, "gap +2% to +5%"), (0.05, 9, "gap >= +5%")]:
        a = [d for d in W if lo < d["gap"] <= hi] if lo < 0 else [d for d in W if lo <= d["gap"] < hi]
        pcs = {id(d): D[D.index(d) - 1]["c"] for d in a}
        filled = [(d["h"] >= pcs[id(d)]) if d["gap"] < 0 else (d["l"] <= pcs[id(d)]) for d in a]
        gaps.append(dict(bucket=name, n=len(a), fill_rate=pct(mean(filled), 1) if a else None,
                         intra=pct(mean([d["intra"] for d in a])), next_day=pct(mean([d["fwd1"] for d in a if d["fwd1"] is not None]))))
    two = [abs(d["ret"]) > 2 * d["sd60"] for d in W]
    after_two = [two[i] for i in range(1, len(two)) if two[i - 1]]
    drop = [d["l"] / d["o"] - 1 for d in W]
    # weeks
    weeks = collections.defaultdict(list)
    for d in W:
        weeks[d["date"].isocalendar()[:2]].append(d)
    wk_ret = [w[-1]["c"] / w[0]["o"] - 1 for w in weeks.values()]
    wk_deep = [min(x["l"] for x in w) / w[0]["o"] - 1 for w in weeks.values()]
    worst_wk = min(weeks.values(), key=lambda w: w[-1]["c"] / w[0]["o"])
    full = [w for w in weeks.values() if len(w) == 5]
    obs_low = collections.Counter(min(range(5), key=lambda k: w[k]["l"]) for w in full)
    # chance: 4,000 weeks built from 5 random days of the same fund, each day as moves relative to its prior close
    rng = random.Random(7)
    pool = [(d["o"] / (d["c"] / (1 + d["ret"])), d["l"] / (d["c"] / (1 + d["ret"])), 1 + d["ret"]) for d in W]
    sim = collections.Counter()
    for _ in range(4000):
        px, lows = 1.0, []
        for _k in range(5):
            o, l, c = rng.choice(pool)
            lows.append(px * l)
            px *= c
        sim[lows.index(min(lows))] += 1
    chance_mf = (sim[0] + sim[4]) / 4000
    k_mf = obs_low[0] + obs_low[4]
    p_wk = binom_p(k_mf, len(full), chance_mf)
    record(sym, "week", "Week low on Monday or Friday", p_wk)
    big = max(W, key=lambda d: d["ret"])
    small = min(W, key=lambda d: d["ret"])
    return dict(
        sessions=len(W), start_close=round(D[D.index(W[0]) - 1]["c"], 2), end_close=round(W[-1]["c"], 2),
        largest_up=[str(big["date"]), pct(big["ret"], 1)], largest_down=[str(small["date"]), pct(small["ret"], 1)],
        mean_abs=pct(mean([abs(r) for r in rets])), median_abs=pct(statistics.median([abs(r) for r in rets])),
        days_down_10=sum(r <= -0.10 for r in rets), days_up_10=sum(r >= 0.10 for r in rets), pct_up=pct(mean([r > 0 for r in rets]), 1),
        worst_week=[str(worst_wk[0]["date"]), pct(worst_wk[-1]["c"] / worst_wk[0]["o"] - 1, 1)],
        mean_down_week=pct(mean([r for r in wk_ret if r < 0])), pct_weeks_down=pct(mean([r < 0 for r in wk_ret]), 1),
        deepest_in_week=pct(min(wk_deep), 1),
        gaps=gaps, two_sigma_rate=pct(mean(two), 1), two_sigma_after_two_sigma=pct(mean(after_two), 1), n_two_sigma=sum(two),
        drop_from_open_median=pct(statistics.median(drop), 1), drop_from_open_p10=pct(quantile(drop, 0.10), 1),
        week_low=dict(full_weeks=len(full), observed=[round(100 * obs_low[k] / len(full), 1) for k in range(5)],
                      chance=[round(100 * sim[k] / 4000, 1) for k in range(5)], mon_or_fri=round(100 * k_mf / len(full), 1),
                      chance_mon_or_fri=round(100 * chance_mf, 1), p=p_wk))


# ---------------------------------------------------------------- backtests

def simulate(W, entry, exit_):
    """Trades at the close. entry(i) opens when flat; exit_(entry_i, i) closes. Costs 0.05% per side."""
    eq, pos, ei, held, trades, curve, peak, mdd = 1.0, False, None, 0, [], [], 1.0, 0.0
    for i in range(len(W)):  # W[0] is the close before the window: only buy & hold enters there
        if pos:
            eq *= W[i]["c"] / W[i - 1]["c"]
            held += 1
            if exit_(ei, i):
                eq *= 1 - COST
                trades.append((W[ei]["date"], W[i]["date"], W[i]["c"] / W[ei]["c"] * (1 - COST) ** 2 - 1))
                pos = False
        elif entry(i):
            eq *= 1 - COST
            pos, ei = True, i
        if i > 0:
            peak, mdd = max(peak, eq), min(mdd, eq / max(peak, eq) - 1)
            curve.append((W[i]["date"], eq))
    open_trade = None
    if pos:
        open_trade = (str(W[ei]["date"]), pct(W[-1]["c"] / W[ei]["c"] - 1))
    return summarize(curve, mdd, trades, held / (len(W) - 1), open_trade)


def summarize(curve, mdd, trades, exposure, open_trade=None):
    yearly, start_eq = [], 1.0
    for y in range(1, 6):
        pts = [e for d, e in curve if year_of(d) == y]
        if pts:
            yearly.append(pct(pts[-1] / start_eq - 1, 1))
            start_eq = pts[-1]
    total = curve[-1][1]
    years = (curve[-1][0] - curve[0][0]).days / 365.25
    rets = [t[2] for t in trades]
    return dict(total=pct(total - 1, 1), cagr=pct(total ** (1 / years) - 1, 1), max_dd=pct(mdd, 1), years=yearly,
                trades=len(trades), win_rate=pct(mean([r > 0 for r in rets]), 1) if rets else None,
                avg_trade=pct(mean(rets)) if rets else None, exposure=pct(exposure, 1), open_trade=open_trade,
                curve=[(str(d), round(e, 4)) for d, e in curve[::5] + ([curve[-1]] if (len(curve) - 1) % 5 else [])])


def session_split(W, part, cost=COST):
    """Hold only overnight (close to open) or only during the day (open to close); one round trip per day."""
    eq, peak, mdd, curve = 1.0, 1.0, 0.0, []
    for d in W[1:]:
        eq *= (1 + d["gap" if part == "night" else "intra"]) * (1 - cost) ** 2
        peak, mdd = max(peak, eq), min(mdd, eq / max(peak, eq) - 1)
        curve.append((d["date"], eq))
    return summarize(curve, mdd, [], 1.0)


def backtests(sym, W):
    fomc = set(FOMC)
    rules = {
        "Buy & hold": (lambda i: i == 0, lambda e, i: False),
        "RSI(2)<10 -> exit above 5-day avg": (lambda i: W[i]["rsi2"] < 10, lambda e, i: W[i]["c"] > W[i]["sma5"]),
        "RSI(2)<10 -> exit above 5-day avg or day 10": (lambda i: W[i]["rsi2"] < 10, lambda e, i: W[i]["c"] > W[i]["sma5"] or i - e >= 10),
        "Down >=2-sigma day -> hold 3 days": (lambda i: W[i]["ret"] < -2 * W[i]["sd60"], lambda e, i: i - e >= 3),
        "3 down days -> exit first up day": (lambda i: W[i]["streak"] <= -3, lambda e, i: W[i]["ret"] > 0),
        "Close below lower Bollinger -> exit above 20-day avg": (lambda i: W[i]["z20"] < -2, lambda e, i: W[i]["c"] > W[i]["sma20"]),
        "Tuesday close -> Wednesday close": (lambda i: W[i]["date"].weekday() == 1, lambda e, i: True),
        "FOMC-day close -> next close": (lambda i: W[i]["date"] in fomc, lambda e, i: True),
    }
    out = {name: simulate(W, en if name == "Buy & hold" else (lambda i, en=en: i >= 1 and en(i)), ex) for name, (en, ex) in rules.items()}
    out["Overnight only (close->open)"] = session_split(W, "night")
    out["Intraday only (open->close)"] = session_split(W, "day")
    out["Overnight only, before costs"] = session_split(W, "night", 0)
    out["Intraday only, before costs"] = session_split(W, "day", 0)
    # Tuesday close -> Wednesday open (the Tuesday-night gap alone)
    eq, peak, mdd, curve, trades = 1.0, 1.0, 0.0, [], []
    for d in W[1:]:
        if d["date"].weekday() == 2:
            r = (1 + d["gap"]) * (1 - COST) ** 2
            eq *= r
            trades.append((d["date"], d["date"], r - 1))
        peak, mdd = max(peak, eq), min(mdd, eq / max(peak, eq) - 1)
        curve.append((d["date"], eq))
    out["Tuesday close -> Wednesday open"] = summarize(curve, mdd, trades, 0.2)
    return out


# ---------------------------------------------------------------- intraday (hourly bars)

SEGS = ["Overnight", "9:30-10:30", "10:30-11:30", "11:30-12:30", "12:30-1:30", "1:30-2:30", "2:30-3:30", "3:30-4:00"]


def intraday(sym, H):
    out = dict(days=len(H), first=str(H[0]["date"]), last=str(H[-1]["date"]))
    out["abs_move"] = [pct(mean([abs(h["segs"][k]) for h in H])) for k in range(8)]
    down = [h for h in H if h["ret"] < 0]
    tot = sum(math.log(1 + h["ret"]) for h in down)
    share = [sum(math.log(1 + h["segs"][k]) for h in down) / tot for k in range(8)]
    out["down_day_loss_share"] = dict(overnight=pct(share[0], 1), first_hour=pct(share[1], 1), rest=pct(sum(share[2:]), 1))
    p10 = quantile([h["ret"] for h in H], 0.10)
    for name, days in [("low_hour_up_days", [h for h in H if h["ret"] > 0]), ("low_hour_worst10", [h for h in H if h["ret"] <= p10])]:
        cnt = collections.Counter(h["low_bar"] for h in days)
        out[name] = [round(100 * cnt[k] / len(days), 1) for k in range(7)]
    # last 30 minutes by where the day stood at 3:30
    rows = []
    for lo, hi, name in [(-9, -0.06, "Down 6%+"), (-0.06, -0.03, "Down 3-6%"), (-0.01, 0.01, "Flat +/-1%"), (0.03, 0.06, "Up 3-6%"), (0.06, 9, "Up 6%+")]:
        a = [h for h in H if lo <= h["p330"] / h["pc"] - 1 < hi]
        b = [h["segs"][7] for h in H if not lo <= h["p330"] / h["pc"] - 1 < hi]
        p = welch_p([h["segs"][7] for h in a], b)
        record(sym, "last30", name + " at 3:30", p)
        rows.append(dict(at_330=name, n=len(a), last30=pct(mean([h["segs"][7] for h in a])), fell=pct(mean([h["segs"][7] < 0 for h in a]), 1) if a else None,
                         p=p, years=hourly_years(a, lambda h: h["segs"][7]), next_gap=pct(mean([h["nxt_gap"] for h in a if h["nxt_gap"] is not None]))))
    out["last30"] = rows
    # opening-gap patterns: first hour, then 10:30 to the close
    pats = []
    for name, fn in [("Gap down 5%+", lambda h: h["gap"] <= -0.05), ("Gap down 2%+", lambda h: h["gap"] <= -0.02),
                     ("Flat open (within 1%)", lambda h: abs(h["gap"]) < 0.01), ("Gap up 2%+", lambda h: h["gap"] >= 0.02),
                     ("Gap up 5%+", lambda h: h["gap"] >= 0.05)]:
        a = [h for h in H if fn(h)]
        b = [h for h in H if not fn(h)]
        fh = [h["segs"][1] for h in a]
        rest_day = [h["c"] / h["p1030"] - 1 for h in a]
        p1 = welch_p(fh, [h["segs"][1] for h in b])
        p2 = welch_p(rest_day, [h["c"] / h["p1030"] - 1 for h in b])
        record(sym, "gap-intraday", name + " first hour", p1)
        record(sym, "gap-intraday", name + " 10:30 to close", p2)
        pats.append(dict(name=name, n=len(a), first_hour=pct(mean(fh)), first_hour_up=pct(mean([x > 0 for x in fh]), 1) if fh else None, p_first=p1,
                         rest_of_day=pct(mean(rest_day)), rest_up=pct(mean([x > 0 for x in rest_day]), 1) if fh else None, p_rest=p2,
                         years_first=hourly_years(a, lambda h: h["segs"][1]), years_rest=hourly_years(a, lambda h: h["c"] / h["p1030"] - 1)))
    out["gap_patterns"] = pats
    return out


def hourly_years(days, fn):
    ys = collections.defaultdict(list)
    for h in days:
        ys[year_of(h["date"])].append(fn(h))
    return {f"Y{y}": [pct(mean(v)), len(v)] for y, v in sorted(ys.items())}


# ---------------------------------------------------------------- report

def main():
    vix = {r["t"].date(): r["c"] for r in load_chart(RAW / "daily_VIX.json")}
    results = {"window": [str(START), str(END)], "funds": {}}
    for sym in FUNDS:
        D = daily_table(sym, vix)
        W = [d for d in D if START <= d["date"] <= END]
        H = hourly_days(sym, D)
        results["funds"][sym] = dict(structure=structure(sym, W, D), signals=signal_table(sym, D, W), weekday=weekday_table(sym, W),
                                     events=event_table(sym, W, D), vix=vix_table(sym, W), backtests=backtests(sym, [D[D.index(W[0]) - 1]] + W),
                                     intraday=intraday(sym, H),
                                     current=dict(date=str(D[-1]["date"]), close=round(D[-1]["c"], 2), rsi2=round(D[-1]["rsi2"], 1),
                                                  rsi14=round(D[-1]["rsi14"], 1), z20=round(D[-1]["z20"], 2), dd20=pct(D[-1]["dd20"], 1),
                                                  sd60=pct(D[-1]["sd60"], 2), vix=D[-1]["vix"]))
    q = bh_qvalues([t[3] for t in TESTS])
    for t, qq in zip(TESTS, q):
        t.append(qq)
    results["fdr"] = dict(n_tests=len(TESTS), n_p_below_05=sum(t[3] < 0.05 for t in TESTS), expected_by_chance=round(0.05 * len(TESTS), 1),
                          n_survive_q10=sum(t[4] < 0.10 for t in TESTS), smallest=sorted(([t[0], t[2], round(t[3], 4), round(t[4], 3)] for t in TESTS), key=lambda x: x[2])[:25])
    OUT.write_text(json.dumps(results, indent=1, default=str))
    print("saved", OUT, "|", results["fdr"]["n_tests"], "tests,", results["fdr"]["n_p_below_05"], "with p<0.05,",
          results["fdr"]["expected_by_chance"], "expected by luck,", results["fdr"]["n_survive_q10"], "survive the false-discovery check")


if __name__ == "__main__":
    main()
