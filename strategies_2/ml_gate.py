"""
strategies_2/ml_gate.py — pluggable ML gate for HFT strategies.

Design
------
Each HFT strategy builds a one-row feature vector in the same shape the
trainer emitted (ml.feature_engineer.build_features yields 10 columns).
The strategy hands that feature vector to MLGate.score(features=...).
MLGate proxies it to whatever predictor is bound; the default is a
NullPredictor that returns None, in which case the gate is effectively
disabled and signals flow unfiltered.
When params["ml_enabled"] is False the strategy should not even call
score() so the hot path stays cheap.

Wiring
------
The engine loop calls default_ml_gate().bind(Predictor()) once at startup
if a ready ML model exists in the DB. Strategies never need to know whether
a model is present.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Protocol

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


# Predictor protocol -----------------------------------------------------

class MLPredictorProtocol(Protocol):
    """Anything with a predict_proba(X) -> np.ndarray (sklearn / ml.Predictor).

    The gate only depends on this narrow surface so we can swap between
    a freshly-loaded joblib model, a remote inference stub, or a stub
    (NullPredictor) without touching the strategies.
    """

    def predict_proba(self, X: np.ndarray) -> np.ndarray: ...


# NullPredictor (default) -----------------------------------------------

class NullPredictor:
    """Returns probability = None, signalling 'no prediction available'.

    score() is still callable: it returns None so the strategy can branch
    on None instead of having to handle exceptions.
    """

    is_ready: bool = False

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.empty((0, 0))


# MLGate ---------------------------------------------------------------

class MLGate:
    """Score candidate signals with a binary classifier (P(win)).

    Lifecycle:
        gate = MLGate()
        gate.bind(predictor)        # optional; falls back to NullPredictor
        gate.score(features)        # returns float | None
        gate.allow(features, 0.55)  # returns (passed: bool, p: float)
    """

    def __init__(self, predictor: MLPredictorProtocol | None = None) -> None:
        self._predictor: Any = predictor or NullPredictor()
        self._lock = threading.Lock()
        self._model_version: str = "none"

    # Wiring ------------------------------------------------------------
    def bind(self, predictor: MLPredictorProtocol, model_version: str = "") -> None:
        """Attach a new predictor at runtime (engine hot-swap safe)."""
        with self._lock:
            self._predictor = predictor
            self._model_version = model_version
        log.info(
            "MLGate: bound predictor version=%s ready=%s",
            model_version or "?",
            getattr(predictor, "is_ready", True),
        )

    def unbind(self) -> None:
        """Reset to NullPredictor (e.g. on model unload)."""
        self.bind(NullPredictor(), model_version="none")

    @property
    def is_bound(self) -> bool:
        return not isinstance(self._predictor, NullPredictor)

    @property
    def model_version(self) -> str:
        return self._model_version

    # Inference ---------------------------------------------------------
    def _to_array(self, features: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(features, pd.DataFrame):
            X = features.to_numpy(dtype=np.float64, copy=False)
        else:
            X = np.asarray(features, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return X

    def score(self, features: pd.DataFrame | np.ndarray) -> float | None:
        """Return P(win) in [0, 1] for a one-row feature vector, or None if
        the gate has no bound predictor (NullPredictor / inference failure).
        """
        if isinstance(self._predictor, NullPredictor):
            return None
        try:
            X = self._to_array(features)
            with self._lock:
                proba = self._predictor.predict_proba(X)
            if proba is None or len(proba) == 0:
                return None
            # Binary classifier: probability of positive class (last col).
            p = float(proba[0, -1])
            if not np.isfinite(p):
                return None
            return min(1.0, max(0.0, p))
        except Exception as exc:
            log.warning("MLGate.score failed: %s", exc)
            return None

    def allow(
        self,
        features: pd.DataFrame | np.ndarray,
        min_prob: float,
    ) -> tuple[bool, float | None]:
        """Decide whether a candidate signal passes the gate.

        Returns
        -------
        (passed, prob)
            passed : bool — True if no predictor is bound or prob >= min_prob
            prob   : float | None — raw probability, or None if no model
        """
        prob = self.score(features)
        if prob is None:
            return True, None  # no-op gate: don't block
        return (prob >= min_prob, prob)


# Singleton accessor ----------------------------------------------------

_DEFAULT_GATE: MLGate | None = None
_DEFAULT_LOCK = threading.Lock()


def default_ml_gate() -> MLGate:
    """Lazy-built process-wide MLGate used by all strategies by default."""
    global _DEFAULT_GATE
    if _DEFAULT_GATE is None:
        with _DEFAULT_LOCK:
            if _DEFAULT_GATE is None:
                _DEFAULT_GATE = MLGate()
                log.info("MLGate: initialised unbound (NullPredictor)")
    return _DEFAULT_GATE


# Feature helpers ------------------------------------------------------

# Ordered feature names — must match what ml/feature_engineer.py emits so a
# model trained there can be served without rebuilding the trainer.
FEATURE_NAMES: tuple[str, ...] = (
    "rsi_14",
    "atr_pct",
    "vwap_dev",
    "ema_cross",
    "vol_delta",
    "body_ratio",
    "session_london",
    "session_ny",
    "session_overlap",
    "rolling_vol",
)


def build_hft_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the same 10 features used by the trainer, on the most recent
    row of df. Returns a (1, 10) DataFrame ready for MLGate.score(...).

    Falls back to NaNs (which the gate treats as a miss) if df is too short,
    rather than raising — strategies still emit signals with default
    confidence in that case so a missing-data blip doesn't break the hot loop.
    """
    out = pd.DataFrame({name: [np.nan] for name in FEATURE_NAMES})
    if df is None or len(df) < 30:
        return out

    try:
        # Reuse the trainer's logic so the live model and the trained model
        # share feature semantics.
        from ml.feature_engineer import build_features  # local import

        X, _y, names = build_features(df, target_bars=1)
        if len(X) == 0:
            return out
        latest = X[-1]
        row = {name: float(latest[i]) for i, name in enumerate(names)}
        out = pd.DataFrame([row], columns=names)
    except Exception as exc:
        log.debug("build_hft_features fallback: %s", exc)
        # Lightweight in-place fallback so the strategy never breaks.
        close = df["close"]
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
        loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100.0 - 100.0 / (1.0 + rs)).iloc[-1]

        rng = (df["high"] - df["low"]).iloc[-1]
        body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
        body_ratio = float(body / rng) if rng > 0 else 0.0

        ret_std = df["close"].pct_change().rolling(20).std()
        atr_pct = float(ret_std.iloc[-1]) if pd.notna(ret_std.iloc[-1]) else 0.0

        row = {name: np.nan for name in FEATURE_NAMES}
        row["rsi_14"] = float(rsi) if pd.notna(rsi) else np.nan
        row["body_ratio"] = body_ratio
        row["atr_pct"] = atr_pct
        out = pd.DataFrame([row], columns=FEATURE_NAMES)
    return out
