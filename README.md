# EtherPulse

**EtherPulse** unisce **segnali di microstruttura** (Funding, Open Interest, Liquidazioni, CVD), **pivot dinamici** (Floor/Donchian) e **VWAP intraday** in uno **score bilanciato bull/bear** con output **BUY / SELL / NEUTRAL**.
Per default usa **solo endpoint gratuiti** (Binance + Bybit). **Opzionale**: Santiment per “whales”.

> **Obiettivo:** segnali **24–72h** con criteri di affidabilità configurabili (confluenze + margini minimi).

---

## Caratteristiche

* **Fonti gratuite**:

  * **Binance Futures** REST: funding, OI (snapshot + storico 7d H1), liquidazioni (allForceOrders), klines.
  * **Bybit V5** REST: OI, funding, klines (incluso 1m per VWAP).
* **Segnali**:

  1. Funding (bull/bear simmetrico)
  2. Open Interest (OI rise/drop)
  3. Liquidazioni 15m (mean-revert prudente)
  4. CVD (pendenza cumulativa aggressioni)
  5. Breakout **pivot dinamici**: `floor` (daily P/R/S) o `donchian` (Mid di HighN/LowN su H1)
  6. **VWAP intraday** (ancorato a UTC 00:00) con banda di esclusione
  7. (**Opzionale**) *Whales*: Santiment (supply distrib.) o **fallback** Binance Top Accounts Long/Short ratio
* **Decision engine**: pesi bull/bear separati, min. confluenze, margine minimo e soglie finali.
* **Config dinamica**: profili **Severo / Morbido / Momentum** pronti.

---

## Struttura

```
EtherPulse/
├─ eth_signal_kit/
│  ├─ cli.py                # CLI principale
│  ├─ engine.py             # scoring & decision logic
│  ├─ data_sources/
│  │  ├─ binance.py         # REST Binance (funding, OI, liquidations, klines, top L/S)
│  │  ├─ bybit.py           # REST Bybit V5 (funding, OI, klines)
│  │  └─ santiment.py       # (opz.) GraphQL
│  ├─ indicators/
│  │  └─ cvd.py             # util CVD (se necessario)
│  └─ __init__.py
├─ config.yaml              # soglie/pesi/parametri (pivot_mode, VWAP, ecc.)
├─ .env.example
├─ requirements.txt
└─ docs/
   └─ config-guide.md       # guida completa alla configurazione
```

---

## Installazione

```bash
python -m venv .venv
source .venv/bin/activate     # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env          # aggiungi se vuoi SANTIMENT_API_KEY
```

**requirements.txt** (indicativo):

```
httpx>=0.27
PyYAML>=6.0
python-dotenv>=1.0
```

---

## Configurazione rapida (`config.yaml`)

* **Pivot dinamici** (default `floor`), **VWAP**, soglie OI/Funding, CVD, whales fallback, confluenze e margini:

```yaml
symbol: ETHUSDT
interval: 1m
lookback_min: 60

pivot_mode: floor          # static | floor | donchian

levels:                     # fallback se pivot dinamici falliscono
  pivot_primary: 3980.0
  pivot_secondary_low: 3860.0
  pivot_secondary_low2: 3720.0
  pivot_invalid_up: 4250.0

thresholds:
  # Funding
  funding_neutral_max: 0.0
  funding_bull_min:    0.0003

  # Open Interest
  oi_drop_pct: 5.0
  oi_rise_pct: 5.0

  # Liquidazioni
  liquidations_usd_15m: 200000000

  # CVD
  cvd_window_min: 60

  # VWAP
  vwap_min_distance_pct: 0.30

  # Whales fallback
  whales_ratio_min_change_pct: 8.0

  # Affidabilità
  min_bull_reasons: 3
  min_bear_reasons: 3
  margin_buy_min: 25
  margin_sell_min: 25

  breakout_confirm_candles: 2
  donchian_window: 55

bear_weights:
  funding_neutral_or_neg: 10
  oi_drop: 15
  liq_spike_mean_revert: 25
  cvd_negative: 15
  break_pivot_down: 20
  whales_net_selling: 10
  vwap_below: 12
  break_vwap_down: 18

bull_weights:
  funding_positive: 10
  oi_rise: 15
  cvd_positive: 15
  break_pivot_up: 20
  whales_net_buying: 10
  vwap_above: 12
  break_vwap_up: 18

decision:
  sell_score: 70
  buy_score: 70
```

> Guida completa con definizioni e profili pronti: **`docs/config-guide.md`**.

---

## Variabili d’ambiente (`.env`)

```bash
# Opzionale — sblocca il segnale whales via Santiment GraphQL
SANTIMENT_API_KEY=xxxxxxxxxxxxxxxx

# Override API (opzionale)
BINANCE_FAPI_BASE=https://fapi.binance.com
BYBIT_BASE=https://api.bybit.com
```

---

## Uso (CLI)

```bash
# Esempio severo (binance + whales fallback + pivot floor + vwap)
python -m eth_signal_kit.cli \
  --symbol ETHUSDT \
  --exchange binance \
  --interval 1m \
  --lookback-min 90 \
  --with-whales true

# Con debug verboso
python -m eth_signal_kit.cli ... --debug true
```

**Output** (JSON): inputs normalizzati, score bull/bear, **decisione**, ragioni attive.

```json
{
  "symbol": "ETHUSDT",
  "exchange": "binance",
  "inputs": {
    "funding_rate": 4.6e-05,
    "oi_drop_pct": 1.5,
    "oi_rise_pct": 8.6,
    "liq_usd_15m": 0.0,
    "cvd_slope": -126.9,
    "broke_pivot_down": false,
    "broke_pivot_up": false,
    "above_vwap": true,
    "broke_vwap_up": false,
    "broke_vwap_down": false,
    "vwap_distance_pct": 0.16,
    "whales_net_selling_7d": true
  },
  "score": { "bear": 25, "bull": 15 },
  "decision": "NEUTRAL",
  "reasons": ["BEAR:", "cvd<0", "whales_selling", "BULL:", "oi_rise>=..."]
}
```

---

## Dati: gratis vs API key

* **Gratuiti**:

  * Binance Futures: `/fapi/v1/fundingRate`, `/fapi/v1/openInterest`, `/futures/data/openInterestHist`, `/fapi/v1/allForceOrders`, `/fapi/v1/klines`.
  * Bybit V5: `/v5/market/open-interest`, `/v5/market/history-fund-rate`, `/v5/market/kline`.
* **Con API key (free tier limitate)**:

  * **Santiment** (GraphQL): supply distribution / holders cohorts (per “whales”).
* **Non completamente free**:

  * Opzioni/greeks (gamma exposure, ecc.): richiede calcolo custom (Deribit) o provider a pagamento.

---

## Troubleshooting

* **Troppe NEUTRAL** → abbassa `margin_*_min` e/o `sell_score`/`buy_score`, riduci `min_*_reasons`.
* **Segnale troppo reattivo** → aumenta `cvd_window_min`, alza `vwap_min_distance_pct`, alza soglie OI/funding.
* **Santiment non risponde** → entra il **fallback** Binance Top Accounts L/S (richiede una variazione minima `whales_ratio_min_change_pct`).
* **400 su `allForceOrders`** → lo script usa già il fallback senza `startTime/endTime`.
* **VWAP non “pesa”** → riduci `vwap_min_distance_pct` (es. 0.10–0.20).
* **Momentum puro** → prova `pivot_mode: donchian` con `donchian_window: 20` e `breakout_confirm_candles: 1`.

---

## Avvertenza

Questa repo è a scopo **educational**. Non è consulenza finanziaria. Rischi di mercato, limiti/affidabilità delle API e infrastruttura sono a tuo carico.
