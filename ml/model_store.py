"""ml/model_store.py — .joblib artifact persistence for trained models."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import joblib

log = logging.getLogger(__name__)

# Artifact root — lives inside the project so it's version-controlled
# (artifacts themselves are gitignored, path is tracked).
_ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "ml_models"


def _ensure_dir() -> Path:
    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return _ARTIFACT_DIR


def save_model(model: Any, name: str, model_type: str) -> Path:
    """Persist model as .joblib, return the path."""
    directory = _ensure_dir()
    safe_name = name.replace(" ", "_").replace("/", "_").lower()
    ts = int(time.time())
    fname = f"{safe_name}_{model_type}_{ts}.joblib"
    path = directory / fname
    joblib.dump({"model": model, "type": model_type, "name": name}, path)
    log.info("Model artifact saved: %s", path)
    return path


def load_model(path: str | Path) -> Any | None:
    """Load a persisted model. Returns None if file missing."""
    path = Path(path)
    if not path.exists():
        log.error("Model artifact not found: %s", path)
        return None
    try:
        data = joblib.load(path)
        return data["model"]
    except Exception as exc:
        log.error("Model artifact load failed (%s): %s", path, exc)
        return None
