
"""
backtest/metrics.py
KPI base per valutare la strategia.
"""
import pandas as pd
import numpy as np

def equity_curve(trades: pd.DataFrame, start_equity: float = 1.0) -> pd.DataFrame:
    eq = start_equity
    rows = []
    for _, t in trades.iterrows():
        eq *= (1.0 + t["pnl"])
        rows.append({"time": t["exit"], "equity": eq})
    if not rows:
        return pd.DataFrame(columns=["time","equity"])
    out = pd.DataFrame(rows).set_index("time").sort_index()
    return out

def kpi(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0, "win_rate": 0.0, "pf": 0.0, "avg_pnl": 0.0, "max_dd": 0.0, "sharpe": 0.0}
    wins = trades[trades["pnl"]>0]
    losses = trades[trades["pnl"]<=0]
    win_rate = len(wins)/len(trades) if len(trades)>0 else 0.0
    gross_profit = wins["pnl"].sum()
    gross_loss   = -losses["pnl"].sum()
    pf = (gross_profit / gross_loss) if gross_loss>0 else float("inf")
    avg_pnl = trades["pnl"].mean()
    # naive sharpe with daily assumption (placeholder)
    sharpe = (avg_pnl / (trades["pnl"].std() + 1e-9)) * (252 ** 0.5)
    # max drawdown from equity
    eq = equity_curve(trades)
    if eq.empty:
        mdd = 0.0
    else:
        roll_max = eq["equity"].cummax()
        drawdown = eq["equity"]/roll_max - 1.0
        mdd = float(drawdown.min())
    return {"trades": int(len(trades)), "win_rate": float(win_rate), "pf": float(pf), "avg_pnl": float(avg_pnl), "max_dd": mdd, "sharpe": float(sharpe)}
