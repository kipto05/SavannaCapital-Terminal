"""ml/trainer.py — model training + feature importance extraction.

Trains a scikit-learn model with TimeSeriesSplit, returns metrics dict
with feature_importance keyed by feature name, and saves artifact via
model_store.save().
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from db.session import SessionLocal
from execution.notification_service import NotificationService
from ml.feature_engineer import build_features

log = logging.getLogger(__name__)

_MODEL_CLASSES: dict[str, type] = {
    "random_forest": RandomForestClassifier,
    "gradient_boosting": GradientBoostingClassifier,
    "logistic": LogisticRegression,
}


def _default_params(model_type: str) -> dict[str, Any]:
    if model_type == "random_forest":
        return {"n_estimators": 200, "max_depth": 10, "min_samples_leaf": 5, "random_state": 42}
    if model_type == "gradient_boosting":
        return {
            "n_estimators": 150,
            "max_depth": 4,
            "learning_rate": 0.1,
            "min_samples_leaf": 5,
            "random_state": 42,
        }
    # logistic
    return {"C": 1.0, "max_iter": 1000, "random_state": 42}


def train(
    symbol: str,
    timeframe: str,
    model_type: str,
    model_name: str,
    db_session: Any,
    n_splits: int = 5,
) -> dict[str, Any]:
    """Train and persist a model.

    Parameters
    ----------
    symbol, timeframe : str
        Used to load OHLCV bars from the DB.
    model_type : str
        One of random_forest, gradient_boosting, logistic.
    model_name : str
        Human-readable name for this model instance.
    db_session : Session
        Active SQLAlchemy session.

    Returns
    -------
    dict with keys: model_id, name, model_type, accuracy, precision,
    recall, f1, feature_importance, n_samples, hyperparams,
    feature_columns, artifact_path, training_seconds.
    """
    from db.models import OHLCVBar, MLModel

    t0 = time.monotonic()

    try:  # Wrap entire function to publish failure on unhandled exception
        if model_type not in _MODEL_CLASSES:
            raise ValueError(f"Unknown model_type: {model_type}")

        # ── Load OHLCV from DB ────────────────────────────────────────
        bars = (
            db_session.query(OHLCVBar)
            .filter(OHLCVBar.symbol == symbol, OHLCVBar.timeframe == timeframe)
            .order_by(OHLCVBar.timestamp.asc())
            .all()
        )
        if not bars:
            raise ValueError(f"No OHLCV data found for {symbol}/{timeframe}")

        import pandas as pd

        rows = [
            {
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume or 0,
                "tick_volume": b.tick_volume or 0,
                "spread": b.spread or 0,
            }
            for b in bars
        ]
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime([b.timestamp for b in bars], utc=True)

        log.info("Loaded %d OHLCV bars for %s/%s", len(df), symbol, timeframe)

        # ── Build features ────────────────────────────────────────────
        X, y, feature_names = build_features(df)
        n_samples = len(X)
        log.info("Training matrix: %d samples, %d features", n_samples, len(feature_names))

        # ── TimeSeriesSplit CV ────────────────────────────────────────
        tscv = TimeSeriesSplit(n_splits=min(n_splits, max(2, n_samples // 200)))

        cls = _MODEL_CLASSES[model_type]
        params = _default_params(model_type)
        model = cls(**params)

        cv_accs = []
        for train_idx, val_idx in tscv.split(X):
            model.fit(X[train_idx], y[train_idx])
            cv_accs.append(accuracy_score(y[val_idx], model.predict(X[val_idx])))
        log.info("CV accuracy per fold: %s", [f"{a:.3f}" for a in cv_accs])

        # ── Final fit on all data ─────────────────────────────────────
        model.fit(X, y)

        # ── Metrics ───────────────────────────────────────────────────
        y_pred = model.predict(X)
        accuracy = accuracy_score(y, y_pred)
        precision = precision_score(y, y_pred, zero_division=0)
        recall = recall_score(y, y_pred, zero_division=0)
        f1 = f1_score(y, y_pred, zero_division=0)

        # ── Feature importance ────────────────────────────────────────
        fi_raw = _extract_importance(model, feature_names)
        feature_importance = dict(zip(feature_names, fi_raw))

        elapsed = round(time.monotonic() - t0, 2)

        # ── Persist artifact ──────────────────────────────────────────
        from ml.model_store import save_model

        artifact_path = save_model(model, model_name, model_type)

        # ── Persist MLModel record ────────────────────────────────────
        ml_model = MLModel(
            name=model_name,
            model_type=model_type,
            symbol=symbol,
            timeframe=timeframe,
            artifact_path=str(artifact_path),
            feature_columns=feature_names,
            hyperparams=params,
            accuracy=round(accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            n_train_samples=n_samples,
            is_active=False,
        )
        db_session.add(ml_model)
        db_session.flush()

        log.info(
            "Model trained: %s accuracy=%.3f f1=%.3f elapsed=%ss",
            model_name,
            accuracy,
            f1,
            elapsed,
        )

        # Publish success notification before returning
        try:
            with SessionLocal() as db:
                ns = NotificationService(db)
                ns.publish(
                    event_type="model_trained",
                    title=f"Model trained: {model_name}",
                    message=f"Model {model_name} trained successfully: accuracy={accuracy:.3f}, f1={f1:.3f}",
                    data={
                        "model_name": model_name,
                        "model_type": model_type,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "metrics": {
                            "accuracy": accuracy,
                            "precision": precision,
                            "recall": recall,
                            "f1": f1,
                        },
                        "artifact_path": str(artifact_path),
                        "n_samples": n_samples,
                        "training_seconds": elapsed,
                    }
                )
        except Exception as exc:
            log.exception("Failed to publish model_trained notification: %s", exc)

        return {
            "model_id": ml_model.id,
            "name": model_name,
            "model_type": model_type,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "feature_importance": feature_importance,
            "n_samples": n_samples,
            "hyperparams": params,
            "feature_columns": feature_names,
            "artifact_path": str(artifact_path),
            "training_seconds": elapsed,
        }

    except Exception as exc:
        # Publish failure notification
        try:
            with SessionLocal() as db:
                ns = NotificationService(db)
                ns.publish(
                    event_type="model_training_failed",
                    title=f"Model training failed: {model_name}",
                    message=f"Training error: {exc}",
                    data={
                        "model_name": model_name,
                        "model_type": model_type,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "error": str(exc),
                    }
                )
        except Exception as pub_exc:
            log.exception("Failed to publish model_training_failed notification: %s", pub_exc)
        raise


def _extract_importance(model: Any, feature_names: list[str]) -> list[float]:
    if hasattr(model, "feature_importances_"):
        return list(model.feature_importances_)
    if hasattr(model, "coef_"):
        coef = model.coef_
        if coef.ndim > 1:
            coef = coef[0]
        return list(np.abs(coef))
    return [0.0] * len(feature_names)