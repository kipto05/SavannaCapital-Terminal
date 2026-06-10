"""dashboard/routes/ml.py — ML Center API endpoints.

Endpoints
---------
POST   /api/ml/train               Train a new model on XAUUSD M5 (or any symbol+tf)
POST   /api/ml/deploy              Deploy / activate a trained model as a strategy
POST   /api/ml/retrain/{model_id}  Trigger auto-retrain of an existing model
GET    /api/ml/models              List all trained models (supersedes inline handler)
GET    /api/ml/predictions/{id}    Latest prediction from an active model
GET    /api/ml/feature-importance/{id}  Feature importance for a model
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from auth.router import _get_current_user
from config.settings import config
from db.models import MLModel, StrategyConfig, Trade, User
from db.session import get_db
from ml.feature_engineer import build_features
from ml.model_store import save_model, load_model
from ml.trainer import train as train_model

log = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class TrainRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "M5"
    model_type: str = Field(
        "random_forest",
        pattern="^(random_forest|gradient_boosting|logistic)$",
    )
    model_name: str = "XAUUSD-M5-Predictor"
    n_splits: int = 5


class DeployRequest(BaseModel):
    model_id: int
    param_overrides: dict[str, Any] | None = None


class RetrainRequest(BaseModel):
    model_id: int


# ── Background train helper ───────────────────────────────────────────────────

def _bg_train(
    model_id: int,
    symbol: str,
    timeframe: str,
    model_type: str,
    model_name: str,
    n_splits: int,
    db_factory: Any,  # callable returning a Session
) -> None:
    """Run training off the request thread. Updates MLModel row in place."""
    db: Session = db_factory()
    try:
        ml_model: MLModel | None = db.query(MLModel).get(model_id)
        if ml_model is None:
            log.warning("Train bg: MLModel %d not found", model_id)
            return
        ml_model.status = "training"  # type: ignore[attr-defined]
        db.add(ml_model)
        db.commit()

        result = train_model(
            symbol=symbol,
            timeframe=timeframe,
            model_type=model_type,
            model_name=model_name,
            db_session=db,
            n_splits=n_splits,
        )
        ml_model.accuracy = result["accuracy"]
        ml_model.precision = result["precision"]
        ml_model.recall = result["recall"]
        ml_model.f1 = result["f1"]
        ml_model.n_train_samples = result["n_samples"]
        ml_model.hyperparams = result["hyperparams"]
        ml_model.feature_columns = result["feature_columns"]
        ml_model.feature_importance = result["feature_importance"]
        ml_model.artifact_path = result["artifact_path"]
        ml_model.last_trained_at = datetime.now(timezone.utc)
        ml_model.status = "ready"
        db.add(ml_model)
        db.commit()
        db.refresh(ml_model)
        log.info(
            "Train complete: model_id=%d name=%s accuracy=%.3f",
            ml_model.id,
            ml_model.name,
            result["accuracy"],
        )
    except Exception as exc:
        log.exception("Train bg failed: model_id=%d: %s", model_id, exc)
        try:
            ml_model = db.query(MLModel).get(model_id)
            if ml_model is not None:
                ml_model.status = "failed"
                db.add(ml_model)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/ml/train")
def post_ml_train(
    body: TrainRequest,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Start training a new model. Returns the created MLModel row immediately;
    training runs in a background thread."""
    # Guard: need at least config.ml.min_samples bars — trainer enforces this
    # but surface a clearer error here.
    from db.models import OHLCVBar
    cnt = (
        db.query(OHLCVBar)
        .filter(OHLCVBar.symbol == body.symbol, OHLCVBar.timeframe == body.timeframe)
        .count()
    )
    min_bars = getattr(config.ml, "min_training_bars", 300)
    if cnt < min_bars:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Not enough bars for {body.symbol}/{body.timeframe}: "
                f"have {cnt}, need ≥ {min_bars}. Fetch more data first.",
            },
        )

    ml_model = MLModel(
        name=body.model_name,
        model_type=body.model_type,
        symbol=body.symbol,
        timeframe=body.timeframe,
        artifact_path="",
        feature_columns=[],
        hyperparams={},
        n_train_samples=0,
        status="pending",
    )
    db.add(ml_model)
    db.flush()
    model_id = ml_model.id

    # Launch background thread so FastAPI event loop is never blocked
    t = threading.Thread(
        target=_bg_train,
        args=(model_id, body.symbol, body.timeframe, body.model_type,
              body.model_name, body.n_splits, db.bind.connect),
        daemon=True,
    )
    t.start()

    return {
        "id": model_id,
        "name": body.model_name,
        "model_type": body.model_type,
        "symbol": body.symbol,
        "timeframe": body.timeframe,
        "status": "pending",
        "message": "Training started — poll GET /api/ml/models for status.",
    }


@router.get("/api/ml/models")
def get_ml_models(
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all ML models, most recent first."""
    models: list[MLModel] = (
        db.query(MLModel).order_by(desc(MLModel.created_at)).all()
    )
    return [m.to_dict() for m in models]


@router.post("/api/ml/deploy")
def post_ml_deploy(
    body: DeployRequest,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Activate a trained model and register it as a StrategyConfig so the
    live engine picks it up (deploy-as-strategy mechanism).

    Only one ML model can be active per (symbol, timeframe) at a time.
    The strategy is registered as ``ml_{model_id}_{model_type}``.
    """
    source: MLModel | None = db.query(MLModel).get(body.model_id)
    if source is None:
        raise HTTPException(status_code=404, detail={"error": "Model not found"})
    if source.status not in ("ready", "active"):
        raise HTTPException(
            status_code=400,
            detail={"error": f"Model status is '{source.status}', deploy requires 'ready'"},
        )

    strategy_name = f"ml_{source.id}_{source.model_type}"

    # Deactivate any existing ML strategy for the same symbol/tf first
    existing = (
        db.query(StrategyConfig)
        .filter(
            StrategyConfig.symbol == source.symbol,
            StrategyConfig.timeframe == source.timeframe,
            StrategyConfig.name.like("ml_%"),
        )
        .all()
    )
    for cfg in existing:
        cfg.is_active = False
        db.add(cfg)

    # Upsert the ML strategy entry
    cfg: StrategyConfig | None = (
        db.query(StrategyConfig)
        .filter(StrategyConfig.name == strategy_name)
        .first()
    )
    params: dict[str, Any] = (body.param_overrides or {})
    params.setdefault("model_id", source.id)
    params.setdefault("model_type", source.model_type)
    params.setdefault("artifact_path", source.artifact_path)
    params.setdefault("feature_columns", source.feature_columns or [])
    params.setdefault("prediction_threshold", float(getattr(config.ml, "prediction_threshold", 0.60)))
    params.setdefault("confidence_to_show", float(getattr(config.ai, "min_confidence_to_show", 0.7)))
    params.setdefault("cooldown_minutes", int(getattr(config.ai, "cooldown_minutes", 15)))
    params.setdefault("lookback_bars", int(getattr(config.ai, "lookback_bars", 50)))

    if cfg is None:
        cfg = StrategyConfig(
            name=strategy_name,
            label=f"ML: {source.name}",
            symbol=source.symbol,
            timeframe=source.timeframe,
            is_active=True,
            params=params,
        )
    else:
        cfg.is_active = True
        cfg.params = params

    source.is_active = True
    db.add(cfg)
    db.add(source)
    db.commit()
    db.refresh(cfg)
    db.refresh(source)

    log.info("ML model deployed: id=%d strategy=%s symbol=%s",
             source.id, strategy_name, source.symbol)
    return {
        "model_id": source.id,
        "strategy_name": strategy_name,
        "symbol": source.symbol,
        "timeframe": source.timeframe,
        "is_active": True,
        "config": cfg.to_dict(),
    }


def _run_prediction(model: MLModel, df: Any) -> dict[str, Any] | None:
    """Load artifact, build last feature row, return prediction dict."""
    if not model.artifact_path:
        return None
    art = load_model(model.artifact_path)
    if art is None:
        log.error("Prediction: artifact missing for model %s", model.id)
        return None
    try:
        X, _, feature_names = build_features(df)
    except ValueError as exc:
        log.warning("Prediction: feature build failed for model %s: %s", model.id, exc)
        return None
    if len(X) == 0:
        return None
    latest = X[-1:].astype(float)
    try:
        confidence = float(art.predict_proba(latest)[0])
    except AttributeError:
        # LogisticRegression may lack predict_proba for some configurations
        confidence = 0.5
    predicted_class = int(art.predict(latest)[0])
    threshold = float(getattr(config.ml, "prediction_threshold", 0.60))
    if confidence < threshold and predicted_class == 0:
        return None
    side = "BUY" if predicted_class == 1 else "SELL"
    return {
        "model_id": model.id,
        "model_name": model.name,
        "symbol": model.symbol,
        "timeframe": model.timeframe,
        "side": side,
        "confidence": round(confidence, 4),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/ml/predictions/{model_id}")
def get_ml_prediction(
    model_id: int,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the latest prediction for an **active** ML model (if any data is available)."""
    model: MLModel | None = db.query(MLModel).get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail={"error": "Model not found"})
    if not model.is_active:
        raise HTTPException(status_code=400, detail={"error": "Model is not active"})

    from data.repository import fetch_ohlcv
    df = fetch_ohlcv(
        symbol=model.symbol,
        timeframe=model.timeframe,
        n_bars=getattr(config.ml, "feature_window", 40),
    )
    if df is None or len(df) < 40:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Insufficient live data for {model.symbol}/{model.timeframe}"},
        )
    result = _run_prediction(model, df)
    if result is None:
        return {
            "model_id": model.id,
            "model_name": model.name,
            "status": "below_threshold",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    return result


@router.post("/api/ml/retrain/{model_id}")
def post_ml_retrain(
    model_id: int,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Trigger re-training of an existing model. Runs in background."""
    model: MLModel | None = db.query(MLModel).get(model_id)
    if model is None or not model.artifact_path:
        raise HTTPException(status_code=404, detail={"error": "Model not found"})

    # Reset to pending and fire background thread
    model.status = "pending"
    db.add(model)
    db.commit()
    db.refresh(model)

    t = threading.Thread(
        target=_bg_train,
        args=(model_id, model.symbol, model.timeframe,
              model.model_type, model.name, 5, db.bind.connect),
        daemon=True,
    )
    t.start()
    return {
        "id": model_id,
        "status": "pending",
        "message": "Retrain started.",
    }


@router.get("/api/ml/feature-importance/{model_id}")
def get_ml_feature_importance(
    model_id: int,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return feature importance sorted highest → lowest."""
    model: MLModel | None = db.query(MLModel).get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail={"error": "Model not found"})

    fi: dict[str, float] = getattr(model, "feature_importance", None) or {}
    if not fi:
        # Fall back: recompute from artifact
        art = load_model(model.artifact_path) if model.artifact_path else None
        if art is not None and hasattr(art, "feature_importances_"):
            cols = list(getattr(model, "feature_columns", []) or [])
            fi = dict(zip(cols, map(float, art.feature_importances_)))
            db.add(model)
            model.feature_importance = fi  # type: ignore[attr-defined]
            db.commit()
    ranked = sorted(fi.items(), key=lambda x: abs(x[1]), reverse=True)
    return {
        "model_id": model_id,
        "model_name": model.name,
        "features": [{"name": n, "importance": round(v, 6)} for n, v in ranked],
    }
