from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class BearWeights:
    funding_neutral_or_neg: int = 10
    oi_drop: int = 15
    liq_spike_mean_revert: int = 25
    cvd_negative: int = 15
    break_pivot_down: int = 20
    whales_net_selling: int = 10

@dataclass
class BullWeights:
    funding_positive: int = 10
    oi_rise: int = 15
    cvd_positive: int = 15
    break_pivot_up: int = 20
    whales_net_buying: int = 10

@dataclass
class DecisionThresholds:
    sell_score: int = 65
    buy_score: int = 65

@dataclass
class SignalInputs:
    # derivati / microstruttura
    funding_rate: float
    oi_drop_pct: float            # % drop vs max 7d
    oi_rise_pct: float            # % rise vs min 7d (nuovo)
    liq_usd_15m: float            # totale notional liquidazioni 15m (non direzionale)
    cvd_slope: float              # >0 bull, <0 bear
    broke_pivot_down: bool
    broke_pivot_up: bool          # nuovo
    # on-chain proxy
    whales_net_selling_7d: Optional[bool] = None

def compute_score(
    x: SignalInputs,
    bear_w: BearWeights,
    bull_w: BullWeights,
    thresholds: Dict[str, float]
) -> Dict[str, Any]:
    bear_score, bull_score = 0, 0
    bear_reasons, bull_reasons = [], []

    # --- BEAR side ---
    if x.funding_rate <= thresholds.get("funding_neutral_max", 0.0001):
        bear_score += bear_w.funding_neutral_or_neg
        bear_reasons.append(f"funding<=neutral ({x.funding_rate:.5f})")

    if x.oi_drop_pct >= thresholds.get("oi_drop_pct", 3.0):
        bear_score += bear_w.oi_drop
        bear_reasons.append(f"oi_drop>={x.oi_drop_pct:.1f}%")

    if x.liq_usd_15m >= thresholds.get("liquidations_usd_15m", 150_000_000):
        # spike di liquidation -> mean revert ribassista se il contesto è sotto pressione
        bear_score += bear_w.liq_spike_mean_revert
        bear_reasons.append(f"liqs_spike_15m>={x.liq_usd_15m:,.0f}$")

    if x.cvd_slope < 0:
        bear_score += bear_w.cvd_negative
        bear_reasons.append(f"cvd<0 ({x.cvd_slope:.3f})")

    if x.broke_pivot_down:
        bear_score += bear_w.break_pivot_down
        bear_reasons.append("break_pivot_down")

    if x.whales_net_selling_7d is True:
        bear_score += bear_w.whales_net_selling
        bear_reasons.append("whales_selling")

    # --- BULL side (simmetrico) ---
    if x.funding_rate >= thresholds.get("funding_bull_min", 0.0002):
        bull_score += bull_w.funding_positive
        bull_reasons.append(f"funding>=bull ({x.funding_rate:.5f})")

    if x.oi_rise_pct >= thresholds.get("oi_rise_pct", 3.0):
        bull_score += bull_w.oi_rise
        bull_reasons.append(f"oi_rise>={x.oi_rise_pct:.1f}%")

    if x.cvd_slope > 0:
        bull_score += bull_w.cvd_positive
        bull_reasons.append(f"cvd>0 ({x.cvd_slope:.3f})")

    if x.broke_pivot_up:
        bull_score += bull_w.break_pivot_up
        bull_reasons.append("break_pivot_up")

    if x.whales_net_selling_7d is False:  # implicito: net-buying
        bull_score += bull_w.whales_net_buying
        bull_reasons.append("whales_buying")

    sell_score = thresholds.get("decision.sell_score", 65)
    buy_score  = thresholds.get("decision.buy_score", 65)

    # Decisione: vince il punteggio più alto se supera la soglia dedicata
    decision = "NEUTRAL"
    reasons  = []
    score    = {"bear": bear_score, "bull": bull_score}

    if bear_score >= sell_score and bear_score >= bull_score:
        decision = "SELL"
        reasons = bear_reasons
    elif bull_score >= buy_score and bull_score > bear_score:
        decision = "BUY"
        reasons = bull_reasons
    else:
        # opzionale: mostrare entrambe le liste per debug del trader
        reasons = (["BEAR:"] + bear_reasons) + (["BULL:"] + bull_reasons)

    return {"score": score, "decision": decision, "reasons": reasons}
