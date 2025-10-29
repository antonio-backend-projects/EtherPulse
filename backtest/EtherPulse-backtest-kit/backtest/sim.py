
"""
backtest/sim.py
Simulatore semplice con ordini a chiusura barra:
- Entry a close
- Stop/TP in ATR o su VWAP/Pivot
- Fee + slippage
"""
import pandas as pd
import numpy as np

def atr(df: pd.DataFrame, n:int=14) -> pd.Series:
    tr1 = (df["high"] - df["low"]).abs()
    tr2 = (df["high"] - df["close"].shift(1)).abs()
    tr3 = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def run_sim(df: pd.DataFrame,
            side_col: str,
            fees_bps: float = 6.0,
            slip_bps: float = 2.0,
            risk_per_trade: float = 0.01,
            atr_k_stop: float = 1.2,
            atr_k_tp: float = 1.8):
    df = df.copy()
    df["ATR"] = atr(df, 14)
    trades = []
    pos = None

    for ts, row in df.iterrows():
        signal = row[side_col]  # "LONG" / "SHORT" / None
        price = row["close"]

        # exit conditions if in position
        if pos is not None:
            if pos["side"] == "LONG":
                if row["low"] <= pos["stop"]:
                    exit_px = pos["stop"]
                    pnl = (exit_px - pos["entry"]) / pos["entry"]
                    pnl -= (fees_bps + slip_bps)/1e4
                    trades.append({**pos, "exit": ts, "exit_px": exit_px, "pnl": pnl})
                    pos = None
                elif row["high"] >= pos["tp"]:
                    exit_px = pos["tp"]
                    pnl = (exit_px - pos["entry"]) / pos["entry"]
                    pnl -= (fees_bps + slip_bps)/1e4
                    trades.append({**pos, "exit": ts, "exit_px": exit_px, "pnl": pnl})
                    pos = None
            else:  # SHORT
                if row["high"] >= pos["stop"]:
                    exit_px = pos["stop"]
                    pnl = (pos["entry"] - exit_px) / pos["entry"]
                    pnl -= (fees_bps + slip_bps)/1e4
                    trades.append({**pos, "exit": ts, "exit_px": exit_px, "pnl": pnl})
                    pos = None
                elif row["low"] <= pos["tp"]:
                    exit_px = pos["tp"]
                    pnl = (pos["entry"] - exit_px) / pos["entry"]
                    pnl -= (fees_bps + slip_bps)/1e4
                    trades.append({**pos, "exit": ts, "exit_px": exit_px, "pnl": pnl})
                    pos = None

        # entry at bar close (if flat)
        if pos is None and signal in ("LONG","SHORT"):
            atrv = row["ATR"]
            if pd.isna(atrv) or atrv <= 0:
                continue
            if signal == "LONG":
                entry = price * (1 + slip_bps/1e4)
                stop = entry - atrv * atr_k_stop
                tp   = entry + atrv * atr_k_tp
            else:
                entry = price * (1 - slip_bps/1e4)
                stop = entry + atrv * atr_k_stop
                tp   = entry - atrv * atr_k_tp
            pos = {"side": signal, "entry": entry, "entry_time": ts, "stop": stop, "tp": tp}

    trades_df = pd.DataFrame(trades)
    return trades_df
