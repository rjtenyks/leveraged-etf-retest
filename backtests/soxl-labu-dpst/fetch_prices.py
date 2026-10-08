"""Download daily and hourly prices for SOXL, LABU, DPST and the VIX from Yahoo Finance.

Daily bars go back to Jan 2021 (warm-up for the indicators before the 5-year window).
Hourly bars: Yahoo keeps about the last 730 sessions.

Output: data/soxl-labu-dpst/raw/daily_<SYM>.json and hourly_<SYM>.json (git-ignored).
Run from the repo root:  python3 backtests/soxl-labu-dpst/fetch_prices.py
Uses only the Python standard library.
"""
import datetime as dt
import pathlib
import time
import urllib.request

OUT = pathlib.Path("data/soxl-labu-dpst/raw")
FUNDS = ["SOXL", "LABU", "DPST"]
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"


def get(symbol, query, dest):
    req = urllib.request.Request(BASE + symbol + "?" + query, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        dest.write_bytes(r.read())
    print("saved", dest)
    time.sleep(1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    start = int(dt.datetime(2021, 1, 1, tzinfo=dt.UTC).timestamp())
    end = int(time.time())
    daily = f"period1={start}&period2={end}&interval=1d&includeAdjustedClose=true&events=div%2Csplits"
    for s in FUNDS:
        get(s, daily, OUT / f"daily_{s}.json")
    get("%5EVIX", daily, OUT / "daily_VIX.json")
    for s in FUNDS:
        get(s, "range=730d&interval=60m&includePrePost=false", OUT / f"hourly_{s}.json")


if __name__ == "__main__":
    main()
