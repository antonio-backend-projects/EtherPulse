
"""
backtest/run.py
Esegue un backtest semplice usando l'engine live per la decisione.
"""
import argparse, os, yaml, pandas as pd, numpy as np
from datetime import datetime
from eth_signal_kit.engine import compute_score, BearWeights, BullWeights
from eth_signal_kit.engine import SignalInputs
from backtest.features import load_klines_csv, resample_to, enrich_features, load_funding_csv, load_oi_csv
from backtest.sim import run_sim
from backtest.metrics import kpi, equity_curve

def decide_row(row, cfg):
    thresholds = cfg.get("thresholds", {})
    bear_w = BearWeights(**cfg.get("bear_weights", {}))
    bull_w = BullWeights(**cfg.get("bull_weights", {}))

    x = SignalInputs(
        funding_rate = float(row.get("funding_rate", 0.0)),
        oi_drop_pct  = float(row.get("oi_drop_pct", 0.0)),
        oi_rise_pct  = float(row.get("oi_rise_pct", 0.0)),
        liq_usd_15m  = 0.0,  # non disponibile in storico: lasciamo 0
        cvd_slope    = float(row.get("cvd_slope", 0.0)),
        broke_pivot_down = bool(row.get("broke_pivot_down", False)),
        broke_pivot_up   = bool(row.get("broke_pivot_up", False)),
        above_vwap       = bool(row.get("above_vwap", False)),
        broke_vwap_up    = bool(row.get("broke_vwap_up", False)),
        broke_vwap_down  = bool(row.get("broke_vwap_down", False)),
        vwap_distance_pct= float(row.get("vwap_distance_pct", 0.0)),
        whales_net_selling_7d = None
    )
    out = compute_score(x, bear_w, bull_w, {
        **thresholds,
        "decision.sell_score": cfg.get("decision", {}).get("sell_score", 65),
        "decision.buy_score":  cfg.get("decision", {}).get("buy_score", 65),
    })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data", help="Dir con CSV generati da ingest.py")
    ap.add_argument("--symbol", default="ETHUSDT")
    ap.add_argument("--tf", default="5T", help="pandas offset alias (5T=5m, 15T=15m)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--outdir", default="runs/ETH_5m_backtest")
    ap.add_argument("--fees_bps", type=float, default=6.0)
    ap.add_argument("--slip_bps", type=float, default=2.0)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)

    # Load data
    kpath = os.path.join(args.data, f"binance_klines_{args.symbol}_1m.csv")
    fpath = os.path.join(args.data, f"binance_funding_{args.symbol}.csv")
    opath = os.path.join(args.data, f"binance_oi_hist_{args.symbol}_1h.csv")

    df1m = load_klines_csv(kpath)
    df_tf = resample_to(df1m, args.tf)
    fund = load_funding_csv(fpath)
    oi   = load_oi_csv(opath)

    # Clip by date
    df_tf = df_tf.loc[args.start:args.end]
    fund  = fund.loc[:args.end]
    oi    = oi.loc[:args.end]

    # Enrich features (match live semantics)
    pivot_mode = cfg.get("pivot_mode", "floor")
    donchian_window = int(cfg.get("thresholds", {}).get("donchian_window", 55))
    cvd_window = int(cfg.get("thresholds", {}).get("cvd_window_min", 60))
    feats = enrich_features(df_tf, fund, oi, cvd_window, pivot_mode, donchian_window)

    # Decisions
    dec_list = []
    for ts, row in feats.iterrows():
        dec = decide_row(row, cfg)
        out = {"decision": dec["decision"], "score_bear": dec["score"]["bear"], "score_bull": dec["score"]["bull"]}
        dec_list.append(out)
    dec_df = pd.DataFrame(dec_list, index=feats.index)

    # Convert to side for sim
    def side_from_dec(row):
        if row["decision"] == "BUY":
            return "LONG"
        elif row["decision"] == "SELL":
            return "SHORT"
        return None
    feats["side"] = dec_df.apply(side_from_dec, axis=1)

    # Simulate
    trades = run_sim(feats, "side", fees_bps=args.fees_bps, slip_bps=args.slip_bps)
    eq = equity_curve(trades)

    trades_path = os.path.join(args.outdir, "trades.csv")
    eq_path = os.path.join(args.outdir, "equity_curve.csv")
    report_path = os.path.join(args.outdir, "report.json")

    trades.to_csv(trades_path, index=False)
    eq.to_csv(eq_path)
    import json
    with open(report_path, "w") as f:
        json.dump(kpi(trades), f, indent=2)

    print("Saved:", trades_path, eq_path, report_path)

if __name__ == "__main__":
    main()
