# Guida completa alla configurazione — **ETH Signal Kit**

Questa guida spiega **tutte** le voci del `config.yaml`, cosa misurano i segnali, come viene deciso **BUY/SELL/NEUTRAL**, e come adattare lo strumento al tuo stile (intraday / multi-day, conservativo / aggressivo).

---

## 1) File di configurazione: struttura

```yaml
symbol: ETHUSDT
interval: 1m
lookback_min: 60

pivot_mode: floor   # static | floor | donchian

levels:             # usati solo come fallback se i pivot dinamici falliscono
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

## 2) Significato dei **parametri globali**

* `symbol`: il contratto futures/spot da analizzare (es. `ETHUSDT`).
* `interval`: timeframe principale per alcune metriche (es. CVD, pivot check); **non** cambia la finestra di OI (fissa 1h x 7d) né il VWAP intraday.
* `lookback_min`: numero minimo di minuti di dati Kline richiesti per calcoli sul timeframe impostato.
* `pivot_mode`: come calcolare i **pivot**:

  * `static`: usa i livelli dentro `levels`.
  * `floor`: **Floor Trader Pivots** (P, R1, S1, R2, S2) derivati da **H/L/C del daily precedente** (dinamico ogni giorno).
  * `donchian`: pivot “mid” = media tra **massimo e minimo** delle ultime `donchian_window` barre H1 (dinamico ad ogni ora).

`levels`: livelli **di sicurezza** usati se il calcolo dinamico fallisce (endpoint down o rate limit).

---

## 3) Sezione **thresholds** (soglie e filtri)

### Derivati e microstruttura

* `funding_neutral_max`
  Se il **funding** è **≤** questa soglia → segnale **bear (neutral/negativo)**.
  *Tipico:* `0.0` (penalizza solo funding ≤ 0).

* `funding_bull_min`
  Se il funding è **≥** questa soglia → segnale **bull (positivo)**.
  Esempi: `0.00015` = 0,015%; `0.0003` = 0,03%.

* `oi_drop_pct`
  **Riduzione di Open Interest** rispetto al **massimo degli ultimi 7 giorni (H1)**.
  Se `oi_drop_pct` misurata ≥ soglia → **bear**.
  Esempio: 5.0 = -5% dal picco 7d.

* `oi_rise_pct`
  **Aumento di Open Interest** rispetto al **minimo 7d (H1)**.
  Se ≥ soglia → **bull**.

* `liquidations_usd_15m`
  Soglia di **liquidazioni aggregate** (notional) negli ultimi 15 minuti.
  Se superata, il modello aggiunge punti **bear** come **mean-revert** (di default); puoi riconsiderarlo se fai strategie momentum pure.

* `cvd_window_min`
  **Finestra** (in barre del tuo `interval`) per la pendenza del **CVD** (delta cumulato tra aggressioni buy e sell).
  Più grande = segnale più “lento” e stabile, meno rumore.

### VWAP

* `vwap_min_distance_pct`
  Se la **distanza** tra last close e **VWAP intraday** (ancorato a UTC 00:00) è **inferiore** a questa soglia, i segnali **VWAP** vengono **ignorati** (zona “no-trade” vicino alla media intraday).

### Whales (fallback)

* `whales_ratio_min_change_pct`
  Variazione **percentuale minima** del rapporto **Top Accounts Long/Short** (Binance) richiesta per considerare valido il segnale “whales” (altrimenti “no-signal”).

### Affidabilità (confluenze + margini)

* `min_bull_reasons`, `min_bear_reasons`
  Numero minimo di **ragioni/indicatori** concordi per accettare **BUY** o **SELL**.

* `margin_buy_min`, `margin_sell_min`
  **Margine minimo** di vantaggio tra punteggio lato vincente e lato opposto per emettere **BUY/SELL**.
  Esempio: se bull=80 e bear=60, margine=20 → se `margin_buy_min`=25 ⇒ **non** basta ⇒ **NEUTRAL**.

### Breakout

* `breakout_confirm_candles`
  Numero di **candele di conferma** richieste dopo il superamento/sfondamento del pivot per validare `broke_pivot_up/down` (se implementato nel tuo engine).

### Donchian

* `donchian_window`
  Larghezza della finestra H1 per calcolare HighN/LowN (usata **solo** con `pivot_mode: donchian`).
  Più piccola = più reattivo; più grande = più lento/robusto.

---

## 4) Sezione **weights** (pesi dei segnali)

I pesi controllano **quanto incide** ogni segnale sullo score **bear** o **bull**.

* **Bear**:

  * `funding_neutral_or_neg`: funding ≤ `funding_neutral_max`
  * `oi_drop`: OI in calo ≥ `oi_drop_pct`
  * `liq_spike_mean_revert`: liquidazioni 15m ≥ soglia
  * `cvd_negative`: CVD < 0 (pendenza negativa)
  * `break_pivot_down`: close sotto pivot
  * `whales_net_selling`: whales selling (Santiment o fallback)
  * `vwap_below`: close **sotto** VWAP e **abbastanza distante** (filtrato da `vwap_min_distance_pct`)
  * `break_vwap_down`: rottura **verso il basso** del VWAP

* **Bull** (simmetrico):

  * `funding_positive`: funding ≥ `funding_bull_min`
  * `oi_rise`: OI in aumento ≥ `oi_rise_pct`
  * `cvd_positive`: CVD > 0
  * `break_pivot_up`: close sopra pivot
  * `whales_net_buying`: whales buying
  * `vwap_above`: close **sopra** VWAP e distante
  * `break_vwap_up`: rottura **verso l’alto** del VWAP

**Consiglio pratico:** parti con pesi equilibrati (10–20) e alza/abbassa dopo qualche giorno di osservazione, **non** tutti insieme.

---

## 5) Sezione **decision** (soglie finali)

* `sell_score`, `buy_score`
  Punteggio **minimo** del lato vincente per dichiarare **SELL** o **BUY** (oltre ai vincoli di confluenze e margini).
  Esempio severo: 70 / 70 — Esempio morbido: 60 / 60.

---

## 6) Cosa significano gli **indicatori** (glossario rapido)

* **Funding**: il tasso pagato tra long e short sui perpetual futures.

  > **Bull** se sostanzialmente positivo (domanda di long), **Bear** se nullo/negativo (domanda di short).

* **Open Interest (OI)**: numero di contratti aperti (posizioni attive).

  > **OI in salita** con prezzo che sale → **Bull** (nuovi long in ingresso).
  > **OI in calo** con prezzo debole → **Bear** (chiusure/derisk).

* **Liquidazioni**: valore in USD dei contratti forzatamente chiusi in un intervallo.

  > Un grande spike spesso porta a **mean-reversion** (presa profitti/assorbimento) — qui pesato lato **bear** per prudenza.

* **CVD (Cumulative Volume Delta)**: differenza cumulata tra volumi a **taker buy** e **taker sell**.

  > **CVD>0** → acquisto aggressivo prevale (**Bull**), **CVD<0** → vendita aggressiva (**Bear**).

* **VWAP (Volume-Weighted Average Price)** intraday: media dei prezzi pesata per volumi dalla mezzanotte UTC.

  > Trading **sopra** VWAP (a **distanza sufficiente**) → **Bull**, **sotto** → **Bear**.

* **Pivot**:

  * **Static**: valori manuali in `levels`.
  * **Floor**: P, R1, S1, R2, S2 dalla **daily precedente**.
  * **Donchian**: media tra HighN/LowN (H1) sull’ultima finestra.

  > **Break sopra pivot** → **Bull**, **sotto** → **Bear** (con eventuale conferma).

* **Whales**: proxy del comportamento dei grandi operatori.

  * **Santiment (opzionale)**: supply distribution per cohort selezionati.
  * **Fallback Binance**: variazione del **Top Accounts Long/Short ratio** (se scende → net selling).

---

## 7) Profili pronti (copiaincolla)

### A) **Severo** (swing / prudente)

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

### B) **Morbido** (più reattivo / intraday)

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

### C) **Momentum/Breakout** (donchian)

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

## 8) Come viene decisa l’**uscita** (BUY/SELL/NEUTRAL)

1. Calcolo **score_bear** e **score_bull** sommando i **pesi** dei segnali attivati.
2. Applico i **vincoli**:

   * n. minimo di **ragioni** per il lato vincente (`min_*_reasons`)
   * **margine minimo** tra i due punteggi (`margin_*_min`)
   * **soglia finale** (`sell_score` / `buy_score`)
3. Se **tutti** i vincoli sono soddisfatti → **BUY** o **SELL**.
   Altrimenti → **NEUTRAL** (ti mostra le ragioni dei due lati).

---

## 9) Variabili d’ambiente utili

* `.env`

  ```bash
  SANTIMENT_API_KEY=xxxxxxxxxxxxxxxx
  BYBIT_BASE=https://api.bybit.com          # o testnet
  BINANCE_FAPI_BASE=https://fapi.binance.com
  ```

---

## 10) Esecuzione & debug

* Run tipico:

  ```bash
  python -m eth_signal_kit.cli --symbol ETHUSDT --exchange binance --interval 1m --lookback-min 90 --with-whales true
  ```
* Con debug:

  ```bash
  python -m eth_signal_kit.cli ... --debug true
  ```

  Mostra: pivot calcolati, stato Santiment, fallback whales, ecc.

---

## 11) Consigli pratici

* **Non “forzare” BUY/SELL**: alza le soglie e richiedi **confluenze**. Meglio perdere un trade che entrare in 5 sbagliati.
* **VWAP**: se fai scalping/intraday, abbassa `vwap_min_distance_pct` (0.10–0.20) per farlo “pesare” di più.
* **Funding**: su ETH tende ad essere piccolo; una soglia **bull** troppo alta rischia di non attivarsi quasi mai.
* **OI**: combina con CVD. OI↑ con CVD<0 può indicare **short** che entrano aggressivi (non per forza bull).
* **Pivot mode**:

  * `floor`: semplice, robusto, si aggiorna daily — ottimo default.
  * `donchian`: più “trend-aware” — ideale per breakout/momentum.
* **Whales**: il fallback basato su **Top Accounts L/S** è un **proxy**. Trattalo come segnale **secondario**, non primario.

---

## 12) Troubleshooting rapido

* **Santiment “None”** in debug
  → chiave non valida / rate limit / metrica non disponibile. Verrà usato il **fallback**.
* **400 su `allForceOrders`**
  → evita `startTime/endTime` e usa solo `limit` (già fatto nel codice).
* **Score oscillante troppo**
  → aumenta `cvd_window_min`, alza `vwap_min_distance_pct`, rendi più alte le soglie OI/funding.
* **Troppi NEUTRAL**
  → abbassa `margin_*_min` e/o `buy_score`/`sell_score`, riduci `min_*_reasons`.

