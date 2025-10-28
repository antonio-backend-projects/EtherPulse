from __future__ import annotations
import asyncio, os, json, argparse, time, yaml, sys
from typing import Dict, Any
import httpx  # per gestire eventuali HTTPStatusError
from dotenv import load_dotenv  # carica .env

from .data_sources import binance as bapi
from .data_sources import bybit as byapi
from .data_sources import santiment as snt
from .engine import compute_score, SignalInputs, BearWeights, BullWeights

def log(msg: str):
    print(f"[eth-signal-kit] {msg}", file=sys.stderr, flush=True)

def load_cfg(path: str = "config.yaml") -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)

async def main():
    # carica le variabili dal .env (SANTIMENT_API_KEY, endpoint override, ecc.)
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=None, help="Futures symbol, e.g., ETHUSDT")
    parser.add_argument("--interval", default=None, help="e.g., 1m,5m,15m")
    parser.add_argument("--lookback-min", type=int, default=None)
    parser.add_argument("--exchange", choices=["binance","bybit"], default="binance")
    parser.add_argument("--with-whales", type=lambda x: x.lower()=="true", default=False)
    parser.add_argument("--debug", type=lambda x: x.lower()=="true", default=False)
    args = parser.parse_args()

    cfg = load_cfg()
    symbol   = args.symbol or cfg.get("symbol", "ETHUSDT")
    interval = args.interval or cfg.get("interval", "1m")
    lookback = args.lookback_min or cfg.get("lookback_min", 60)
    thresholds = cfg.get("thresholds", {})
    bear_w = BearWeights(**cfg.get("bear_weights", {}))
    bull_w = BullWeights(**cfg.get("bull_weights", {}))

    if args.debug:
        log(f"symbol={symbol} interval={interval} lookback={lookback} exchange={args.exchange}")
        log(f"SANTIMENT_API_KEY set? {'yes' if os.getenv('SANTIMENT_API_KEY') else 'no'}")

    # --- default sicuri ---
    funding_rate = 0.0
    oi_drop_pct  = 0.0
    oi_rise_pct  = 0.0
    liq_usd      = 0.0
    cvd_slope    = 0.0
    broke_pivot_down = False
    broke_pivot_up   = False

    if args.exchange == "binance":
        # --- Funding ---
        try:
            fr = await bapi.get_funding_rates(symbol, limit=1)
            funding_rate = float(fr[0]["fundingRate"]) if fr else 0.0
        except Exception as e:
            if args.debug: log(f"funding_rates error: {type(e).__name__}: {e}")

        # --- Open Interest (7d hourly) ---
        try:
            oi_hist = await bapi.get_open_interest_hist(symbol, period="1h", limit=168)
            oi_vals = [float(x["sumOpenInterest"]) for x in oi_hist] if oi_hist else []
            if oi_vals:
                cur    = oi_vals[-1]
                peak   = max(oi_vals)
                trough = min(oi_vals)
                if peak > 0:
                    oi_drop_pct = (peak - cur) / peak * 100.0
                if trough > 0 and cur >= trough:
                    oi_rise_pct = (cur - trough) / trough * 100.0
        except Exception as e:
            if args.debug: log(f"open_interest_hist error: {type(e).__name__}: {e}")

        # --- Liquidazioni (robust fallback: senza start/end) ---
        try:
            liqs = await bapi.get_all_liquidations(symbol=symbol, limit=200)
            for L in liqs:
                price = float(L.get("avgPrice") or L.get("price", 0.0) or 0.0)
                qty   = float(L.get("executedQty") or L.get("origQty", 0.0) or 0.0)
                liq_usd += price * qty
        except httpx.HTTPStatusError:
            liq_usd = 0.0  # degrada senza crash
        except Exception as e:
            if args.debug: log(f"allForceOrders error: {type(e).__name__}: {e}")

        # --- CVD proxy + breakout pivot ---
        try:
            kl = await bapi.get_klines(symbol, interval=interval, limit=max(lookback, 30))
            taker_buy = [float(k[9]) for k in kl] if kl else []
            total     = [float(k[5]) for k in kl] if kl else []
            cvd_series, acc = [], 0.0
            for tb, tot in zip(taker_buy, total):
                delta = (tb - (tot - tb))
                acc  += delta
                cvd_series.append(acc)
            window = min(10, len(cvd_series))
            cvd_slope = (cvd_series[-1] - cvd_series[-window]) / window if window >= 2 else 0.0

            piv = cfg.get("levels", {}).get("pivot_primary", 3980.0)
            last_close = float(kl[-1][4]) if kl else 0.0
            prev_close = float(kl[-2][4]) if len(kl) >= 2 else last_close
            broke_pivot_down = (prev_close >= piv and last_close < piv)
            broke_pivot_up   = (prev_close <= piv and last_close > piv)
        except Exception as e:
            if args.debug: log(f"klines/cvd/pivot error: {type(e).__name__}: {e}")

    else:
        # --- Bybit path (public endpoints) ---
        try:
            frj = await byapi.get_funding_history(symbol, category="linear", limit=1)
            funding_rate = float(frj.get("result", {}).get("list", [{"fundingRate": 0.0}])[-1]["fundingRate"])
        except Exception as e:
            if args.debug: log(f"bybit funding_history error: {type(e).__name__}: {e}")

        try:
            oij = await byapi.get_open_interest(symbol, interval="1h", category="linear", limit=168)
            lst = oij.get("result", {}).get("list", [])
            vals = [float(x["openInterest"]) for x in lst]
            if vals:
                cur    = vals[-1]
                peak   = max(vals)
                trough = min(vals)
                if peak > 0:
                    oi_drop_pct = (peak - cur) / peak * 100.0
                if trough > 0 and cur >= trough:
                    oi_rise_pct = (cur - trough) / trough * 100.0
        except Exception as e:
            if args.debug: log(f"bybit open_interest error: {type(e).__name__}: {e}")

        # Per semplicità qui non calcoliamo cvd/pivot su Bybit
        liq_usd = 0.0
        cvd_slope = 0.0
        broke_pivot_down = False
        broke_pivot_up   = False

    # --- Whales (opzionale; richiede SANTIMENT_API_KEY e flag) ---
    whales_net_selling = None
    if args.with_whales and os.getenv("SANTIMENT_API_KEY"):
        try:
            data = await snt.whales_amount_last7d()
            if args.debug:
                log(f"santiment raw keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            ts = data.get("data", {}).get("getMetric", {}).get("timeseriesData", []) if isinstance(data, dict) else []
            if args.debug:
                log(f"santiment points: {len(ts)}  sample: {ts[:1]} ... {ts[-1:]}")
            if len(ts) >= 2:
                first = float(ts[0].get("value") or 0.0)
                last  = float(ts[-1].get("value") or 0.0)
                whales_net_selling = (last < first)
        except Exception as e:
            if args.debug: log(f"santiment whales error: {type(e).__name__}: {e}")
            whales_net_selling = None

    # Fallback "whales" se Santiment non ha dato segnale
    if whales_net_selling is None:
        try:
            # Usa 4h x 7d ≈ 42 barre (mettiamo 60 per stare larghi)
            top = await bapi.get_top_accounts_long_short_ratio(symbol, period="4h", limit=60)
            # longShortRatio > 1 -> long dominance; <1 -> short dominance
            ratios = [float(x.get("longShortRatio", 0.0)) for x in top if x.get("longShortRatio") is not None]
            if len(ratios) >= 2:
                first, last = ratios[0], ratios[-1]
                # Se la dominanza long dei top account cala sulla finestra -> net selling (bear)
                whales_net_selling = (last < first)
                if args.debug:
                    log(f"fallback whales via topAccounts L/S: first={first:.3f} last={last:.3f} -> net_selling={whales_net_selling}")
        except Exception as e:
            if args.debug: log(f"fallback whales ratio error: {type(e).__name__}: {e}")
            whales_net_selling = None


    # --- Build inputs e compute ---
    x = SignalInputs(
        funding_rate=funding_rate,
        oi_drop_pct=oi_drop_pct,
        oi_rise_pct=oi_rise_pct,
        liq_usd_15m=liq_usd,
        cvd_slope=cvd_slope,
        broke_pivot_down=broke_pivot_down,
        broke_pivot_up=broke_pivot_up,
        whales_net_selling_7d=whales_net_selling
    )
    out = compute_score(
        x, bear_w, bull_w, {
            **thresholds,
            "decision.sell_score": cfg.get("decision", {}).get("sell_score", 65),
            "decision.buy_score":  cfg.get("decision", {}).get("buy_score", 65),
        }
    )

    print(json.dumps({
        "symbol": symbol,
        "exchange": args.exchange,
        "inputs": x.__dict__,
        "score": out["score"],        # {"bear": X, "bull": Y}
        "decision": out["decision"],  # BUY / SELL / NEUTRAL
        "reasons": out["reasons"]     # motivi (lato vincente o entrambi se neutrale)
    }, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
