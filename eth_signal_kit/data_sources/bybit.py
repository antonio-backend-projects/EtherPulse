from __future__ import annotations
import os
from typing import Dict, Any, List
import httpx

# Permette override (es. testnet: https://api-testnet.bybit.com)
BYBIT_BASE = os.getenv("BYBIT_BASE", "https://api.bybit.com")

async def get_open_interest(
    symbol: str,
    interval: str = "1h",
    category: str = "linear",
    limit: int = 50
) -> Dict[str, Any]:
    """
    Bybit OI timeseries (public endpoint).
    Docs: GET /v5/market/open-interest
    """
    url = f"{BYBIT_BASE}/v5/market/open-interest"
    params = {
        "category": category,
        "symbol": symbol,
        "intervalTime": interval,
        "limit": min(limit, 200)
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_funding_history(
    symbol: str,
    category: str = "linear",
    limit: int = 200
) -> Dict[str, Any]:
    """
    Bybit funding history (public endpoint).
    Docs: GET /v5/market/history-fund-rate
    """
    url = f"{BYBIT_BASE}/v5/market/history-fund-rate"
    params = {
        "category": category,
        "symbol": symbol,
        "limit": min(limit, 200)
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

# ---- Klines --------------------------------------------------------

INTERVAL_MAP = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720",
    "1d": "D", "1w": "W", "1M": "M",
}

async def get_klines(
    symbol: str,
    interval: str = "1m",
    category: str = "linear",
    limit: int = 200
) -> List[list]:
    """
    Bybit V5 market kline (public).
    Docs: https://bybit-exchange.github.io/docs/v5/market/kline

    Returns list of bars (ascending by time):
      [start, open, high, low, close, volume, turnover]
    """
    iv = INTERVAL_MAP.get(interval, "1")
    url = f"{BYBIT_BASE}/v5/market/kline"
    params = {
        "category": category,
        "symbol": symbol,
        "interval": iv,
        "limit": min(limit, 1000)
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        lst = data.get("result", {}).get("list", []) or []
        lst.sort(key=lambda x: int(x[0]))  # ensure ascending by timestamp
        return lst
