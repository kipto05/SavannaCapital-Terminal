"""Portfolio risk monitor — aggregated endpoint."""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from auth.router import _get_current_user
from db.models import AccountSnapshot, Trade
from db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter()

_CRYPTO_PFX = ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA")
_EQUITY_PFX = ("AAPL", "TSLA", "NVDA", "MSFT", "GOOG", "META", "AMZN", "ES", "NQ")
_METAL_PFX = ("XAU", "XAG", "GOLD", "SILVER", "GC", "SI")
_FX_PFX = ("EUR", "GBP", "USD", "JPY", "AUD", "NZD", "CAD", "CHF")


def _asset(sym: str) -> str:
    s = sym.upper()
    if any(s.startswith(p) for p in _METAL_PFX):
        return "metals"
    if any(s.startswith(p) for p in _CRYPTO_PFX):
        return "crypto"
    if any(s.startswith(p) for p in _EQUITY_PFX):
        return "equities"
    if len(s) >= 6 and s[:3] in _FX_PFX and s[3:6] in _FX_PFX:
        return "fx"
    return "other"


def _grp(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("trend", "ema", "macd", "momentum")):
        return "trend"
    if any(k in n for k in ("reversion", "mean", "band", "vwap", "stoch")):
        return "mean_reversion"
    if any(k in n for k in ("scalp", "hf", "hft")):
        return "hft_scalp"
    if any(k in n for k in ("breakout", "session", "macro")):
        return "macroscopic_event"
    if any(k in n for k in ("divergence", "swing")):
        return "swing_divergence"
    return "other"


def _pearson(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    a2, b2 = a[:n], b[:n]
    ma = sum(a2) / n
    mb = sum(b2) / n
    num = sum((a2[i] - ma) * (b2[i] - mb) for i in range(n))
    da = math.sqrt(sum((x - ma) ** 2 for x in a2))
    db2 = math.sqrt(sum((x - mb) ** 2 for x in b2))
    if da < 1e-12 or db2 < 1e-12:
        return 0.0
    return num / (da * db2)


@router.get("/overview")
def overview(
    current_user=Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    latest = db.query(AccountSnapshot).order_by(desc(AccountSnapshot.created_at)).first()
    prev = (
        db.query(AccountSnapshot)
        .filter(AccountSnapshot.id != (latest.id if latest else 0))
        .order_by(desc(AccountSnapshot.created_at))
        .first()
    )
    eq_now = float(latest.equity) if latest else 0.0
    eq_prev = float(prev.equity) if prev else 0.0
    margin = float(latest.margin) if latest else 0.0
    free = float(latest.free_margin) if latest else 0.0
    margin_pct = (margin / eq_now * 100) if eq_now > 0 else 0.0
    daily_dd = ((eq_now - eq_prev) / eq_prev * 100) if eq_prev > 0 else 0.0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    wk_snaps = (
        db.query(AccountSnapshot)
        .filter(AccountSnapshot.created_at >= week_ago)
        .order_by(AccountSnapshot.created_at.asc())
        .all()
    )
    weekly_dd = 0.0
    if wk_snaps and eq_prev > 0:
        weekly_dd = (eq_now - min(float(s.equity) for s in wk_snaps)) / eq_prev * 100

    all_snaps = db.query(AccountSnapshot).order_by(AccountSnapshot.created_at.asc()).limit(365).all()
    var_95 = 0.0
    if len(all_snaps) >= 5:
        eqs = [float(s.equity) for s in all_snaps]
        rets = [
            (eqs[i] - eqs[i - 1]) / eqs[i - 1]
            for i in range(1, len(eqs))
            if eqs[i - 1] != 0
        ]
        if len(rets) >= 2:
            mu = sum(rets) / len(rets)
            vr = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
            var_95 = 1.645 * math.sqrt(vr) * eq_now

    trades = (
        db.query(Trade)
        .filter(Trade.is_active.is_(True))
        .order_by(desc(Trade.opened_at))
        .limit(500)
        .all()
    )

    positions = []
    total_exposure = 0.0
    by_asset = defaultdict(float)
    by_strat = defaultdict(float)
    strat_ret = defaultdict(list)

    for t in trades:
        entry = float(t.entry or t.open_price or 0.0)
        size = float(t.lot_size or 0.0)
        notional = size * entry * 100_000 if entry > 0 else 0.0
        pnl = float(t.pnl or 0.0)
        sl = float(t.sl or 0.0)
        tp = float(t.tp or 0.0)
        risk_pct = 0.0
        if entry > 0 and sl > 0 and eq_now > 0:
            risk_pct = abs(entry - sl) / entry * size * 100_000 / eq_now * 100

        positions.append({
            "account": "Quant-A1",
            "symbol": t.symbol,
            "dir": "Long" if t.side.name == "BUY" else "Short",
            "entry": entry,
            "price": entry,
            "size": size,
            "sl": sl,
            "tp": tp,
            "pnl": pnl,
            "risk_pct": round(risk_pct, 2),
            "asset_class": _asset(t.symbol),
            "strategy": t.strategy_name,
        })
        total_exposure += notional
        by_asset[_asset(t.symbol)] += notional
        g = _grp(t.strategy_name)
        by_strat[g] += notional
        if t.pnl_r is not None:
            strat_ret[g].append(float(t.pnl_r))

    alloc = {
        k: round(v / total_exposure * 100, 1) if total_exposure > 0 else 0.0
        for k, v in by_asset.items()
    }
    for k in ("equities", "fx", "crypto", "metals", "other"):
        alloc.setdefault(k, 0.0)

    strat_exp = {k: round(v, 0) for k, v in sorted(by_strat.items(), key=lambda x: -x[1])}
    groups = sorted(set(_grp(t.strategy_name) for t in trades if t.strategy_name))

    corr = [[1.0 if i == j else 0.0 for j in range(len(groups))] for i in range(len(groups))]
    if len(groups) >= 2:
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                r = _pearson(
                    strat_ret.get(groups[i], []),
                    strat_ret.get(groups[j], []),
                )
                corr[i][j] = round(r, 2)
                corr[j][i] = round(r, 2)

    alerts = []
    for a_name, a_val in by_asset.items():
        if total_exposure > 0 and a_val / total_exposure > 0.35:
            alerts.append({
                "severity": "error",
                "account": "System",
                "symbol": a_name.upper(),
                "message": f"High concentration: {a_name} at {a_val / total_exposure * 100:.1f}% of portfolio",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
    if daily_dd < -2.0:
        alerts.append({
            "severity": "warning",
            "account": "System",
            "symbol": "PORTFOLIO",
            "message": f"Daily drawdown {daily_dd:.2f}% breached -2.0% threshold",
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    if eq_now > 0 and margin_pct > 80:
        alerts.append({
            "severity": "error",
            "account": "System",
            "symbol": "MARGIN",
            "message": f"Margin usage {margin_pct:.1f}% above 80% threshold",
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    if eq_now > 0 and free / eq_now < 0.2:
        alerts.append({
            "severity": "warning",
            "account": "System",
            "symbol": "FREE_MARGIN",
            "message": f"Free margin ratio {free / eq_now * 100:.1f}% below 20% floor",
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "kpis": {
            "daily_dd_pct": round(daily_dd, 2),
            "weekly_dd_pct": round(weekly_dd, 2),
            "total_exposure_usd": round(total_exposure, 0),
            "var_95_1d_usd": round(var_95, 0),
            "margin_usage_pct": round(margin_pct, 1),
        },
        "positions": positions,
        "asset_allocation": alloc,
        "strategy_exposure_usd": strat_exp,
        "correlation": {
            "labels": groups,
            "matrix": corr,
        },
        "alerts": alerts,
    }
