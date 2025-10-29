# Backtest Quick Guide — EtherPulse

## Dati (gratuiti)
1. Klines 1m (Binance Futures) — contiene `takerBuyBaseAssetVolume` per CVD.
2. Funding 8h (Binance Futures).
3. Open Interest 1h (Binance Futures, fino ~1 mese per volta).

## 1) Scarica i dati (esempio 2025-06-01 → 2025-09-30)
```
python -m backtest.ingest --symbol ETHUSDT --start 2025-06-01 --end 2025-09-30 --out data/
```

## 2) Esegui il backtest su 5 minuti
```
python -m backtest.run --data data --symbol ETHUSDT --tf 5T   --config configs/strategy_severo.yaml   --start 2025-06-01 --end 2025-09-30   --outdir runs/ETH_5m_severo_JunSep
```

## 3) Report
- `runs/.../trades.csv` — elenco trade con P&L
- `runs/.../equity_curve.csv` — curva equity
- `runs/.../report.json` — KPI principali

## 4) Ottimizzazione (random search)
```
python -m backtest.optimize --config configs/strategy_severo.yaml   --iters 10 --start 2025-06-01 --end 2025-07-15 --tf 5T --data data --symbol ETHUSDT
```