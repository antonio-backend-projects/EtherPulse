
"""
backtest/ingest.py
Scarica e normalizza CSV storici da Binance Futures per ETHUSDT:
- klines 1m (poi si può resamplare a 5m)
- funding 8h
- open interest 1h (rolling 7d per min/max)

Uso:
    python -m backtest.ingest --symbol ETHUSDT --start 2025-06-01 --end 2025-09-30 --out data/
Note:
    - Richiede internet (Binance public REST).
    - Nessuna API key necessaria.
"""
import argparse, os, math, time, csv, datetime as dt, asyncio
import httpx

BINANCE_FAPI_BASE = os.getenv("BINANCE_FAPI_BASE", "https://fapi.binance.com")

def to_ms(d: dt.datetime) -> int:
    return int(d.timestamp() * 1000)

def parse_date(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)

async def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int, limit: int = 1500):
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit, "startTime": start_ms, "endTime": end_ms}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def fetch_series(symbol: str, start: str, end: str, outdir: str):
    os.makedirs(outdir, exist_ok=True)
    # 1) Klines 1m
    start_dt = parse_date(start)
    end_dt = parse_date(end)
    start_ms = to_ms(start_dt)
    end_ms = to_ms(end_dt)

    rows = []
    window_ms = 1000 * 60 * 60 * 24 * 3  # 3 giorni per pagina
    cur = start_ms
    while cur < end_ms:
        nxt = min(end_ms, cur + window_ms)
        data = await fetch_klines(symbol, "1m", cur, nxt)
        rows.extend(data)
        if data:
            cur = int(data[-1][0]) + 60_000
        else:
            cur = nxt
        await asyncio.sleep(0.2)

    # Write klines csv
    kpath = os.path.join(outdir, f"binance_klines_{symbol}_1m.csv")
    with open(kpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ts","open","high","low","close","volume","taker_buy_base"])
        for k in rows:
            w.writerow([k[0], k[1], k[2], k[3], k[4], k[5], k[9]])

    # 2) Funding history
    url_f = f"{BINANCE_FAPI_BASE}/fapi/v1/fundingRate"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url_f, params={"symbol": symbol, "limit": 1000, "startTime": start_ms, "endTime": end_ms})
        r.raise_for_status()
        frows = r.json()
    fpath = os.path.join(outdir, f"binance_funding_{symbol}.csv")
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ts","funding_rate"])
        for x in frows:
            w.writerow([x["fundingTime"], x["fundingRate"]])

    # 3) OI 1h (ultimo mese per volta; qui preleviamo 7d per compatibilità con score)
    url_oi = f"{BINANCE_FAPI_BASE}/futures/data/openInterestHist"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url_oi, params={"symbol": symbol, "period": "1h", "limit": 168})
        r.raise_for_status()
        oij = r.json()
    opath = os.path.join(outdir, f"binance_oi_hist_{symbol}_1h.csv")
    with open(opath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ts","open_interest"])
        for x in oij:
            w.writerow([x["timestamp"], x["sumOpenInterest"]])

    print("Saved:", kpath, fpath, opath)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="ETHUSDT")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out", default="data")
    args = ap.parse_args()

    import asyncio
    asyncio.run(fetch_series(args.symbol, args.start, args.end, args.out))

if __name__ == "__main__":
    main()
