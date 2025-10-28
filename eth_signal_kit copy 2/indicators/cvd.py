
from __future__ import annotations
import pandas as pd
from typing import List, Dict, Any

def cvd_from_aggtrades(agg_trades: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Compute a simple CVD from a list of aggregate trades.
    For Binance aggTrade payload, flag 'm' == True means buyer is maker (taker is seller).
    We'll treat taker-buy volume as positive, taker-sell as negative.
    Expected keys per trade: {'T': time, 'q': qty, 'm': isBuyerMaker}
    """
    rows = []
    for t in agg_trades:
        qty = float(t.get("q"))
        # taker side: if buyer is maker -> taker is seller => negative
        side = -1.0 if t.get("m") else 1.0
        rows.append({"time": int(t.get("T")), "vol": side * qty})
    df = pd.DataFrame(rows).sort_values("time")
    df["cvd"] = df["vol"].cumsum()
    return df
