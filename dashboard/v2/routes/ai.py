"""dashboard/v2/routes/ai.py — AI Trading endpoints.

Mount: app.include_router(ai.router) -> /api/v2/ai/...
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from config.settings import config
from db.models import AIAdvisorSuggestion, StrategyConfig, Trade
from db.session import get_db
from strategies.registry import StrategyRegistry, StrategyRecord
from ai_advisor.advisor import agent as ai_agent

log = logging.getLogger(__name__)
router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _strategy_stats(db: Session, name: str) -> dict[str, Any]:
    """Compute stats from Trade table for strategy_name=name."""
    trades = db.query(Trade).filter(Trade.strategy_name == name).limit(500).all()
    total = len(trades)
    wins = sum(1 for t in trades if t.pnl_r is not None and t.pnl_r > 0)
    losses = sum(1 for t in trades if t.pnl_r is not None and t.pnl_r < 0)
    win_rate = wins / total if total else 0.0
    pnl_list = [t.pnl_r for t in trades if t.pnl_r is not None]
    net_pnl_r = sum(pnl_list) if pnl_list else 0.0
    avg_pnl_r = net_pnl_r / total if total else 0.0
    gross_win = sum(r for r in pnl_list if r > 0)
    gross_loss = abs(sum(r for r in pnl_list if r < 0))
    profit_factor = gross_win / gross_loss if gross_loss else None
    max_dd = None
    if pnl_list:
        equity = 1.0
        peak = 1.0
        max_dd_val = 0.0
        for r in pnl_list:
            equity += r * config.risk.risk_per_trade
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd_val:
                max_dd_val = dd
        max_dd = round(max_dd_val, 4)
    sharpe = None
    if len(pnl_list) > 1:
        mean_r = sum(pnl_list) / len(pnl_list)
        var_r = sum((r - mean_r) ** 2 for r in pnl_list) / (len(pnl_list) - 1)
        std_r = var_r ** 0.5
        if std_r > 0:
            sharpe = round(mean_r / std_r, 4)
    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),
        "net_pnl_r": round(net_pnl_r, 4),
        "avg_pnl_r": round(avg_pnl_r, 4),
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
    }

def _to_dict(sugg: AIAdvisorSuggestion) -> dict[str, Any]:
    """Serialize an AIAdvisorSuggestion for the frontend."""
    mc = sugg.market_context or {}
    return {
        "id": sugg.id,
        "symbol": sugg.symbol,
        "timeframe": sugg.timeframe,
        "side": sugg.side.value if hasattr(sugg.side, "value") else str(sugg.side),
        "confidence": sugg.confidence,
        "reasoning": sugg.reasoning,
        "market_context": mc,
        "entry": mc.get("entry"),
        "sl": mc.get("sl"),
        "tp1": mc.get("tp1"),
        "tp2": mc.get("tp2"),
        "created_at": sugg.created_at.isoformat() if sugg.created_at else None,
    }

def _fmt_age(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    delta = datetime.now(timezone.utc) - dt
    if delta.total_seconds() < 60:
        return f"{int(delta.total_seconds())}s"
    if delta.total_seconds() < 3600:
        return f"{int(delta.total_seconds() // 60)}m"
    return f"{int(delta.total_seconds() // 3600)}h"

# ── Mock heatmap data ─────────────────────────────────────────────────────────

_MOCK_HEATMAP = [
    {"symbol": "XAUUSD", "score": 0.85, "signal_count": 3, "direction": "LONG", "is_demo": True},
    {"symbol": "BTCUSD", "score": -0.62, "signal_count": 2, "direction": "SHORT", "is_demo": True},
    {"symbol": "EURUSD", "score": 0.41, "signal_count": 2, "direction": "LONG", "is_demo": True},
    {"symbol": "NVDA", "score": 0.91, "signal_count": 1, "direction": "LONG", "is_demo": True},
    {"symbol": "WTI", "score": -0.38, "signal_count": 1, "direction": "SHORT", "is_demo": True},
    {"symbol": "GBPUSD", "score": 0.55, "signal_count": 2, "direction": "LONG", "is_demo": True},
    {"symbol": "ETHUSD", "score": -0.29, "signal_count": 1, "direction": "SHORT", "is_demo": True},
    {"symbol": "US500", "score": 0.33, "signal_count": 1, "direction": "LONG", "is_demo": True},
]

# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/suggestions")
def get_suggestions(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """GET /api/v2/ai/suggestions — recent AI suggestions with stats."""
    rows = (
        db.query(AIAdvisorSuggestion)
        .order_by(desc(AIAdvisorSuggestion.created_at))
        .limit(limit)
        .all()
    )
    suggestions = [_to_dict(r) for r in rows]
    stats = _strategy_stats(db, "ai_trading")
    accuracy = round(stats["win_rate"] * 100, 1) if stats["total_trades"] > 0 else None
    avg_alpha = round(stats["avg_pnl_r"], 3) if stats["total_trades"] > 0 else None
    return {
        "suggestions": suggestions,
        "total_signals": len(suggestions),
        "accuracy_pct": accuracy,
        "avg_alpha": avg_alpha,
        "stats": stats,
    }

@router.get("/heatmap")
def get_heatmap(db: Session = Depends(get_db)):
    """GET /api/v2/ai/heatmap — per-asset sentiment scores.

    Returns live data when suggestions exist, otherwise falls back to
    mock data with is_demo=true so the UI always has data to display.
    """
    all_sugg = db.query(AIAdvisorSuggestion).all()
    if all_sugg:
        asset_map: dict[str, list[float]] = {}
        for s in all_sugg:
            sym = s.symbol.upper()
            if sym not in asset_map:
                asset_map[sym] = []
            side_val = s.side.value if hasattr(s.side, "value") else str(s.side)
            score = 1.0 if side_val == "BUY" else -1.0
            asset_map[sym].append(score * s.confidence)
        assets = []
        for sym, scores in asset_map.items():
            avg_score = sum(scores) / len(scores)
            assets.append({
                "symbol": sym,
                "score": round(avg_score, 3),
                "signal_count": len(scores),
                "direction": "LONG" if avg_score > 0 else "SHORT",
                "is_demo": False,
            })
        assets.sort(key=lambda x: abs(x["score"]), reverse=True)
        return {"assets": assets, "is_demo": False}

    return {"assets": _MOCK_HEATMAP, "is_demo": True, "note": "No live suggestions yet — showing demo data."}

@router.get("/reasoning/{symbol}")
def get_reasoning(symbol: str, db: Session = Depends(get_db)):
    """GET /api/v2/ai/reasoning/{symbol} — latest reasoning for a symbol."""
    row = (
        db.query(AIAdvisorSuggestion)
        .filter(AIAdvisorSuggestion.symbol == symbol.upper())
        .order_by(desc(AIAdvisorSuggestion.created_at))
        .first()
    )
    if row is None:
        return {
            "symbol": symbol.upper(),
            "direction": "—",
            "confidence": 0,
            "market_context": (
                "No AI suggestions generated yet for this symbol. "
                "Enable AI in the AI Trading page to start receiving signals."
            ),
            "alpha_factors": [],
            "risk_bullets": [],
            "model_version": config.ai.model,
            "is_demo": True,
        }

    side_val = row.side.value if hasattr(row.side, "value") else str(row.side)
    return {
        "symbol": row.symbol,
        "direction": side_val,
        "confidence": row.confidence,
        "market_context": row.reasoning or "No narrative available.",
        "alpha_factors": [
            {"name": "LLM Confidence", "value": f"{row.confidence * 100:.0f}%"},
            {"name": "Timeframe", "value": row.timeframe},
            {"name": "Signal Age", "value": _fmt_age(row.created_at)},
        ],
        "risk_bullets": [
            {"icon": "info", "text": "Signal is AI-generated — verify with your own analysis."},
            {"icon": "schedule", "text": f"Generated {_fmt_age(row.created_at)} ago."},
        ],
        "model_version": config.ai.model,
        "is_demo": False,
    }

@router.post("/chat")
def post_chat(body: dict[str, Any]):
    """POST /api/v2/ai/chat — research terminal query.

    Body: {"query": "...", "context": {"symbol": "...", "timeframe": "..."}}
    """
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(400, "body.query is required")
    context = body.get("context")
    result = ai_agent.chat(query, context=context)
    return result

@router.post("/toggle")
def toggle_ai(db: Session = Depends(get_db)):
    """POST /api/v2/ai/toggle — toggle AI strategy on/off.

    Creates StrategyConfig row for 'ai_trading' if it doesn't exist yet,
    then flips is_active via the registry.
    """
    reg = StrategyRegistry(db)
    rec = reg.get_by_name("ai_trading")
    if rec is None:
        row = StrategyConfig(
            name="ai_trading",
            label="AI Trading",
            symbol="XAUUSD",
            timeframe="M15",
            is_active=False,
            params={
                "enabled": False,
                "symbols": ["XAUUSD", "BTCUSD", "EURUSD", "NVDA"],
                "timeframe": "M15",
                "cooldown_minutes": config.ai.cooldown_minutes,
                "min_confidence": config.ai.min_confidence_to_show,
            },
            version=1,
        )
        db.add(row)
        db.flush()
        log.info("AI strategy seeded: ai_trading (inactive)")
        return {"name": "ai_trading", "is_active": False}

    # Toggle via registry (returns StrategyRecord with is_enabled)
    new_rec = reg.toggle("ai_trading")
    log.info(
        "AI toggle: name=ai_trading active=%s",
        new_rec.is_enabled,
    )
    return {"name": "ai_trading", "is_active": new_rec.is_enabled}

@router.get("/config")
def get_ai_config(db: Session = Depends(get_db)):
    """GET /api/v2/ai/config — current AI settings."""
    reg = StrategyRegistry(db)
    rec = reg.get_by_name("ai_trading")
    row_params = rec.params if rec else {}

    has_key = bool(
        config.ai.anthropic_api_key
        or config.ai.nvidia_api_key
        or config.ai.gemini_api_key
        or config.ai.openrouter_api_key
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("NVIDIA_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
    )
    return {
        "is_enabled": has_key,
        "provider": config.ai.provider,
        "model": config.ai.model,
        "min_confidence_to_show": config.ai.min_confidence_to_show,
        "cooldown_minutes": config.ai.cooldown_minutes,
        "max_tokens": config.ai.max_tokens,
        "strategy_active": rec.is_enabled if rec else False,
        "strategy_params": row_params,
    }

@router.put("/config")
def update_ai_config(body: dict[str, Any], db: Session = Depends(get_db)):
    """PUT /api/v2/ai/config — update AI settings."""
    allowed = {"cooldown_minutes", "min_confidence", "symbols", "timeframe", "min_confidence_to_show"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(400, f"no valid fields. allowed: {sorted(allowed)}")

    reg = StrategyRegistry(db)
    try:
        reg.update_params("ai_trading", updates)
    except Exception:
        pass

    if "cooldown_minutes" in updates:
        config.ai.cooldown_minutes = int(updates["cooldown_minutes"])
        ai_agent._cooldown_seconds = config.ai.cooldown_minutes * 60
    if "min_confidence_to_show" in updates:
        config.ai.min_confidence_to_show = float(updates["min_confidence_to_show"])

    return {"updated": updates}

@router.post("/generate")
def generate_signals(body: dict[str, Any]):
    """POST /api/v2/ai/generate — trigger AI suggestions for symbols.

    Body: {"symbols": ["BTCUSD", ...], "timeframe": "M15"}
    For production use, call from a background task.
    """
    symbols = body.get("symbols", [])
    timeframe = body.get("timeframe", "M15")
    if not symbols:
        raise HTTPException(400, "body.symbols must be a non-empty list")

    results = ai_agent.generate_signals(symbols, timeframe=timeframe)
    return {
        "generated": len(results),
        "symbols": [r.symbol for r in results],
        "timeframe": timeframe,
    }
