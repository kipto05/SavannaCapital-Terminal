# ML Center — End-to-End Workflow

## 1. Overview

ML models train on historical OHLCV data → produce feature importance → can be **deployed** as
live trading strategies → emit predictions into the Live Prediction Stream.

```
Train → Feature Analysis → Deploy → Live Predictions
  ↑                                      |
  └──────────── auto-retrain ────────────┘
```

## 2. Training Flow

1. User sets **Symbol** (default: XAUUSD), **Timeframe** (default: M5), **Model Type**
   (RF / GBM / Logistic).
2. User clicks **Train Model**.
3. Backend:
   - Pulls OHLCV bars from `ohlcv_bars` table for that symbol + timeframe.
   - Calls `ml.feature_engineer.build_features(df)`.
   - Splits via `TimeSeriesSplit`.
   - Calls `ml.trainer.train(model_type, X, y)`.
   - Persists `MLModel` record to DB (accuracy, precision, recall, f1,
     `feature_columns`, `hyperparams`, artifact path).
   - Emits a **TrainingJob** record (status `running` → `complete` / `failed`).
4. Frontend:
   - Training Jobs table updates to `COMPLETED`.
   - Feature Analysis panel populates with the model's `feature_columns` + importance scores.
   - Model card appears in the Active Models grid with a **Deploy** button.

## 3. Feature Analysis

- After training, each model returns a dict of `{feature_name: importance_score}`.
- The **Feature Analysis** panel shows a ranked horizontal bar chart.
- Bars are coloured by the model's primary accent colour.
- This is per-model; a dropdown to switch between deployed models will be added later.

## 4. Deploy

1. Click **Deploy** on a model card.
2. Backend sets `MLModel.is_active = true` + registers the model instance
   in the **Strategy Registry** as a read-only `MLStrategy`.
3. The "Models Deployed" counter increments.
4. The model starts emitting predictions via `/api/ml/predictions`:
   - **Direction** (LONG / SHORT), **Symbol**, **Confidence %**, **Timeframe**,
     **Timestamp**, **Source Model**.
5. Predictions appear in the **Live Prediction Stream** table.
6. Predictions also feed into the engine for potential trade execution
   (the actual trade logic connects to the execution module; stubbed for v2).

## 5. Auto-Retrain

- Toggle in the Training panel.
- When enabled, a background loop retrains the model every **N hours** (default: 24).
- Implemented on the backend as a scheduled job (APScheduler or a simple
  thread-loop checked on engine heartbeat).
- New training overwrites the old artifact; a new version entry is created.
- If the new accuracy is worse, a warning toast appears and the model stays
  deployed with the old weights (do not downgrade silently).

## 6. Live Prediction Stream

- **v2**: Pulls from the in-memory prediction queue of active `MLModel` instances.
- **v3**: Push via WebSocket to the dashboard for sub-second updates.

## 7. Model Card Detail Modal

Opens on click; shows: Hyperparameters table, Feature importance mini-bars,
Performance metrics, **Retrain** / **Undeploy** buttons,
**View in Strategy Lab** → navigates to `/strategies?model_id={id}`.

## 8. Files

| File | Role |
|------|------|
| `db/models.py` | `MLModel` + new `TrainingJob` model (planned) |
| `dashboard/routes/ml.py` | Train / deploy / predict / feature endpoints |
| `dashboard/app.py` | Mount ML router |
| `dashboard/templates/pages/page_ml.html` | UI |
| `dashboard/static/app.js` | ML page JS (data fetching, charts) |
