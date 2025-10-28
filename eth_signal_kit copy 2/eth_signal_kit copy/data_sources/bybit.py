from __future__ import annotations
import os
import httpx
from typing import Dict, Any

BYBIT_BASE = os.getenv("BYBIT_BASE", "https://api.bybit.com")

async def get_open_interest(symbol: str, interval: str = "1h", category: str = "linear", limit: int = 50) -> Dict[str, Any]:
    """
    Bybit OI timeseries (public endpoint).
    Docs: GET /v5/market/open-interest
    """
    url = f"{BYBIT_BASE}/v5/market/open-interest"
    params = {"category": category, "symbol": symbol, "intervalTime": interval, "limit": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_funding_history(symbol: str, category: str = "linear", limit: int = 200) -> Dict[str, Any]:
    """
    Bybit funding history (public endpoint).
    Docs: GET /v5/market/history-fund-rate
    """
    url = f"{BYBIT_BASE}/v5/market/history-fund-rate"
    params = {"category": category, "symbol": symbol, "limit": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()
