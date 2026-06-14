"""ml/predictor.py — ML prediction layer for the engine loop.

Loads trained model artifacts and produces buy/sell/hold predictions
with confidence scores. Gracefully handles missing artifacts.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from config.settings import config

log = logging.getLogger(__name__)


class Predictor:
    """Load and run inference with the latest deployed model."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._model_path: str | None = None
        self._version: str = "none"

    def _load(self) -> None:
        """Load the most recent active model from the DB."""
        try:
            from db.session import SessionLocal
            from db.models import MLModel

            db = SessionLocal()
            try:
                row = (
                    db.query(MLModel)
                    .filter(MLModel.is_active == True, MLModel.status == "ready")
                    .order_by(MLModel.id.desc())
                    .first()
                )
                if row is None or not row.artifact_path:
                    log.debug("Predictor: no active model found")
                    self._model = None
                    self._model_path = None
                    self._version = "none"
                    return

                if not os.path.exists(row.artifact_path):
                    log.error("Predictor: artifact missing: %s", row.artifact_path)
                    self._model = None
                    self._model_path = None
                    self._version = "missing"
                    return

                import joblib
                self._model = joblib.load(row.artifact_path)
                self._model_path = row.artifact_path
                self._version = f"{row.model_type.value}:{row.id}"
                log.info("Predictor: loaded model v%s (%s)", self._version, row.name)
            finally:
                db.close()
        except Exception as exc:
            log.exception("Predictor: load failed: %s", exc)
            self._model = None

    def predict(self, features: Any) -> dict | None:
        """Run inference on a feature DataFrame.

        Parameters
        ----------
        features : pd.DataFrame or np.ndarray
            Feature matrix (1 row = latest bar, or multiple for batch).

        Returns
        -------
        dict with keys: side, confidence, model_version
            or None if confidence below threshold or no model.
        """
        if self._model is None:
            self._load()
        if self._model is None:
            return None

        try:
            import numpy as np
            import pandas as pd

            if isinstance(features, pd.DataFrame):
                X = features.values
            elif isinstance(features, np.ndarray):
                X = features
            else:
                log.warning("Predictor: unexpected feature type %s", type(features))
                return None

            if len(X.shape) == 1:
                X = X.reshape(1, -1)

            # Try predict_proba first (classifier), fall back to predict
            if hasattr(self._model, "predict_proba"):
                proba = self._model.predict_proba(X)
                # Get probability of positive class (buy/up)
                confidence = float(proba[0][-1])
            elif hasattr(self._model, "decision_function"):
                decision = self._model.decision_function(X)
                # Map to [0, 1] confidence
                confidence = float(1.0 / (1.0 + np.exp(-decision[0])))
            else:
                pred = self._model.predict(X)
                confidence = 0.65  # fallback confidence when no proba available

            # Determine side from confidence
            threshold = config.ml.prediction_threshold
            if confidence < threshold:
                log.debug(
                    "Predictor: confidence %.3f below threshold %.3f",
                    confidence,
                    threshold,
                )
                return None

            side = "BUY" if confidence >= 0.5 else "SELL"

            return {
                "side": side,
                "confidence": round(confidence, 4),
                "model_version": self.current_version(),
            }
        except Exception as exc:
            log.exception("Predictor: inference failed: %s", exc)
            return None

    def current_version(self) -> str:
        """Return the loaded model version string."""
        return self._version

    @property
    def is_ready(self) -> bool:
        return self._model is not None
