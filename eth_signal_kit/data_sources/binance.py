from __future__ import annotations

import os
from typing import Dict, Any, List, Optional
import httpx

# Permette override (es. per proxy o mirror)
BINANCE_FAPI_BASE = os.getenv("BINANCE_FAPI_BASE", "https://fapi.binance.com")

# -----------------------------
# Top Trader Long/Short Ratio
# -----------------------------
async def get_top_accounts_long_short_ratio(
    symbol: str,
    period: str = "4h",
    limit: int = 100,
    source: str = "account",  # "account" (default) oppure "position"
) -> List[Dict[str, Any]]:
    """
    Binance Futures Top Trader Long/Short Ratio (public).
    Docs:
      - Accounts:  GET /futures/data/topLongShortAccountRatio
      - Positions: GET /futures/data/topLongShortPositionRatio
    `period` examples: 5m,15m,30m,1h,2h,4h,6h,12h,1d,3d
    Ritorna lista di dict con almeno 'longShortRatio' e 'timestamp'.
    """
    ep = (
        "topLongShortAccountRatio"
        if source.lower().startswith("acc")
        else "topLongShortPositionRatio"
    )
    url = f"{BINANCE_FAPI_BASE}/futures/data/{ep}"
    params = {"symbol": symbol, "period": period, "limit": min(int(limit), 500)}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json() or []
        # tipicamente già in ordine crescente; non fa male assicurarsi
        try:
            data.sort(key=lambda x: int(x.get("timestamp", 0)))
        except Exception:
            pass
        return data  # [{ "longShortRatio": "1.23", "timestamp": 123456789, ...}, ...]

# -----------------------------
# Funding
# -----------------------------
async def get_funding_rates(symbol: str, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Recent funding rate history per symbol.
    Docs: GET /fapi/v1/fundingRate
    """
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": min(int(limit), 1000)}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_funding_info() -> List[Dict[str, Any]]:
    """
    Funding rate caps/floors (se esposti).
    Docs: GET /fapi/v1/fundingInfo
    """
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/fundingInfo"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

# -----------------------------
# Open Interest
# -----------------------------
async def get_open_interest(symbol: str) -> Dict[str, Any]:
    """
    Present OI per symbol.
    Docs: GET /fapi/v1/openInterest
    """
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/openInterest"
    params = {"symbol": symbol}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def get_open_interest_hist(
    symbol: str,
    period: str = "5m",
    limit: int = 200
) -> List[Dict[str, Any]]:
    """
    Historical OI (ultimi ~30 giorni).
    Docs: GET /futures/data/openInterestHist
    """
    url = f"{BINANCE_FAPI_BASE}/futures/data/openInterestHist"
    params = {"symbol": symbol, "period": period, "limit": min(int(limit), 500)}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json() or []
        # garantiamo ordinamento per time
        try:
            data.sort(key=lambda x: int(x.get("timestamp", 0)))
        except Exception:
            pass
        return data

# -----------------------------
# Klines (OHLCV)
# -----------------------------
async def get_klines(
    symbol: str,
    interval: str = "1m",
    limit: int = 500
) -> List[List[Any]]:
    """
    Futures klines OHLCV.
    Docs: GET /fapi/v1/klines
    Ritorna lista di barre (open-time ascendente):
      [openTime, open, high, low, close, volume, closeTime, ...]
    """
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": min(int(limit), 1500)}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json() or []
        # in genere già ordinate per openTime crescente
        try:
            data.sort(key=lambda x: int(x[0]))
        except Exception:
            pass
        return data

# -----------------------------
# Liquidations (force orders)
# -----------------------------
async def get_all_liquidations(
    symbol: Optional[str] = None,
    startTime: Optional[int] = None,
    endTime: Optional[int] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """
    All force orders (public).
    Docs: GET /fapi/v1/allForceOrders
    NOTE:
      - Per robustezza spesso è meglio NON passare start/end (evita 400 per range errati).
      - Questo SDK accetta comunque start/end se servono per analisi storiche specifiche.
    """
    url = f"{BINANCE_FAPI_BASE}/fapi/v1/allForceOrders"
    params: Dict[str, Any] = {"limit": min(int(limit), 1000)}
    if symbol:
        params["symbol"] = symbol
    if startTime:
        params["startTime"] = int(startTime)
    if endTime:
        params["endTime"] = int(endTime)
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json() or []
        # spesso già ordinati; proviamo a normalizzare in ogni caso
        try:
            data.sort(key=lambda x: int(x.get("time", 0)))
        except Exception:
            pass
        return data
