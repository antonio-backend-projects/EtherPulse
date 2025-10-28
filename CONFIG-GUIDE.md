# Guida completa alla configurazione — **ETH Signal Kit**

Questa guida spiega **tutte** le voci del `config.yaml`, cosa misurano i segnali, come viene deciso **BUY/SELL/NEUTRAL**, e come adattare lo strumento al tuo stile (intraday / multi‑day, conservativo / aggressivo).

---

## 1) Struttura del file di configurazione

```yaml
symbol: ETHUSDT
interval: 1m
lookback_min: 60

pivot_mode: floor   # static | floor | donchian

levels:             # fallback se i pivot dinamici falliscono
  pivot_primary: 3980.0
  pivot_secondary_low: 3860.0
  pivot_secondary_low2: 3720.0
  pivot_invalid_up: 4250.0

thresholds:
  funding_neutral_max: 0.0
  funding_bull_min: 0.0003

  oi_drop_pct: 5.0
  oi_rise_pct: 5.0

  liquidations_usd_15m: 200000000

  cvd_window_min: 60

  vwap_min_distance_pct: 0.30
  whales_ratio_min_change_pct: 8.0

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

---

## 2) Parametri globali

* **`symbol`**: contratto da analizzare (es. `ETHUSDT`).
* **`interval`**: timeframe principale per CVD, check pivot/VWAP; **non** influisce su OI (H1, 7d) né sul day‑VWAP.
* **`lookback_min`**: minuti minimi di klines sul `interval`.
* **`pivot_mode`**:

  * `static`: usa i livelli manuali in `levels`.
  * `floor`: calcola **Floor Trader Pivots** (P,R1,S1,R2,S2) dalla **daily precedente**.
  * `donchian`: pivot “mid” = media tra **HighN/LowN** su **H1** (finestra `donchian_window`).

`levels` rimane come **fallback** se un endpoint non risponde.

---

## 3) `thresholds` — Soglie & filtri

### Derivati / microstruttura

* **`funding_neutral_max`**
  Funding ≤ soglia ⇒ **bear** (neutral/negativo). Tipico `0.0`.
* **`funding_bull_min`**
  Funding ≥ soglia ⇒ **bull** (es. `0.0003` = 0,03%).
* **`oi_drop_pct`**
  Calo OI vs **massimo 7d (H1)** ⇒ **bear**.
* **`oi_rise_pct`**
  Salita OI vs **minimo 7d (H1)** ⇒ **bull**.
* **`liquidations_usd_15m`**
  Soglia notional liquidazioni in 15m ⇒ peso **bear** (mean‑revert prudente).
* **`cvd_window_min`**
  Finestra (barre `interval`) per pendenza CVD: più grande = meno rumore.

### VWAP

* **`vwap_min_distance_pct`**
  Se |close−VWAP|/VWAP < soglia ⇒ **ignora** segnali VWAP (no‑trade band vicino alla media intraday).

### Whales (fallback)

* **`whales_ratio_min_change_pct`**
  Variazione minima del **Top Accounts Long/Short ratio** (Binance) per validare il segnale (altrimenti no‑signal).

### Affidabilità (confluenze + margini)

* **`min_bull_reasons`**, **`min_bear_reasons`**
  Numero minimo di **ragioni concordi** per accettare BUY/SELL.
* **`margin_buy_min`**, **`margin_sell_min`**
  **Vantaggio minimo** (punti) tra lato vincente e perdente per emettere BUY/SELL.

### Breakout / Donchian

* **`breakout_confirm_candles`**
  N. candele di conferma dopo break pivot.
* **`donchian_window`**
  Finestra H1 per `pivot_mode: donchian` (20 = reattivo, 55 = classico, 100 = lento/robusto).

---

## 4) `bear_weights` e `bull_weights` — Pesi dei segnali

| Segnale                                       | Lato        | Descrizione                                                    |
| --------------------------------------------- | ----------- | -------------------------------------------------------------- |
| `funding_neutral_or_neg` / `funding_positive` | bear / bull | Funding ≤ `neutral_max` (bear) o ≥ `bull_min` (bull).          |
| `oi_drop` / `oi_rise`                         | bear / bull | OI ↓ da max 7d (bear) / OI ↑ da min 7d (bull).                 |
| `liq_spike_mean_revert`                       | bear        | Liquidazioni 15m ≥ soglia ⇒ mean‑revert prudente.              |
| `cvd_negative` / `cvd_positive`               | bear / bull | Pendenza CVD < 0 (bear) o > 0 (bull).                          |
| `break_pivot_down` / `break_pivot_up`         | bear / bull | Close sotto/sopra pivot (floor/donchian/static).               |
| `whales_net_selling` / `whales_net_buying`    | bear / bull | Santiment (se presente) o fallback Top Accounts L/S.           |
| `vwap_below` / `vwap_above`                   | bear / bull | Close sotto/sopra **day‑VWAP** e **oltre** la distanza minima. |
| `break_vwap_down` / `break_vwap_up`           | bear / bull | Rottura verso giù/su del day‑VWAP.                             |

> **Suggerimento:** parti con pesi 10–20 e calibra dopo alcuni giorni di osservazione. Evita di cambiare molte cose insieme.

---

## 5) `decision` — Regole finali BUY/SELL/NEUTRAL

1. Somma dei pesi ⇒ **score_bear** e **score_bull**.
2. Controlli di **affidabilità**:

   * `min_*_reasons` (n. minimo di ragioni sul lato vincente)
   * `margin_*_min` (vantaggio minimo di punti)
   * soglia `sell_score` / `buy_score` (punteggio minimo lato vincente)
3. Se **tutti** soddisfatti ⇒ BUY o SELL; altrimenti ⇒ **NEUTRAL** (con elenco ragioni dei due lati).

---

## 6) Glossario essenziale

* **Funding**: tasso di scambio tra long e short nei perpetual. Positivo ⇒ domanda di long; negativo ⇒ domanda di short.
* **Open Interest (OI)**: contratti aperti (posizioni attive). OI↑ con prezzo↑ = ingresso di posizioni (spesso bull); OI↓ = chiusure.
* **Liquidazioni**: chiusure forzate per margin call. Spike elevati spesso precedono Mean‑Reversion.
* **CVD (Cumulative Volume Delta)**: differenza cumulata tra volumi a taker‑buy e taker‑sell. >0 bull, <0 bear.
* **VWAP intraday**: media dei prezzi pesata per volume dalla mezzanotte UTC.
* **Pivot**:

  * *Floor*: P/R1/S1/R2/S2 da Daily H/L/C‑1.
  * *Donchian*: Mid = (HighN+LowN)/2 su finestra H1.
  * *Static*: livelli manuali in `levels`.
* **Whales**: grandi operatori. Proxy da Santiment (supply distribution) o da Binance Top Accounts L/S.

---

## 7) Profili pronti

### A) Severo (swing / prudente)

```yaml
pivot_mode: floor
thresholds:
  funding_neutral_max: 0.0
  funding_bull_min: 0.0003
  oi_drop_pct: 5.0
  oi_rise_pct: 5.0
  liquidations_usd_15m: 200000000
  cvd_window_min: 60
  vwap_min_distance_pct: 0.30
  whales_ratio_min_change_pct: 8.0
  min_bull_reasons: 3
  min_bear_reasons: 3
  margin_buy_min: 25
  margin_sell_min: 25
  breakout_confirm_candles: 2
  donchian_window: 55
decision:
  sell_score: 70
  buy_score: 70
```

### B) Morbido (più reattivo / intraday)

```yaml
pivot_mode: floor
thresholds:
  funding_neutral_max: 0.0
  funding_bull_min: 0.00015
  oi_drop_pct: 3.0
  oi_rise_pct: 3.0
  liquidations_usd_15m: 120000000
  cvd_window_min: 40
  vwap_min_distance_pct: 0.15
  whales_ratio_min_change_pct: 5.0
  min_bull_reasons: 2
  min_bear_reasons: 2
  margin_buy_min: 15
  margin_sell_min: 15
  breakout_confirm_candles: 2
  donchian_window: 20
decision:
  sell_score: 60
  buy_score: 60
```

### C) Momentum / Breakout (donchian)

```yaml
pivot_mode: donchian
thresholds:
  donchian_window: 20
  funding_neutral_max: 0.0
  funding_bull_min: 0.0002
  oi_drop_pct: 3.0
  oi_rise_pct: 4.0
  liquidations_usd_15m: 150000000
  cvd_window_min: 40
  vwap_min_distance_pct: 0.20
  whales_ratio_min_change_pct: 6.0
  min_bull_reasons: 3
  min_bear_reasons: 3
  margin_buy_min: 20
  margin_sell_min: 20
  breakout_confirm_candles: 1
decision:
  sell_score: 65
  buy_score: 65
```

---

## 8) Variabili d’ambiente

```bash
# .env
SANTIMENT_API_KEY=xxxxxxxxxxxxxxxx
BYBIT_BASE=https://api.bybit.com          # o testnet
BINANCE_FAPI_BASE=https://fapi.binance.com
```

---

## 9) Esecuzione & debug

```bash
python -m eth_signal_kit.cli --symbol ETHUSDT --exchange binance --interval 1m --lookback-min 90 --with-whales true
# con debug
python -m eth_signal_kit.cli --symbol ETHUSDT --exchange binance --interval 1m --lookback-min 90 --with-whales true --debug true
```

---

## 10) Troubleshooting

* **Santiment = None**: chiave mancante/limit; entra il fallback Binance L/S.
* **400 su allForceOrders**: non passare start/end (già gestito dal codice). Usa solo `limit`.
* **Score troppo volatile**: alza `cvd_window_min`, `vwap_min_distance_pct`, soglie OI/funding.
* **Troppi NEUTRAL**: riduci `margin_*_min` e/o `sell_score`/`buy_score`, e `min_*_reasons`.

---

### Note finali

* Calibra **pochi parametri alla volta** e annota l’impatto sui segnali.
* VWAP per intraday; Floor/Donchian per contesto/direzione.
* Tratta i segnali “Whales” come **conferme**, non come trigger principali.
