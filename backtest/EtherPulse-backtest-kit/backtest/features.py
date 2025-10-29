
"""
backtest/features.py
Calcola le feature bar-by-bar (CVD, VWAP, pivot dinamici, allineamento OI/funding).
Usa CSV generati da ingest.py.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def load_klines_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.sort_values("ts").set_index("ts")
    df[["open","high","low","close","volume","taker_buy_base"]] = df[["open","high","low","close","volume","taker_buy_base"]].astype(float)
    return df

def resample_to(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    o = df["open"].resample(tf).first()
    h = df["high"].resample(tf).max()
    l = df["low"].resample(tf).min()
    c = df["close"].resample(tf).last()
    v = df["volume"].resample(tf).sum()
    tb= df["taker_buy_base"].resample(tf).sum()
    out = pd.DataFrame({"open":o,"high":h,"low":l,"close":c,"volume":v,"taker_buy_base":tb}).dropna()
    return out

def compute_cvd(df: pd.DataFrame, window:int) -> pd.Series:
    sell = df["volume"] - df["taker_buy_base"]
    delta = df["taker_buy_base"] - sell
    cvd = delta.cumsum()
    slope = (cvd - cvd.shift(window)) / window
    return slope.fillna(0.0)

def day_vwap(df: pd.DataFrame) -> pd.Series:
    # reset a ogni giorno UTC
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    day = df.index.floor("D")
    num = (tp * df["volume"]).groupby(day).cumsum()
    den = df["volume"].groupby(day).cumsum()
    vwap = num / den
    return vwap

def load_funding_csv(path: str) -> pd.DataFrame:
    f = pd.read_csv(path)
    f["ts"] = pd.to_datetime(f["ts"], unit="ms", utc=True)
    f = f.sort_values("ts").set_index("ts")
    f["funding_rate"] = f["funding_rate"].astype(float)
    return f

def load_oi_csv(path: str) -> pd.DataFrame:
    o = pd.read_csv(path)
    o["ts"] = pd.to_datetime(o["ts"], unit="ms", utc=True)
    o = o.sort_values("ts").set_index("ts")
    o["open_interest"] = o["open_interest"].astype(float)
    return o

def add_pivots_floor(df_tf: pd.DataFrame, df_daily: pd.DataFrame) -> pd.DataFrame:
    # pivots calcolati dalla daily precedente, poi ffill sul timeframe operativo
    daily = df_daily.copy()
    prev = daily.shift(1)
    P = (prev["high"] + prev["low"] + prev["close"]) / 3.0
    R1 = 2*P - prev["low"]
    S1 = 2*P - prev["high"]
    R2 = P + (prev["high"] - prev["low"])
    S2 = P - (prev["high"] - prev["low"])
    piv = pd.DataFrame({"P":P, "R1":R1, "S1":S1, "R2":R2, "S2":S2})
    piv_tf = piv.reindex(df_tf.index, method="ffill")
    return piv_tf

def add_pivots_donchian(df_h1: pd.DataFrame, window:int, index_like) -> pd.DataFrame:
    hi = df_h1["high"].rolling(window).max()
    lo = df_h1["low"].rolling(window).min()
    mid = (hi + lo) / 2.0
    piv = pd.DataFrame({"DONCH_MID": mid})
    return piv.reindex(index_like, method="ffill")

def enrich_features(df_tf: pd.DataFrame,
                    funding: pd.DataFrame,
                    oi: pd.DataFrame,
                    cvd_window:int,
                    pivot_mode:str="floor",
                    donchian_window:int=55) -> pd.DataFrame:
    out = df_tf.copy()

    # CVD slope
    out["cvd_slope"] = compute_cvd(out, cvd_window)

    # VWAP intraday
    out["vwap"] = day_vwap(out)
    out["vwap_distance_pct"] = (out["close"] - out["vwap"]).abs() / out["vwap"] * 100.0
    out["above_vwap"] = out["close"] > out["vwap"]

    # Funding align
    out["funding_rate"] = funding["funding_rate"].reindex(out.index, method="ffill").fillna(0.0)

    # OI align (1h → tf)
    oi_tf = oi["open_interest"].reindex(out.index, method="ffill").fillna(method="ffill")
    out["oi"] = oi_tf
    # rolling 7d max/min su base 1h ffillata sul tf target: approx accettabile
    # Per robustezza usiamo 7*24*60 / tf_min come finestra in bar
    tf_minutes = 5
    try:
        # infer frequency if possible
        tf_minutes = int(pd.Timedelta(out.index[1] - out.index[0]).total_seconds() // 60)
    except Exception:
        pass
    window_bars = int((7*24*60) / max(1, tf_minutes))
    out["oi_max_7d"] = oi_tf.rolling(window_bars, min_periods=1).max()
    out["oi_min_7d"] = oi_tf.rolling(window_bars, min_periods=1).min()
    out["oi_drop_pct"] = (out["oi_max_7d"] - oi_tf) / out["oi_max_7d"] * 100.0
    out["oi_rise_pct"] = (oi_tf - out["oi_min_7d"]) / out["oi_min_7d"] * 100.0

    # Pivots
    if pivot_mode == "floor":
        daily = out.resample("1D").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum","taker_buy_base":"sum"})
        piv = add_pivots_floor(out, daily)
        out = out.join(piv)
        out["broke_pivot_up"] = (out["close"].shift(1) <= out["P"]) & (out["close"] > out["P"])
        out["broke_pivot_down"] = (out["close"].shift(1) >= out["P"]) & (out["close"] < out["P"])
    elif pivot_mode == "donchian":
        h1 = out.resample("1H").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum","taker_buy_base":"sum"})
        piv = add_pivots_donchian(h1, donchian_window, out.index)
        out = out.join(piv)
        out["broke_pivot_up"] = (out["close"].shift(1) <= out["DONCH_MID"]) & (out["close"] > out["DONCH_MID"])
        out["broke_pivot_down"] = (out["close"].shift(1) >= out["DONCH_MID"]) & (out["close"] < out["DONCH_MID"])
    else:
        out["broke_pivot_up"] = False
        out["broke_pivot_down"] = False

    # VWAP cross
    out["broke_vwap_up"] = (out["close"].shift(1) <= out["vwap"]) & (out["close"] > out["vwap"])
    out["broke_vwap_down"] = (out["close"].shift(1) >= out["vwap"]) & (out["close"] < out["vwap"])

    return out
