
# ETH Signal Kit (free endpoints first)

Unisce **più segnali** (Funding, Open Interest, Liquidazioni, CVD, breakout di livello) in **uno score unico** per ETH.  
Per default usa **solo fonti gratuite** (Binance + Bybit). **Opzionale**: Santiment/Glassnode per "whales".

## Segnali inclusi
1. **Funding** (Binance/Bybit, REST/WS)
2. **Open Interest** (Binance/Bybit, REST)
3. **Liquidazioni** (Binance allForceOrders + WS; Bybit AllLiquidations WS)
4. **CVD** (calcolato da stream `aggTrade`)
5. **Breakout livelli** (da klines)
6. (**Opzionale**) *Whales*: Supply Distribution (Santiment/Glassnode, con API key)

> Obiettivo: **segnale breve 24–72h** con score da 0 a 100.

---

## Installazione

```bash
python -m venv .venv
source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env
# (Opzionale) inserisci API key Santiment/Glassnode nello .env
```

## Uso (CLI)

```bash
python -m eth_signal_kit.cli --symbol ETHUSDT --exchange binance   --lookback-min 60 --interval 1m --with-whales false
```

Output: tabella dei **segnali atomici** e **score composito** + suggerimento (BUY/SELL/NEUTRAL).  
*(Non è consulenza finanziaria).*

## File principali
- `eth_signal_kit/cli.py` — CLI
- `eth_signal_kit/engine.py` — calcolo score & regole
- `eth_signal_kit/data_sources/*.py` — integrazioni API (Binance/Bybit/Santiment/Glassnode)
- `eth_signal_kit/indicators/cvd.py` — CVD da aggTrade
- `config.yaml` — soglie per lo score

## Dati: gratis vs. a chiave (TL;DR)
- **Gratuiti** (nessuna chiave):  
  - Binance Futures: funding (`/fapi/v1/fundingRate`), OI (`/fapi/v1/openInterest` + `/futures/data/openInterestHist`), liquidazioni (`/fapi/v1/allForceOrders`), klines (`/fapi/v1/klines`), websocket `@aggTrade`, `@markPrice`.
  - Bybit V5: OI (`/v5/market/open-interest`), funding (`/v5/market/history-fund-rate`), **WS allLiquidation**.
- **Con chiave (free tier limitate)**:  
  - Santiment GraphQL (supply distribution / labeled holders).  
  - Glassnode (supply by wallet size/cohorts).  
- **Non completamente free**:  
  - Gamma exposure/options (derivati su greeks): richiede calcolo custom da orderbook Deribit o provider a pagamento.

## Esempi di score (default)
- **Funding neutro/≤0** = +10 punti verso SELL (se prezzo laterale/giù)
- **OI in calo ≥ 3%** (vs max 7d) = +15 punti verso SELL
- **Liquidazioni short massicce** + **reclaim livello** = +25 verso SELL (mean-revert)
- **CVD < 0** su 30–60m = +15 verso SELL
- **Break < pivot** (close H1) = +20 verso SELL
- (Whales net-selling 7d) = +10 verso SELL

Soglie finali (modificabili in `config.yaml`):
- **Score ≥ 65** → bias **SELL**
- **Score ≤ 35** → bias **BUY**
- **Altrimenti** → **NEUTRAL**

## Note
- Lo script usa **solo metodi pubblici** per default; alcuni endpoint hanno limiti temporali (es. OI storico Binance max 1 mese).  
- Per CVD, la direzione dell'aggressore è dedotta dal flag `m` (buyer is maker). Se `m=True`, il **taker è il venditore** → volume negativo.

## Avvertenza
Questa repo è **educational**. Nessuna garanzia. Rischi di mercato, API e infrastruttura a tuo carico.
