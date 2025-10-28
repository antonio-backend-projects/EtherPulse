from __future__ import annotations
import asyncio, os, json, argparse, time, yaml, sys
from typing import Dict, Any
import httpx  # per gestire eventuali HTTPStatusError
from dotenv import load_dotenv  # carica .env

from .data_sources import binance as bapi
from .data_sources import bybit as byapi
from .data_sources import santiment as snt
from .engine import compute_score, SignalInputs, BearWeights, BullWeights

# ----------------------------
# Utilities
# ----------------------------
def log(msg: str):
    print(f"[eth-signal-kit] {msg}", file=sys.stderr, flush=True)

def load_cfg(path: str = "config.yaml") -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)

# ----------------------------
# Main
# ----------------------------
async def main():
    # carica le variabili dal .env (SANTIMENT_API_KEY, ecc.)
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
    thresholds = cfg.get("thresholds", {}) or {}
    bear_w = BearWeights(**(cfg.get("bear_weights", {}) or {}))
    bull_w = BullWeights(**(cfg.get("bull_weights", {}) or {}))

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

    # VWAP defaults
    above_vwap = False
    broke_vwap_up = False
    broke_vwap_down = False
    vwap_distance_pct = 0.0

    # ===== Exchange: BINANCE =====
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
            # usa finestra da config per ridurre rumore
            cfg_win = int(thresholds.get("cvd_window_min", 60))
            window = min(cfg_win, len(cvd_series))
            cvd_slope = (cvd_series[-1] - cvd_series[-window]) / window if window >= 2 else 0.0

            piv = cfg.get("levels", {}).get("pivot_primary", 3980.0)
            last_close = float(kl[-1][4]) if kl else 0.0
            prev_close = float(kl[-2][4]) if len(kl) >= 2 else last_close
            broke_pivot_down = (prev_close >= piv and last_close < piv)
            broke_pivot_up   = (prev_close <= piv and last_close > piv)
        except Exception as e:
            if args.debug: log(f"klines/cvd/pivot error: {type(e).__name__}: {e}")

        # --- VWAP intraday (ancorato a UTC day-start) ---
        try:
            # calcola quante candele 1m dalla mezzanotte UTC
            utc_now = int(time.time())
            utc_day_start = utc_now - (utc_now % 86400)  # 00:00:00 UTC
            minutes_since_day_start = max(1, int((utc_now - utc_day_start) / 60))
            limit_1m = min(1440, minutes_since_day_start + 1)

            kl1m = await bapi.get_klines(symbol, interval="1m", limit=limit_1m)
            num, den = 0.0, 0.0
            for k in kl1m:
                high = float(k[2]); low = float(k[3]); close = float(k[4]); vol = float(k[5])
                tp = (high + low + close) / 3.0
                num += tp * vol
                den += vol
            vwap = (num / den) if den > 0 else float('nan')

            # riusa last_close/prev_close calcolati sopra (dal timeframe scelto)
            last_close = float(kl[-1][4]) if 'kl' in locals() and kl else 0.0
            prev_close = float(kl[-2][4]) if 'kl' in locals() and len(kl) >= 2 else last_close

            if vwap == vwap:  # NaN-safe
                above_vwap = (last_close > vwap)
                broke_vwap_up = (prev_close <= vwap and last_close > vwap)
                broke_vwap_down = (prev_close >= vwap and last_close < vwap)
                vwap_distance_pct = (abs(last_close - vwap) / vwap * 100.0) if vwap != 0 else 0.0
            else:
                above_vwap = False
                broke_vwap_up = False
                broke_vwap_down = False
                vwap_distance_pct = 0.0
        except Exception as e:
            if args.debug: log(f"vwap calc error: {type(e).__name__}: {e}")
            above_vwap = False
            broke_vwap_up = False
            broke_vwap_down = False
            vwap_distance_pct = 0.0

    # ===== Exchange: BYBIT =====
    else:
        # --- Funding ---
        try:
            frj = await byapi.get_funding_history(symbol, category="linear", limit=1)
            funding_rate = float(frj.get("result", {}).get("list", [{"fundingRate": 0.0}])[-1]["fundingRate"])
        except Exception as e:
            if args.debug: log(f"bybit funding_history error: {type(e).__name__}: {e}")

        # --- Open Interest (7d hourly) ---
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

        # --- Klines Bybit per break pivot + VWAP ---
        try:
            # klines sul timeframe richiesto per determinare close e break pivot
            kl_by = await byapi.get_klines(symbol, interval=interval, category="linear", limit=max(lookback, 30))
            # struttura bybit: [start, open, high, low, close, volume, turnover]
            last_close = float(kl_by[-1][4]) if kl_by else 0.0
            prev_close = float(kl_by[-2][4]) if len(kl_by) >= 2 else last_close

            piv = cfg.get("levels", {}).get("pivot_primary", 3980.0)
            broke_pivot_down = (prev_close >= piv and last_close < piv)
            broke_pivot_up   = (prev_close <= piv and last_close > piv)

            # VWAP intraday Bybit (1m dal giorno UTC)
            utc_now = int(time.time())
            utc_day_start = utc_now - (utc_now % 86400)
            minutes_since_day_start = max(1, int((utc_now - utc_day_start) / 60))
            limit_1m = min(1440, minutes_since_day_start + 1)

            kl1m_by = await byapi.get_klines(symbol, interval="1m", category="linear", limit=limit_1m)

            num, den = 0.0, 0.0
            for k in kl1m_by:
                high = float(k[2]); low = float(k[3]); close = float(k[4]); vol = float(k[5])
                tp = (high + low + close) / 3.0
                num += tp * vol
                den += vol
            vwap = (num / den) if den > 0 else float('nan')

            if vwap == vwap:
                above_vwap = (last_close > vwap)
                broke_vwap_up = (prev_close <= vwap and last_close > vwap)
                broke_vwap_down = (prev_close >= vwap and last_close < vwap)
                vwap_distance_pct = (abs(last_close - vwap) / vwap * 100.0) if vwap != 0 else 0.0
            else:
                above_vwap = False
                broke_vwap_up = False
                broke_vwap_down = False
                vwap_distance_pct = 0.0

            # CVD proxy: Bybit kline non espone taker_buy (per WS aggiungeremo in futuro)
            cvd_slope = 0.0
        except Exception as e:
            if args.debug: log(f"bybit klines/vwap/pivot error: {type(e).__name__}: {e}")
            liq_usd = 0.0
            cvd_slope = 0.0
            broke_pivot_down = False
            broke_pivot_up   = False
            above_vwap = False
            broke_vwap_up = False
            broke_vwap_down = False
            vwap_distance_pct = 0.0

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
            # Usa 4h x ~7d ≈ 42 barre (usiamo 60 per stare larghi)
            top = await bapi.get_top_accounts_long_short_ratio(symbol, period="4h", limit=60)
            # longShortRatio > 1 -> long dominance; <1 -> short dominance
            ratios = [float(x.get("longShortRatio", 0.0)) for x in top if x.get("longShortRatio") is not None]
            if len(ratios) >= 2:
                first, last = ratios[0], ratios[-1]
                # Variazione percentuale richiesta dal config (default 8%)
                min_change = float(thresholds.get("whales_ratio_min_change_pct", 8.0))
                change_pct = ((last - first) / first * 100.0) if first > 0 else 0.0
                if abs(change_pct) >= min_change:
                    whales_net_selling = (last < first)  # True=bear, False=bull
                    if args.debug:
                        dir_str = "net_selling" if whales_net_selling else "net_buying"
                        log(f"fallback whales L/S change={change_pct:.2f}% (>= {min_change}%) -> {dir_str}")
                else:
                    whales_net_selling = None  # variazione troppo piccola: non usiamo il segnale
                    if args.debug:
                        log(f"fallback whales L/S change too small: {change_pct:.2f}% (< {min_change}%) -> no-signal")
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
        above_vwap=above_vwap,
        broke_vwap_up=broke_vwap_up,
        broke_vwap_down=broke_vwap_down,
        vwap_distance_pct=vwap_distance_pct,
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
