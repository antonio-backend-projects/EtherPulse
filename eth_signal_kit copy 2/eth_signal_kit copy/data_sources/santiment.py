
from __future__ import annotations
import os
import httpx
from typing import Dict, Any, Optional

SANTIMENT_API = "https://api.santiment.net/graphql"
SANTIMENT_KEY = os.getenv("SANTIMENT_API_KEY", "")

QUERY = """
{
  getMetric(metric: "amount_in_addresses") {
    timeseriesData(
      selector: { slug: "ethereum", label: "whale", threshold: "1000" }
      from: "utc_now-7d"
      to: "utc_now"
      interval: "1d"
    ){
      datetime
      value
    }
  }
}
"""

async def whales_amount_last7d() -> Optional[Dict[str, Any]]:
    """Example: number of whale addresses >= 1000 ETH label. Requires API key (free tier available)."""
    if not SANTIMENT_KEY:
        return None
    headers = {"Authorization": f"Apikey {SANTIMENT_KEY}"}
    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        r = await client.post(SANTIMENT_API, json={"query": QUERY})
        r.raise_for_status()
        return r.json()
