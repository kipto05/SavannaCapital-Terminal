# **Dual-Pipeline ML System Implementation Plan**

## **Overview**

This document outlines the complete implementation plan for a two-pipeline ML architecture:

1. **ML Signal Generator**: High-conviction, low-frequency trade signals (target: ~1/day, 70% win rate)
2. **ML Trade Gate**: Classifier that filters all trades using backtest trade outcomes

---

## **Current State Analysis**

### **What Exists**
- `ml/trainer.py`: Trains RandomForest on OHLCV → next-bar direction (binary)
- `ml/predictor.py`: Loads active model, makes predictions, called in engine but only logs
- `dashboard/routes/ml.py` & `dashboard/v2/routes/ml.py`: Frontend ML Center APIs
- `quant/runner.py`: Persists backtest trades to `trades` table with `source="backtest"`
- `strategies/registry.py`: Strategy registration system

### **Critical Flaws**

| # | Flaw | Impact | Root Cause |
|---|------|--------|------------|
| 1 | ML predictions NOT used for trading | ML layer is dead weight | Engine calls `_phase_ml_prediction()` but never acts; no strategy created |
| 2 | Wrong training target | Model learns noise, not high-conviction moves | Target = `(close[t+1] > close[t])` |
| 3 | No ML gate | Cannot filter trades | No `_check_ml_gate()` in engine loop |
| 4 | Feature set suboptimal | Lagging indicators for M1/M5 | RSI-14, ATR-20 too slow for scalping |
| 5 | No trade feedback loop | Model never learns from outcomes | Training uses price direction, not trade PnL |
| 6 | Inconsistent frontend APIs | Two separate ML route files | Duplication; v1 real, v2 mock |

---

## **Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    ENGINE LOOP (_phase_scan)                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  For each enabled strategy:                                │
│   1. Strategy.generate_signal() → Signal                   │
│   2. ML Trade Gate (NEW) → PASS/FAIL?                     │
│      - Features: RSI, ATR%, BB pos, session, etc.         │
│      - Model: RandomForest trained on trade outcomes      │
│      - If FAIL: skip this candidate                        │
│   3. Risk Manager check                                    │
│   4. Position Sizing                                       │
│   5. Submit order                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              ML SIGNAL GENERATOR (Standalone)              │
├─────────────────────────────────────────────────────────────┤
│  Registered as Strategy: "ml_signal_generator"            │
│  - Uses highconv_signal model (H1/D1)                     │
│  - Generates 0-2 signals/day                              │
│  - Target win rate: 70%                                    │
│  - Filters: regime, volume, liquidity                     │
└─────────────────────────────────────────────────────────────┘
```

---

## **Implementation Phases**

### **Phase 1: Enhanced Feature Engineering**

**File**: `ml/feature_engineer.py`

Add new functions for high-conviction trading:

```python
def build_highconv_features(df: pd.DataFrame, lookback: int = 100) -> np.ndarray:
    """
    Build feature matrix for high-conviction signals.
    Used for H1/H4/D1 timeframes.
    """
    # 1. Regime features
    adx = calculate_adx(df, period=14)  # Trend strength
    bb_width = bollinger(df['close'], 20, 2)[2] - bollinger(df['close'], 20, 2)[1]
    regime_trending = (adx > 25).astype(int)
    
    # 2. Volume quality
    volume_zscore = (df['tick_volume'] - df['tick_volume'].rolling(20).mean()) / df['tick_volume'].rolling(20).std()
    
    # 3. Liquidity proxy (spread estimate)
    spread_proxy = (df['high'] - df['low']) / df['close']  # Range as % of price
    
    # 4. Volatility regime
    atr_val = atr(df, 14)
    atr_percent = atr_val / df['close']
    atr_percentile = (atr_percent.rolling(100).rank(pct=True) * 100).iloc[-1]
    
    # 5. Session flags (London, NY, Asia)
    session_london, session_ny, session_asia = get_session_flags(df)
    
    # 6. Day of week
    day_of_week = df.index.dayofweek  # 0=Mon, 6=Sun
    
    # 7. Multi-timeframe alignment (if higher TF provided)
    # h4_trend = get_higher_tf_alignment(df, 'H4')
    
    # 8. Momentum with smoothing
    rsi_val = rsi(df['close'], 14).iloc[-1]
    rsi_slope = (rsi(df['close'], 14).iloc[-1] - rsi(df['close'], 14).iloc[-5]) / 5
    
    macd_line, signal_line, histogram = macd(df['close'])
    macd_histogram = histogram.iloc[-1]
    macd_histogram_prev = histogram.iloc[-2]
    macd_divergence = (macd_histogram > macd_histogram_prev) != (df['close'].iloc[-1] > df['close'].iloc[-2])
    
    # 9. Support/resistance proximity
    sr_distance = distance_to_key_level(df, lookback=50)
    
    # 10. Price acceleration (second derivative)
    price_velocity = df['close'].diff(5).iloc[-1]
    price_acceleration = df['close'].diff(5).diff(5).iloc[-1]
    
    # 11. Gap detection
    recent_gap = detect_gap(df, lookback=10)
    
    # Combine into feature vector
    features = np.array([
        adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0,
        bb_width.iloc[-1] if not pd.isna(bb_width.iloc[-1]) else 0,
        volume_zscore.iloc[-1] if not pd.isna(volume_zscore.iloc[-1]) else 0,
        spread_proxy.iloc[-1] if not pd.isna(spread_proxy.iloc[-1]) else 0,
        atr_percentile if not pd.isna(atr_percentile) else 50,
        session_london.iloc[-1] if not pd.isna(session_london.iloc[-1]) else 0,
        session_ny.iloc[-1] if not pd.isna(session_ny.iloc[-1]) else 0,
        session_asia.iloc[-1] if not pd.isna(session_asia.iloc[-1]) else 0,
        day_of_week.iloc[-1] if not pd.isna(day_of_week.iloc[-1]) else 0,
        rsi_val if not pd.isna(rsi_val) else 50,
        rsi_slope if not pd.isna(rsi_slope) else 0,
        macd_histogram if not pd.isna(macd_histogram) else 0,
        macd_divergence if not pd.isna(macd_divergence) else False,
        sr_distance if not pd.isna(sr_distance) else 0,
        price_velocity if not pd.isna(price_velocity) else 0,
        price_acceleration if not pd.isna(price_acceleration) else 0,
        recent_gap if not pd.isna(recent_gap) else 0,
    ])
    
    return features.reshape(1, -1)  # Return as 2D array for sklearn

def detect_regime(df: pd.DataFrame, period: int = 14) -> str:
    """Detect market regime: 'trending', 'ranging', 'volatile'."""
    adx = calculate_adx(df, period)
    bb_width = (bollinger(df['close'], 20, 2)[2] - bollinger(df['close'], 20, 2)[1]) / df['close']
    atr_pct = atr(df, 14) / df['close']
    
    latest_adx = adx.iloc[-1]
    latest_bb_width = bb_width.iloc[-1]
    latest_atr_pct = atr_pct.iloc[-1]
    
    # Thresholds (tune these)
    if latest_adx > 25:
        return "trending"
    elif latest_atr_pct > 0.02:  # High volatility
        return "volatile"
    else:
        return "ranging"

def volume_zscore(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Volume z-score: (volume - mean) / std"""
    vol = df.get('tick_volume', pd.Series(1, index=df.index))
    return (vol - vol.rolling(period).mean()) / vol.rolling(period).std()

def get_session_flags(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return boolean series for London, NY, Asia sessions."""
    hours = df.index.hour
    # London: 8-16 GMT, NY: 13-21 GMT, Asia: 0-8 GMT
    london = hours.isin(range(8, 16))
    ny = hours.isin(range(13, 21))
    asia = hours.isin(range(0, 8))
    return london, ny, asia

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average Directional Index."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    # True Range
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    # Directional Movement
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    # Smoothed averages
    atr = tr.ewm(alpha=1/period, min_periods=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
    
    # ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/period, min_periods=period).mean()
    return adx

def distance_to_key_level(df: pd.DataFrame, lookback: int = 50) -> float:
    """Distance to nearest support/resistance (simple pivot-based)."""
    recent = df.tail(lookback)
    highs = recent['high'].nlargest(3).mean()
    lows = recent['low'].nsmallest(3).mean()
    current = df['close'].iloc[-1]
    
    # Normalize distance as % of price
    if current > (highs + lows) / 2:
        return (current - highs) / current  # Above resistance
    else:
        return (current - lows) / current  # Below support

def detect_gap(df: pd.DataFrame, lookback: int = 10) -> int:
    """Detect if there's a gap in last N bars. Returns 1 if gap, else 0."""
    closes = df['close'].tail(lookback + 1)
    gaps = (closes.diff().abs() / closes.shift(1) > 0.005)  # >0.5% gap
    return 1 if gaps.any() else 0
```

**Keep existing `build_features()` for backward compatibility.**

---

### **Phase 2: ML Signal Generator Strategy**

**New File**: `strategies/ml_signal_generator.py`

```python
"""ML Signal Generator Strategy

High-conviction signals from ML model trained on H1/H4/D1 data.
Target: 1 signal/day max, 70% win rate, longer hold times.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, Signal, Side, StrategyMeta, atr, ema
from ml.predictor import Predictor
from ml.feature_engineer import build_highconv_features, detect_regime, volume_zscore

log = logging.getLogger(__name__)


class MLSignalGenerator(BaseStrategy):
    """ML-powered high-conviction signal generator."""
    
    meta = StrategyMeta(
        name="ml_signal_generator",
        label="ML Signal Generator",
        description="High-conviction ML signals for longer-term trades. "
                    "Uses volume, regime, and liquidity filters. "
                    "Target: 1 signal/day, 70% win rate.",
        asset_class="multi",
        typical_timeframes=["H1", "H4", "D1"],
        default_symbol="XAUUSD",
    )
    
    default_params = {
        # ML confidence threshold (high = fewer signals)
        "confidence_threshold": 0.75,
        # Minimum volume z-score to consider signal
        "min_volume_zscore": 1.0,
        # Allowed market regimes: "trending", "ranging", "volatile"
        "allowed_regimes": ["trending"],
        # SL/TP multipliers based on ATR
        "sl_atr_multiplier": 2.5,
        "tp_atr_multiplier": 4.0,
        # Lookback for feature calculation
        "lookback_bars": 100,
        # Minimum ATR% to avoid low-volatility markets
        "min_atr_percent": 0.001,  # 0.1% of price
    }
    
    param_bounds = {
        "confidence_threshold": (0.60, 0.95, 0.05),
        "min_volume_zscore": (0.0, 3.0, 0.5),
        "sl_atr_multiplier": (1.5, 5.0, 0.5),
        "tp_atr_multiplier": (2.0, 8.0, 0.5),
        "lookback_bars": (50, 200, 10),
        "min_atr_percent": (0.0005, 0.005, 0.0005),
    }
    
    def __init__(self, symbol: str = "", timeframe: str = "", params: dict[str, Any] | None = None):
        super().__init__(symbol, timeframe, params)
        self._predictor = None
    
    def _get_predictor(self) -> Predictor | None:
        """Lazy-load the high-conviction predictor."""
        if self._predictor is None:
            try:
                self._predictor = Predictor()
                # Check if highconv model is available
                if not self._predictor.has_highconv_model:
                    log.warning("MLSignalGenerator: No highconv model active")
                    return None
            except Exception as e:
                log.error("MLSignalGenerator: Failed to load predictor: %s", e)
                return None
        return self._predictor
    
    def generate_signal(self, data: dict[str, pd.DataFrame]) -> Signal | None:
        """
        Generate a high-conviction signal.
        
        Steps:
        1. Check we have enough data
        2. Detect market regime, skip if not in allowed regimes
        3. Check volume quality (z-score)
        4. Check ATR% minimum
        5. Get ML prediction
        6. Check confidence threshold
        7. Compute SL/TP using ATR
        8. Return Signal or None
        """
        df = data.get(self.timeframe)
        if df is None or len(df) < self.params["lookback_bars"]:
            log.debug("MLSignalGenerator: insufficient data (%d bars)", len(df) if df is not None else 0)
            return None
        
        # Use only the last N bars needed
        df_window = df.tail(self.params["lookback_bars"])
        
        # 1. Regime filter
        regime = detect_regime(df_window)
        if regime not in self.params["allowed_regimes"]:
            log.debug("MLSignalGenerator: regime '%s' not in %s", regime, self.params["allowed_regimes"])
            return None
        
        # 2. Volume filter
        vol_zscore = volume_zscore(df_window).iloc[-1]
        if pd.isna(vol_zscore) or vol_zscore < self.params["min_volume_zscore"]:
            log.debug("MLSignalGenerator: volume z-score %.2f below threshold %.2f",
                     vol_zscore, self.params["min_volume_zscore"])
            return None
        
        # 3. ATR% filter
        atr_val = atr(df_window, 14).iloc[-1]
        atr_percent = atr_val / df_window['close'].iloc[-1]
        if atr_percent < self.params["min_atr_percent"]:
            log.debug("MLSignalGenerator: ATR%% %.4f below minimum %.4f",
                     atr_percent, self.params["min_atr_percent"])
            return None
        
        # 4. ML prediction
        predictor = self._get_predictor()
        if predictor is None:
            return None
        
        try:
            pred = predictor.predict_highconv(df_window)
        except Exception as e:
            log.error("MLSignalGenerator: prediction failed: %s", e)
            return None
        
        if pred is None:
            log.debug("MLSignalGenerator: no prediction returned")
            return None
        
        confidence = pred.get("confidence", 0.0)
        if confidence < self.params["confidence_threshold"]:
            log.debug("MLSignalGenerator: confidence %.3f below threshold %.3f",
                     confidence, self.params["confidence_threshold"])
            return None
        
        side_str = pred.get("side", "BUY")
        side = Side.BUY if side_str == "BUY" else Side.SELL
        
        # 5. Compute SL/TP
        entry = df_window['close'].iloc[-1]
        sl_mult = self.params["sl_atr_multiplier"]
        tp_mult = self.params["tp_atr_multiplier"]
        
        if side == Side.BUY:
            sl = entry - atr_val * sl_mult
            tp = entry + atr_val * tp_mult
        else:
            sl = entry + atr_val * sl_mult
            tp = entry - atr_val * tp_mult
        
        # Ensure SL/TP are valid (not too close)
        min_distance = atr_val * 0.5
        if side == Side.BUY:
            if sl >= entry - min_distance:
                sl = entry - min_distance
            if tp <= entry + min_distance:
                tp = entry + min_distance
        else:
            if sl <= entry + min_distance:
                sl = entry + min_distance
            if tp >= entry - min_distance:
                tp = entry - min_distance
        
        log.info(
            "MLSignalGenerator: %s signal %s @ %.2f (conf=%.3f, regime=%s, vol_z=%.2f)",
            self.symbol, side.value, entry, confidence, regime, vol_zscore
        )
        
        return Signal(
            side=side,
            entry=entry,
            sl=sl,
            tp=tp,
            confidence=confidence,
            tag="ml_signal_highconv",
            regime=regime,
            lot_size=0.01,  # Will be overridden by position sizer
            metadata={
                "model_version": pred.get("model_version", "unknown"),
                "regime": regime,
                "volume_zscore": float(vol_zscore),
                "atr_percent": float(atr_percent),
            }
        )
```

---

### **Phase 3: Training Pipeline for High-Conviction Model**

**Update**: `ml/trainer.py`

Add new function:

```python
def train_highconv(
    symbol: str,
    timeframe: str,
    model_type: str = "random_forest",
    hold_period: int = 4,
    atr_multiplier: float = 1.5,
    db_session: Session | None = None,
) -> dict[str, Any]:
    """
    Train a high-conviction model.
    
    Target labeling:
    - 1 (strong buy) if forward_return > atr_multiplier * ATR
    - 0 (strong sell) if forward_return < -atr_multiplier * ATR
    - Drop (exclude) bars where return is between [-threshold, +threshold]
    
    This creates an imbalanced dataset focused on high-move bars.
    """
    from ml.feature_engineer import build_highconv_features
    
    # Fetch data
    if db_session is None:
        from db.session import SessionLocal
        db = SessionLocal()
    else:
        db = db_session
    
    try:
        from data.repository import fetch_ohlcv
        df = fetch_ohlcv(symbol=symbol, timeframe=timeframe, n_bars=5000)
        if df is None or len(df) < 200:
            raise ValueError(f"Insufficient data for {symbol} {timeframe}")
        
        # Build features
        X_list = []
        y_list = []
        feature_names = None
        
        min_lookback = 100
        for i in range(min_lookback, len(df) - hold_period):
            # Feature window
            window = df.iloc[i - min_lookback:i]
            features = build_highconv_features(window)
            
            # Compute forward return and ATR at entry
            entry_price = df['close'].iloc[i]
            exit_price = df['close'].iloc[i + hold_period]
            forward_return = (exit_price - entry_price) / entry_price
            
            # ATR at entry
            atr_val = atr(df.iloc[i - 14:i], 14).iloc[-1]
            atr_threshold = atr_val * atr_multiplier / entry_price  # Normalized
            
            # Label: only include high-conviction moves
            if forward_return > atr_threshold:
                label = 1
            elif forward_return < -atr_threshold:
                label = 0
            else:
                continue  # Skip low-move bars
            
            X_list.append(features.flatten())
            y_list.append(label)
            
            if feature_names is None:
                # Generate feature names (hard-coded for now)
                feature_names = [
                    "adx", "bb_width", "volume_zscore", "spread_proxy",
                    "atr_percentile", "session_london", "session_ny", "session_asia",
                    "day_of_week", "rsi", "rsi_slope", "macd_histogram",
                    "macd_divergence", "sr_distance", "price_velocity",
                    "price_acceleration", "recent_gap"
                ]
        
        if len(X_list) < 100:
            raise ValueError(f"Only {len(X_list)} samples after filtering. Need at least 100.")
        
        X = np.array(X_list)
        y = np.array(y_list)
        
        log.info("train_highconv: %s %s - %d samples (%.1f%% positive)",
                 symbol, timeframe, len(X), y.mean() * 100)
        
        # Train/test split
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Model
        if model_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=20,
                class_weight='balanced',  # Handle imbalance
                random_state=42,
                n_jobs=-1,
            )
        elif model_type == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42,
            )
        else:
            from sklearn.linear_model import LogisticRegression
            model = LogisticRegression(
                class_weight='balanced',
                max_iter=1000,
                random_state=42,
            )
        
        # Train
        model.fit(X_train, y_train)
        
        # Metrics
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        y_pred = model.predict(X_test)
        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        }
        
        # Feature importance
        if hasattr(model, 'feature_importances_'):
            feature_importance = dict(zip(feature_names, model.feature_importances_.tolist()))
        else:
            feature_importance = {}
        
        # Save artifact
        from ml.model_store import save_model
        artifact_path = save_model(model, symbol, timeframe, model_type)
        
        return {
            "model": model,
            "metrics": metrics,
            "feature_columns": feature_names,
            "feature_importance": feature_importance,
            "artifact_path": artifact_path,
            "n_samples": len(X),
            "n_positive": int(y.sum()),
            "hyperparams": model.get_params(),
        }
        
    finally:
        if db_session is None:
            db.close()
```

---

### **Phase 4: Predictor Extension**

**Update**: `ml/predictor.py`

```python
class Predictor:
    """Load and run inference with the latest deployed model."""
    
    def __init__(self) -> None:
        self._model: Any | None = None
        self._model_path: str | None = None
        self._version: str = "none"
        self._model_type: str | None = None
    
    def _load(self, model_type: str | None = None) -> None:
        """Load the most recent active model from the DB.
        
        Parameters
        ----------
        model_type : str | None
            Filter by model_type. If None, loads any active model.
        """
        try:
            from db.session import SessionLocal
            from db.models import MLModel
            
            db = SessionLocal()
            try:
                query = db.query(MLModel).filter(
                    MLModel.is_active == True,
                    MLModel.status == "ready"
                )
                if model_type:
                    query = query.filter(MLModel.model_type == model_type)
                row = query.order_by(MLModel.id.desc()).first()
                
                if row is None or not row.artifact_path:
                    log.debug("Predictor: no active model found (type=%s)", model_type)
                    self._model = None
                    self._model_path = None
                    self._version = "none"
                    self._model_type = None
                    return
                
                if not os.path.exists(row.artifact_path):
                    log.error("Predictor: artifact missing: %s", row.artifact_path)
                    self._model = None
                    self._model_path = None
                    self._version = "missing"
                    self._model_type = None
                    return
                
                import joblib
                self._model = joblib.load(row.artifact_path)
                self._model_path = row.artifact_path
                self._version = f"{row.model_type.value}:{row.id}"
                self._model_type = row.model_type.value if hasattr(row.model_type, 'value') else str(row.model_type)
                log.info("Predictor: loaded model v%s (%s)", self._version, row.name)
            finally:
                db.close()
        except Exception as exc:
            log.exception("Predictor: load failed: %s", exc)
            self._model = None
    
    def predict(self, features: Any) -> dict | None:
        """Run inference on a feature DataFrame (legacy price-direction model)."""
        if self._model is None or self._model_type != "random_forest":
            self._load(model_type="random_forest")
        if self._model is None:
            return None
        
        # ... existing code ...
    
    def predict_highconv(self, df: pd.DataFrame) -> dict | None:
        """Predict using high-conviction model.
        
        Returns
        -------
        dict with keys: side, confidence, model_version
            or None if confidence below threshold or no model.
        """
        if self._model is None or self._model_type != "highconv_signal":
            self._load(model_type="highconv_signal")
        if self._model is None:
            return None
        
        try:
            from ml.feature_engineer import build_highconv_features
            
            # Build features from the window
            X = build_highconv_features(df)
            
            # Predict
            if hasattr(self._model, "predict_proba"):
                proba = self._model.predict_proba(X)
                confidence = float(proba[0][1])  # Probability of positive class
            else:
                pred = self._model.predict(X)[0]
                confidence = 0.65 if pred == 1 else 0.35
            
            # Threshold check (configurable)
            from config.settings import config
            threshold = getattr(config.ml, "highconv_threshold", 0.75)
            if confidence < threshold:
                return None
            
            side = "BUY" if confidence >= 0.5 else "SELL"
            
            return {
                "side": side,
                "confidence": round(confidence, 4),
                "model_version": self.current_version(),
            }
        except Exception as exc:
            log.exception("Predictor: highconv inference failed: %s", exc)
            return None
    
    def predict_gate(self, df: pd.DataFrame, metadata: dict[str, Any] | None = None) -> dict | None:
        """Predict trade outcome using trade gate model.
        
        Parameters
        ----------
        df : pd.DataFrame
            OHLCV data window ending at entry bar
        metadata : dict
            Additional features: strategy_name, side, hour, day_of_week
        
        Returns
        -------
        dict with keys: prediction (1=win, 0=loss), confidence
        """
        if self._model is None or self._model_type != "trade_gate":
            self._load(model_type="trade_gate")
        if self._model is None:
            return None
        
        try:
            from ml.feature_engineer import build_features
            from sklearn.preprocessing import OneHotEncoder
            import pandas as pd
            
            # Build base features from OHLCV
            X_base, _, _ = build_features(df)
            features = X_base[-1:].copy()
            
            # Add metadata features (one-hot encode strategy_name, etc.)
            if metadata:
                # For now, just add hour and day_of_week as numeric
                if 'hour' in metadata:
                    features = np.hstack([features, [metadata['hour']]])
                if 'day_of_week' in metadata:
                    features = np.hstack([features, [metadata['day_of_week']]])
                # Strategy name would need one-hot encoding - skip for simplicity
            
            # Predict
            if hasattr(self._model, "predict_proba"):
                proba = self._model.predict_proba(features)
                confidence = float(proba[0][1])
                prediction = 1 if confidence >= 0.5 else 0
            else:
                prediction = int(self._model.predict(features)[0])
                confidence = 0.65 if prediction == 1 else 0.35
            
            return {
                "prediction": prediction,
                "confidence": round(confidence, 4),
                "model_version": self.current_version(),
            }
        except Exception as exc:
            log.exception("Predictor: gate inference failed: %s", exc)
            return None
    
    def current_version(self) -> str:
        """Return the loaded model version string."""
        return self._version
    
    @property
    def is_ready(self) -> bool:
        return self._model is not None
    
    @property
    def has_highconv_model(self) -> bool:
        """Check if a high-conviction model is loaded."""
        return self._model is not None and self._model_type == "highconv_signal"
```

---

### **Phase 5: Database & Config Updates**

**Update**: `db/models.py`

Add to `ModelType` enum:

```python
from sqlalchemy import Enum as SQLAEnum

class ModelType(str, enum.Enum):
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    LOGISTIC = "logistic"
    HIGHCONV_SIGNAL = "highconv_signal"  # NEW
    TRADE_GATE = "trade_gate"  # NEW
```

**Update**: `config/settings.py`

Add to MLConfig dataclass:

```python
@dataclass
class MLConfig:
    # Existing fields...
    
    # High-conviction signal generator
    signal_generator_enabled: bool = False
    highconv_threshold: float = 0.75
    
    # Trade gate
    trade_gate_enabled: bool = False
    trade_gate_threshold: float = 0.55
```

---

### **Phase 6: ML Trade Gate (Classifier)**

**New File**: `ml/gate_trainer.py`

```python
"""Trade Gate Trainer

Trains a classifier to predict trade outcomes (win/loss) using
historical backtest trades as labeled examples.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from data.repository import fetch_ohlcv
from ml.feature_engineer import build_features
from ml.model_store import save_model

log = logging.getLogger(__name__)


def train_gate(
    symbol: str,
    timeframe: str,
    model_type: str = "random_forest",
    model_name: str | None = None,
    db_session: Session | None = None,
) -> dict[str, Any]:
    """
    Train a trade gate classifier using backtest trade outcomes.
    
    Parameters
    ----------
    symbol : str
        Symbol to train on (e.g., "XAUUSD")
    timeframe : str
        Timeframe (e.g., "M15", "H1")
    model_type : str
        Model type: "random_forest", "gradient_boosting", "logistic"
    model_name : str | None
        Custom model name. If None, auto-generated.
    db_session : Session | None
        Database session. If None, creates new session.
    
    Returns
    -------
    dict with model, metrics, artifact_path, etc.
    """
    if db_session is None:
        from db.session import SessionLocal
        db = SessionLocal()
    else:
        db = db_session
    
    try:
        from db.models import Trade
        
        # Query all winning and losing backtest trades
        trades = db.query(Trade).filter(
            Trade.symbol == symbol,
            Trade.timeframe == timeframe,
            Trade.source == "backtest",
            Trade.pnl_r.isnot(None),
            Trade.opened_at.isnot(None)
        ).order_by(Trade.opened_at).all()
        
        if len(trades) < 100:
            raise ValueError(f"Only {len(trades)} trades found. Need at least 100.")
        
        log.info("train_gate: %s %s - %d trades", symbol, timeframe, len(trades))
        
        X, y = [], []
        feature_names = None
        
        for trade in trades:
            # Fetch OHLCV window ending at entry time
            df = fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                end=trade.opened_at,
                n_bars=100
            )
            if df is None or len(df) < 50:
                continue
            
            # Build features from last bar
            features, _, names = build_features(df)
            if len(features) == 0:
                continue
            
            feature_vec = features[-1].copy()
            
            # Add metadata features
            # Strategy name (one-hot would be better, but skip for now)
            # Side: 1 for BUY, 0 for SELL
            side_val = 1 if trade.side.value == "BUY" else 0
            # Hour of day
            hour = trade.opened_at.hour if trade.opened_at else 12
            # Day of week (0=Mon)
            day_of_week = trade.opened_at.weekday() if trade.opened_at else 0
            
            # Append metadata
            extra_features = np.array([side_val, hour, day_of_week])
            feature_vec = np.concatenate([feature_vec, extra_features])
            
            # Update feature names if first time
            if feature_names is None:
                base_names = names
                meta_names = ["side_buy", "hour", "day_of_week"]
                feature_names = base_names + meta_names
            
            X.append(feature_vec)
            y.append(1 if trade.pnl_r > 0 else 0)
        
        if len(X) < 50:
            raise ValueError(f"Only {len(X)} samples after alignment. Need at least 50.")
        
        X = np.array(X)
        y = np.array(y)
        
        log.info("train_gate: %d samples (%.1f%% positive)", len(X), y.mean() * 100)
        
        # Train/test split
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Model
        if model_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=20,
                class_weight='balanced',
                random_state=42,
                n_jobs=-1,
            )
        elif model_type == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42,
            )
        else:
            from sklearn.linear_model import LogisticRegression
            model = LogisticRegression(
                class_weight='balanced',
                max_iter=1000,
                random_state=42,
            )
        
        model.fit(X_train, y_train)
        
        # Metrics
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        y_pred = model.predict(X_test)
        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        }
        
        # Feature importance
        if hasattr(model, 'feature_importances_'):
            feature_importance = dict(zip(feature_names, model.feature_importances_.tolist()))
        else:
            feature_importance = {}
        
        # Save artifact
        if model_name is None:
            model_name = f"{symbol}_{timeframe}_gate"
        artifact_path = save_model(model, symbol, timeframe, model_type, model_name)
        
        # Create MLModel record
        from db.models import MLModel, ModelType
        ml_model = MLModel(
            name=model_name,
            model_type=ModelType.TRADE_GATE,
            symbol=symbol,
            timeframe=timeframe,
            status="ready",
            artifact_path=artifact_path,
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1=metrics["f1"],
            feature_columns=feature_names,
            feature_importance=feature_importance,
            hyperparams=model.get_params(),
            n_train_samples=len(X),
            last_trained_at=pd.Timestamp.now(tz="UTC"),
        )
        db.add(ml_model)
        db.commit()
        db.refresh(ml_model)
        
        log.info("train_gate: model_id=%d accuracy=%.3f", ml_model.id, metrics["accuracy"])
        
        return {
            "model": model,
            "metrics": metrics,
            "feature_columns": feature_names,
            "feature_importance": feature_importance,
            "artifact_path": artifact_path,
            "n_samples": len(X),
            "n_positive": int(y.sum()),
            "hyperparams": model.get_params(),
            "ml_model_id": ml_model.id,
        }
        
    finally:
        if db_session is None:
            db.close()
```

---

### **Phase 7: Engine Integration**

**Update**: `engine/engine_loop.py`

Add to `EngineLoop` class:

```python
def _check_trade_gate(self, symbol: str, timeframe: str, signal: Signal, df: pd.DataFrame) -> bool:
    """
    Check if trade passes ML gate.
    
    Returns True if trade should proceed, False to block.
    """
    if not self.cfg.ml.trade_gate_enabled:
        return True
    
    try:
        from ml.predictor import Predictor
        
        # Prepare metadata
        metadata = {
            "side": 1 if signal.side == Side.BUY else 0,
            "hour": df.index[-1].hour if hasattr(df.index[-1], 'hour') else 12,
            "day_of_week": df.index[-1].weekday() if hasattr(df.index[-1], 'weekday') else 0,
            "strategy": signal.tag or "unknown",
        }
        
        predictor = Predictor()
        result = predictor.predict_gate(df, metadata)
        
        if result is None:
            log.debug("Trade gate: no prediction (model unavailable or error)")
            return True  # Fail open
        
        prediction = result.get("prediction", 0)
        confidence = result.get("confidence", 0.0)
        threshold = self.cfg.ml.trade_gate_threshold
        
        passed = (prediction == 1) and (confidence >= threshold)
        
        log.info(
            "Trade gate: %s %s - prediction=%s confidence=%.3f threshold=%.2f → %s",
            symbol, signal.side.value,
            "WIN" if prediction == 1 else "LOSS",
            confidence, threshold,
            "PASS" if passed else "BLOCK"
        )
        
        return passed
        
    except Exception as e:
        log.warning("Trade gate error: %s - allowing trade", e)
        return True  # Fail open
```

Modify `_phase_scan()` in `EngineLoop`:

```python
def _phase_scan(self, db, enabled, equity):
    # ... existing code ...
    
    for strat in enabled:
        # ... generate signal ...
        if signal is None:
            continue
        
        # NEW: ML Trade Gate check
        if not self._check_trade_gate(symbol, timeframe, signal, df):
            log.debug("Trade gate blocked %s %s", symbol, signal.side.value)
            continue
        
        # ... existing SL/TP, sizing, risk checks ...
```

---

### **Phase 8: Frontend Integration**

**Update**: `dashboard/v2/routes/ml.py`

Add new endpoints:

```python
@router.post("/train-highconv")
def train_highconv_model(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    """Train a high-conviction signal model."""
    symbol = payload.get("symbol", "XAUUSD")
    timeframe = payload.get("timeframe", "H1")
    model_type = payload.get("model_type", "random_forest")
    model_name = payload.get("model_name", f"{symbol}-{timeframe}-HighConv")
    hold_period = payload.get("hold_period", 4)
    atr_multiplier = payload.get("atr_multiplier", 1.5)
    
    # Create MLModel record
    from db.models import MLModel, ModelType
    try:
        mtype = ModelType.HIGHCONV_SIGNAL
    except ValueError:
        mtype = ModelType.RANDOM_FOREST
    
    ml_model = MLModel(
        name=model_name,
        model_type=mtype,
        symbol=symbol,
        timeframe=timeframe,
        status="pending",
        hyperparams={
            "hold_period": hold_period,
            "atr_multiplier": atr_multiplier,
        },
    )
    db.add(ml_model)
    db.commit()
    db.refresh(ml_model)
    
    # Background training
    from ml.trainer import train_highconv
    thread = threading.Thread(
        target=_bg_train_highconv,
        args=(ml_model.id, symbol, timeframe, model_type, hold_period, atr_multiplier, db.bind.connect),
        daemon=True,
    )
    thread.start()
    
    return {"status": "queued", "model_id": ml_model.id}


def _bg_train_highconv(
    model_id: int,
    symbol: str,
    timeframe: str,
    model_type: str,
    hold_period: int,
    atr_multiplier: float,
    db_factory: Any,
) -> None:
    """Background training worker for high-conviction model."""
    db: Session = db_factory()
    try:
        from ml.trainer import train_highconv
        result = train_highconv(
            symbol=symbol,
            timeframe=timeframe,
            model_type=model_type,
            hold_period=hold_period,
            atr_multiplier=atr_multiplier,
            db_session=db,
        )
        # Update MLModel row (similar to existing _bg_train)
        ml_model = db.query(MLModel).get(model_id)
        if ml_model:
            ml_model.status = "ready"
            ml_model.accuracy = result["metrics"]["accuracy"]
            ml_model.precision = result["metrics"]["precision"]
            ml_model.recall = result["metrics"]["recall"]
            ml_model.f1 = result["metrics"]["f1"]
            ml_model.feature_columns = result["feature_columns"]
            ml_model.feature_importance = result["feature_importance"]
            ml_model.artifact_path = result["artifact_path"]
            ml_model.last_trained_at = pd.Timestamp.now(tz="UTC")
            db.commit()
    except Exception as exc:
        log.exception("HighConv training failed: model_id=%d: %s", model_id, exc)
        ml_model = db.query(MLModel).get(model_id)
        if ml_model:
            ml_model.status = "failed"
            db.commit()
    finally:
        db.close()


@router.post("/gate/train")
def train_gate_model(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    """Train trade gate model from backtest trades."""
    symbol = payload.get("symbol", "XAUUSD")
    timeframe = payload.get("timeframe", "M15")
    model_type = payload.get("model_type", "random_forest")
    model_name = payload.get("model_name", f"{symbol}-{timeframe}-Gate")
    
    # Background training
    from ml.gate_trainer import train_gate
    thread = threading.Thread(
        target=_bg_train_gate,
        args=(symbol, timeframe, model_type, model_name, db.bind.connect),
        daemon=True,
    )
    thread.start()
    
    return {"status": "queued", "message": "Gate training started"}


def _bg_train_gate(
    symbol: str,
    timeframe: str,
    model_type: str,
    model_name: str,
    db_factory: Any,
) -> None:
    """Background training worker for gate model."""
    db: Session = db_factory()
    try:
        from ml.gate_trainer import train_gate
        result = train_gate(
            symbol=symbol,
            timeframe=timeframe,
            model_type=model_type,
            model_name=model_name,
            db_session=db,
        )
        log.info("Gate training complete: model_id=%d", result["ml_model_id"])
    except Exception as exc:
        log.exception("Gate training failed: %s", exc)
    finally:
        db.close()


@router.get("/gate/status")
def get_gate_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get active trade gate model and stats."""
    from db.models import MLModel
    gate_model = db.query(MLModel).filter(
        MLModel.model_type == "trade_gate",
        MLModel.is_active == True,
        MLModel.status == "ready"
    ).first()
    
    if not gate_model:
        return {"active": False, "model": None}
    
    return {
        "active": True,
        "model": {
            "id": gate_model.id,
            "name": gate_model.name,
            "symbol": gate_model.symbol,
            "timeframe": gate_model.timeframe,
            "accuracy": gate_model.accuracy,
            "precision": gate_model.precision,
            "recall": gate_model.recall,
            "f1": gate_model.f1,
            "n_train_samples": gate_model.n_train_samples,
            "last_trained_at": gate_model.last_trained_at.isoformat() if gate_model.last_trained_at else None,
        }
    }
```

---

### **Phase 9: Testing & Validation**

**Unit Tests** (create `tests/test_ml_highconv.py`):

```python
def test_build_highconv_features():
    from ml.feature_engineer import build_highconv_features
    df = pd.DataFrame(...)  # Mock OHLCV data
    features = build_highconv_features(df)
    assert features.shape[1] == 17  # 17 features

def test_detect_regime():
    from ml.feature_engineer import detect_regime
    # Trending market (high ADX)
    assert detect_regime(trending_df) == "trending"
    # Ranging market (low ADX, low ATR)
    assert detect_regime(ranging_df) == "ranging"

def test_ml_signal_generator():
    from strategies.ml_signal_generator import MLSignalGenerator
    strat = MLSignalGenerator(symbol="XAUUSD", timeframe="H1")
    signal = strat.generate_signal(data)
    # Should return None most of the time (high threshold)
    # Occasionally return Signal with high confidence
```

**Integration Test**:

1. Train highconv model on XAUUSD H1 (5000 bars)
2. Deploy via `/api/v2/ml/models/{id}/deploy`
3. Verify `StrategyConfig` entry created: `ml_highconv_{id}`
4. Start engine, check logs for "MLSignalGenerator" signals
5. Backtest ML Signal Generator alone:
   ```bash
   python -m quant.runner --strategy ml_signal_generator --symbol XAUUSD --timeframe H1 --n_bars 5000
   ```
6. Check win rate in `strategy_performance` endpoint

---

### **Phase 10: Documentation**

Create `docs/ml_highconv_workflow.md`:

```markdown
# ML High-Conviction Signal Generator & Trade Gate

## Overview

Two ML pipelines:
1. **Signal Generator**: Produces high-quality trade signals (1/day, 70% win rate)
2. **Trade Gate**: Filters all trades through win/loss classifier

## Quick Start

### Train High-Conviction Model

1. Ensure you have backtest data for XAUUSD H1 (5000+ bars)
2. In ML Center, click "Train High-Conviction Model"
3. Wait for training to complete (status: ready)
4. Click "Deploy" to activate as strategy
5. Enable "ML Signal Generator" in Strategy Library

### Train Trade Gate

1. Run backtests to collect trades (aim for 500+)
2. In ML Center, click "Train Trade Gate"
3. Gate model will train on all backtest trades
4. Enable gate in config: `ML_TRADE_GATE_ENABLED=true`

## Configuration

```python
# .env
ML_SIGNAL_GENERATOR_ENABLED=true
ML_HIGHCONV_THRESHOLD=0.75

ML_TRADE_GATE_ENABLED=true
ML_TRADE_GATE_THRESHOLD=0.55
```

## Expected Performance

- **Signal Generator**: 20-30 trades/month, 65-75% win rate, Sharpe > 1.5
- **Trade Gate**: Blocks 20-40% of low-quality trades, improves overall win rate by 5-10%

## Monitoring

Check engine logs:
- `MLSignalGenerator: XAUUSD BUY signal @ 2340.50 (conf=0.82)`
- `Trade gate: XAUUSD BUY - prediction=WIN confidence=0.73 → PASS`

Dashboard metrics:
- ML signals generated today
- Gate block rate
- Pass-through win rate
```

---

## **Success Criteria**

| Metric | Target |
|--------|--------|
| ML Signal Generator trades/day | 0-2 |
| ML Signal Generator win rate | ≥ 65% |
| ML Signal Generator Sharpe | > 1.5 |
| Trade Gate block rate | 20-40% |
| Pass-through win rate improvement | +5-10% vs blocked trades |

---

## **Rollback Plan**

If issues arise:

1. **Disable ML Signal Generator**: Set `ML_SIGNAL_GENERATOR_ENABLED=false` or deactivate strategy
2. **Disable Trade Gate**: Set `ML_TRADE_GATE_ENABLED=false`
3. **Revert to baseline**: Use existing strategies without ML

---

## **Timeline**

- **Day 1**: Phases 1-3 (Feature engineering, Signal Generator, Training)
- **Day 2**: Phase 4 (Predictor), Phase 5 (DB/config), Phase 6 (Gate)
- **Day 3**: Phase 7 (Frontend), Phase 8 (Testing)
- **Day 4**: Phase 9 (Documentation), validation, tuning

---

## **Questions & Risks**

**Q**: What if highconv model has too few positive samples?
**A**: Adjust `atr_multiplier` lower (1.0) to include more bars, or use longer lookback.

**Q**: Gate model accuracy low (< 55%)?
**A**: Add more features (strategy one-hot, market regime), or collect more trades.

**Q**: ML signals too frequent?
**A**: Increase `confidence_threshold` to 0.85 or tighten `allowed_regimes`.

**Q**: Gate blocking too many trades?
**A**: Lower `trade_gate_threshold` to 0.50 or retrain with more balanced dataset.

---

**Next Step**: Start implementation with Phase 1 (ml/feature_engineer.py enhancements).