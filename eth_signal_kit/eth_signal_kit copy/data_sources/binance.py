
from __future__ import annotations

import os
import time
from typing import Dict, Any, List, Optional
import httpx

BINANCE_FAPI_BASE = os.getenv("BINANCE_FAPI_BASE", "https://fapi.binance.com")

async def get_top_accounts_long_short_ratio(symbol: str, period: str = "4h", limit: int = 100) -> list[dict]:
    """
    Binance Futures Top Trader Accounts Long/Short Position Ratio (public).
    Docs: GET /futures/data/topLongShortPositionRatio
    period examples: 5m,15m,30m,1h,2h,4h,6h,12h,1d,3d
    """
    url = f"{BINANCE_FAPI_BASE}/futures/data/topLongShortPositionRatio"
    params = {"symbol": symbol, "period": period, "limit": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()  # list of { "longShortRatio": "1.2345", "timestamp": 123456789, ... }

async def get_funding_rates(symbol: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Return recent funding rate history for a symbol."""
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_funding_info() -> List[Dict[str, Any]]:
    """Funding rate caps/floors, if any."""
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/fundingInfo"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

async def get_open_interest(symbol: str) -> Dict[str, Any]:
    """Present OI for a symbol."""
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/openInterest"
    params = {"symbol": symbol}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_open_interest_hist(symbol: str, period: str = "5m", limit: int = 200) -> List[Dict[str, Any]]:
    """Historical OI (last 1 month available)."""
    url = f"{BINANCE_FAPI_BASE}/futures/data/openInterestHist"
    params = {"symbol": symbol, "period": period, "limit": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_klines(symbol: str, interval: str = "1m", limit: int = 500) -> List[List[Any]]:
    """Klines OHLCV."""
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_all_liquidations(symbol: Optional[str] = None, startTime: Optional[int] = None, endTime: Optional[int] = None, limit: int = 1000) -> List[Dict[str, Any]]:
    """All force orders (market-wide)."""
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/allForceOrders"
    params = {"limit": limit}
    if symbol: params["symbol"] = symbol
    if startTime: params["startTime"] = startTime
    if endTime: params["endTime"] = endTime
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()
