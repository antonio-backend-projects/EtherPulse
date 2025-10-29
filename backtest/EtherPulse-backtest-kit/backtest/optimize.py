
"""
backtest/optimize.py
Bozza per random search su pochi iperparametri chiave.
"""
import argparse, os, yaml, random, shutil, json, subprocess, sys
from copy import deepcopy

SPACE = {
    "thresholds": {
        "cvd_window_min": [30, 40, 60, 90],
        "vwap_min_distance_pct": [0.10, 0.15, 0.20, 0.30],
        "oi_drop_pct": [3.0, 4.0, 5.0, 6.0],
        "oi_rise_pct": [3.0, 4.0, 5.0, 6.0],
    },
    "decision": {
        "sell_score": [60, 65, 70],
        "buy_score":  [60, 65, 70],
    }
}

def sample(cfg):
    c = deepcopy(cfg)
    for k, vals in SPACE["thresholds"].items():
        c["thresholds"][k] = random.choice(vals)
    for k, vals in SPACE["decision"].items():
        c["decision"][k] = random.choice(vals)
    return c

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--iters", type=int, default=10)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--tf", default="5T")
    ap.add_argument("--data", default="data")
    ap.add_argument("--symbol", default="ETHUSDT")
    ap.add_argument("--outdir", default="opt_runs")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    with open(args.config, "r") as f:
        base = yaml.safe_load(f)

    best = None
    for i in range(args.iters):
        import uuid
        run_id = f"run_{i}_{uuid.uuid4().hex[:6]}"
        cfg_i = sample(base)
        cfg_path = os.path.join(args.outdir, f"{run_id}.yaml")
        with open(cfg_path, "w") as f:
            yaml.safe_dump(cfg_i, f)

        run_dir = os.path.join(args.outdir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        cmd = [
            sys.executable, "-m", "backtest.run",
            "--data", args.data,
            "--symbol", args.symbol,
            "--tf", args.tf,
            "--config", cfg_path,
            "--start", args.start,
            "--end", args.end,
            "--outdir", run_dir
        ]
        subprocess.run(cmd, check=True)

        with open(os.path.join(run_dir, "report.json")) as f:
            rep = json.load(f)
        score = rep.get("pf", 0.0) - abs(rep.get("max_dd", 0.0))  # semplice obiettivo
        if best is None or score > best[0]:
            best = (score, run_id, rep)

    if best:
        print("Best:", best[1], best[2])
    else:
        print("No successful runs.")

if __name__ == "__main__":
    main()
