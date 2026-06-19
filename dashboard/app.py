"""dashboard/app.py — Savanna Capital Quant OS dashboard."""
from __future__ import annotations

import logging
import threading
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from auth.router import (
    _get_current_user,
    router as auth_router,
)
from config.settings import config
from db.models import (
    AIAdvisorSuggestion,
    AccountSnapshot,
    BacktestRun,
    Hypothesis,
    MLModel,
    OHLCVBar,
    PlatformSetting,
    StrategyConfig,
    Trade,
    TradeAnnotation,
    User,
)
from db.session import engine, get_db

log = logging.getLogger(__name__)

app = FastAPI(
    title="Savanna Capital Quant OS",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.dashboard.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# -- Security headers middleware ------------------------------------------------
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Never cache HTML pages during development / frequent deploys
    ctype = (response.headers.get("content-type") or "").lower()
    if "text/html" in ctype:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# -- Auth guard middleware ------------------------------------------------------
# All HTML page routes render regardless of auth state -- the page itself
# fetches data via apiFetch and _base.html handles 401 -> /login redirects.
# API routes enforce auth via the _get_current_user dependency on each handler.
# Public paths below bypass the middleware entirely.

_PUBLIC_PREFIXES = (
    "/auth/",  # login / refresh (router prefix = /auth, not /api/auth)
    "/health",  # health
    "/static/",  # css/js assets
    "/login",  # login page itself
)

@app.middleware("http")
async def _auth_guard(request: Request, call_next):
    path = request.url.path

    # Allow OPTIONS preflight
    if request.method == "OPTIONS":
        return await call_next(request)

    # Allow explicitly public paths
    for prefix in _PUBLIC_PREFIXES:
        if path == prefix.rstrip("/") or path.startswith(prefix):
            return await call_next(request)

    # All other routes pass through -- API endpoints self-protect via
    # _get_current_user, HTML pages will redirect via apiFetch 401 handling.
    return await call_next(request)

# Resolve templates directory once at module load time -- absolute, CWD-independent
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_tpl = None

def _get_templates() -> "Jinja2Templates":
    global _tpl
    if _tpl is None:
        from fastapi.templating import Jinja2Templates
        _tpl = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    return _tpl

# Disabled StaticFiles mount due to 404 issues on Windows; using custom route instead.
# app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

app.include_router(auth_router)

# -- ML Center routes -----------------------------------------------------------
from dashboard.routes.ml import router as ml_router  # noqa: E402
app.include_router(ml_router)

# -- Portfolio Risk Monitor routes ----------------------------------------------
from dashboard.routes.risk import router as risk_router  # noqa: E402
app.include_router(risk_router, prefix="/api/risk")

# -- Quant Optimisation routes ---------------------------------------------------
from dashboard.routes.quant import router as quant_router  # noqa: E402
app.include_router(quant_router, prefix="/api/quant")

# -- Notifications routes --------------------------------------------------------
from dashboard.routes.notifications import router as notifications_router
app.include_router(notifications_router)

# v2 API sub-application
from dashboard.v2.app import app as v2_app  # noqa: E402
app.mount("/api/v2", v2_app)

# -- Static file serving (custom) --------------------------------------------
@app.get("/static/{file_path:path}")
async def serve_static(file_path: str):
    """Serve static files from the static directory."""
    full_path = Path(__file__).parent / "static" / file_path
    if full_path.is_file():
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="File not found")

# -- Internal helper -----------------------------------------------------------
def _mt5_adapter():
    try:
        from execution.mt5_adapter import MT5Adapter
        return MT5Adapter()
    except Exception as exc:
        log.exception("Failed to import MT5Adapter: %s", exc)
        return None

# -- API endpoints -------------------------------------------------------------
@app.get("/api/account/stats")
def api_account_stats(current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    snapshot = db.query(AccountSnapshot).order_by(AccountSnapshot.created_at.desc()).first()
    if snapshot:
        return snapshot.to_dict()
    return {"balance": 0, "equity": 0, "margin": 0, "free_margin": 0}

@app.get("/api/account/snapshots")
def api_account_snapshots(limit: int = 200, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    snaps = (
        db.query(AccountSnapshot)
        .order_by(AccountSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    return [s.to_dict() for s in reversed(snaps)]

@app.get("/api/trades/recent")
def api_trades_recent(limit: int = 50, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    trades = db.query(Trade).order_by(Trade.id.desc()).limit(limit).all()
    return [t.to_dict() for t in trades]

@app.get("/api/strategies")
def api_strategies_list(current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    from strategies.registry import StrategyRegistry
    reg = StrategyRegistry(db)
    reg._seed_if_needed(db)
    configs = db.query(StrategyConfig).order_by(StrategyConfig.name).all()
    return [sc.to_dict() for sc in configs]

@app.get("/api/strategies/library")
def api_strategies_library(current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    from strategies.registry import StrategyRegistry
    reg = StrategyRegistry(db)
    reg._seed_if_needed(db)
    all_rows = db.query(StrategyConfig).order_by(StrategyConfig.name).all()
    results = []
    for row in all_rows:
        cls = reg.classes.get(row.name)
        label = cls.meta.label if cls else row.name.replace("_", " ").title()
        symbol = cls.meta.default_symbol if cls else ""
        tf = cls.meta.typical_timeframes[0] if cls and cls.meta.typical_timeframes else ""
        trades = (
            db.query(Trade)
            .filter(Trade.strategy_name == row.name)
            .order_by(Trade.id.desc())
            .limit(200)
            .all()
        )
        total = len(trades)
        wins = sum(1 for t in trades if t.pnl_r is not None and t.pnl_r > 0)
        win_rate = wins / total if total else 0
        net_pnl = sum(t.pnl_r for t in trades if t.pnl_r is not None)

        # Compute additional metrics
        sharpe_ratio = 0.0
        max_drawdown_pct = 0.0
        return_7d = 0.0
        try:
            # Get risk_per_trade from strategy params or fallback to config
            risk_frac = row.params.get("risk_per_trade", config.risk.risk_per_trade) if row.params else config.risk.risk_per_trade

            # 1. Sharpe ratio from daily returns
            # Filter trades with pnl_r and closed_at
            valid_trades = [t for t in trades if t.pnl_r is not None and t.closed_at is not None]
            if len(valid_trades) >= 2:
                # Group by date (UTC) and sum returns per day
                daily_returns_dict = {}
                for t in valid_trades:
                    # Ensure closed_at is timezone-aware UTC
                    closed = t.closed_at
                    if closed.tzinfo is None:
                        closed = closed.replace(tzinfo=timezone.utc)
                    date_key = closed.date()
                    daily_ret = t.pnl_r * risk_frac
                    daily_returns_dict[date_key] = daily_returns_dict.get(date_key, 0.0) + daily_ret
                # Build chronological list of daily returns
                daily_returns = [daily_returns_dict[date] for date in sorted(daily_returns_dict.keys())]
                if len(daily_returns) >= 2:
                    mean = sum(daily_returns) / len(daily_returns)
                    # Sample standard deviation
                    if len(daily_returns) > 1:
                        variance = sum((x - mean) ** 2 for x in daily_returns) / (len(daily_returns) - 1)
                        std = variance ** 0.5 if variance > 0 else 0
                    else:
                        std = 0
                    sharpe_ratio = mean / std * (252 ** 0.5) if std > 0 else 0.0
                else:
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0

            # 2. Max drawdown percentage using equity curve
            # Use valid trades sorted by opened_at chronological
            trades_with_dates = [t for t in trades if t.opened_at is not None and t.pnl_r is not None]
            if trades_with_dates:
                # Sort by opened_at ascending
                sorted_trades = sorted(trades_with_dates, key=lambda t: t.opened_at)
                equity = 1.0
                peak = 1.0
                max_dd = 0.0
                for t in sorted_trades:
                    # Multiplicative equity update: equity *= (1 + pnl_r * risk_frac)
                    equity *= (1 + t.pnl_r * risk_frac)
                    if equity > peak:
                        peak = equity
                    if peak > 0:
                        dd = (peak - equity) / peak
                        if dd > max_dd:
                            max_dd = dd
                max_drawdown_pct = max_dd * 100
            else:
                max_drawdown_pct = 0.0

            # 3. Return 7D (sum of pnl_r for trades opened in last 7 days)
            now = datetime.now(timezone.utc)
            seven_days_ago = now - timedelta(days=7)
            recent_pnl = []
            for t in trades:
                if t.pnl_r is not None and t.opened_at is not None:
                    opened = t.opened_at
                    # Handle naive datetime: assume UTC
                    if opened.tzinfo is None:
                        opened = opened.replace(tzinfo=timezone.utc)
                    if opened >= seven_days_ago:
                        recent_pnl.append(t.pnl_r)
            return_7d = sum(recent_pnl) if recent_pnl else 0.0

        except Exception as exc:
            log.exception("Error computing metrics for strategy %s: %s", row.name, exc)
            sharpe_ratio = 0.0
            max_drawdown_pct = 0.0
            return_7d = 0.0

        results.append({
            "name": row.name,
            "label": label,
            "symbol": symbol,
            "timeframe": tf,
            "is_active": row.is_active,
            "version": row.version or "1.0.0",
            "total_trades": total,
            "win_rate": win_rate,
            "avg_pnl_r": net_pnl / total if total else 0,
            "params": dict(row.params) if row.params else {},
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown_pct": max_drawdown_pct,
            "return_7d": return_7d,
        })
    return results

@app.post("/api/strategies/{name}/toggle")
def api_strategy_toggle(name: str, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    from strategies.registry import StrategyRegistry
    reg = StrategyRegistry(db)
    try:
        rec = reg.toggle(name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"name": rec.name, "is_active": rec.is_active}

@app.post("/api/strategies/{name}/deploy")
def api_strategy_deploy(name: str, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    from strategies.registry import StrategyRegistry
    reg = StrategyRegistry(db)
    reg._seed_if_needed(db)
    rec = reg.get_by_name(name)
    if rec is None:
        raise HTTPException(404, f"Strategy not found: {name}")
    log.info("Strategy deploy requested: name=%s", name)
    return {"status": "deploy_queued", "name": name}

@app.get("/api/quant/hypotheses")
def api_hypotheses(status: str | None = None, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    q = db.query(Hypothesis)
    if status:
        q = q.filter(Hypothesis.status == status)
    return [h.to_dict() for h in q.order_by(Hypothesis.created_at.desc()).all()]

@app.post("/api/quant/hypotheses")
def api_hypothesis_create(body: dict, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    h = Hypothesis(
        title=body.get("title", ""),
        description=body.get("description"),
        symbol=body.get("symbol"),
        timeframe=body.get("timeframe"),
        status=body.get("status", "draft"),
    )
    db.add(h)
    db.flush()
    return {"id": str(h.id), "status": h.status}

@app.patch("/api/quant/hypotheses/{hypothesis_id}")
def api_hypothesis_update(hypothesis_id: str, body: dict, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    h = db.query(Hypothesis).filter(Hypothesis.id == hypothesis_id).first()
    if h is None:
        raise HTTPException(404, "Hypothesis not found")
    for field in ("title", "description", "symbol", "timeframe", "status"):
        if field in body:
            setattr(h, field, body[field])
    db.flush()
    return {"id": str(h.id), "status": h.status}

@app.delete("/api/quant/hypotheses/{hypothesis_id}")
def api_hypothesis_delete(hypothesis_id: str, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    h = db.query(Hypothesis).filter(Hypothesis.id == hypothesis_id).first()
    if h is None:
        raise HTTPException(404, "Hypothesis not found")
    db.delete(h)
    return {"deleted": str(h.id)}

@app.get("/api/quant/backtests")
def api_backtests_list(current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    runs = db.query(BacktestRun).order_by(BacktestRun.created_at.desc()).all()
    return [r.to_dict() for r in runs]

@app.post("/api/quant/backtests")
def api_backtest_create(body: dict, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    run = BacktestRun(
        strategy_name=body.get("strategy_name", ""),
        symbol=body.get("symbol", ""),
        timeframe=body.get("timeframe", ""),
        status="pending",
        params=body.get("params", {}),
    )
    db.add(run)
    db.flush()
    return {"id": str(run.id), "status": "pending"}

# NOTE: /api/ml/models is now provided by the ML router -- no duplicate inline handler.

@app.get("/api/ai_advisor/suggestions")
def api_suggestions(current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(AIAdvisorSuggestion)
        .order_by(AIAdvisorSuggestion.created_at.desc())
        .limit(50)
        .all()
    )
    return [r.to_dict() for r in rows]

@app.get("/api/data/datasets")
def api_datasets(current_user: User = Depends(_get_current_user)):
    tf_map = getattr(config, "TIMEFRAMES_BY_ASSET", {})
    bar_counts = {}
    try:
        rows = (
            db.query(OHLCVBar.symbol, OHLCVBar.timeframe, func.count(OHLCVBar.id))
            .group_by(OHLCVBar.symbol, OHLCVBar.timeframe)
            .all()
        )
        for sym, tf, cnt in rows:
            bar_counts[f"{sym}|{tf}"] = cnt
    except Exception as exc:
        log.exception("Failed to fetch OHLCV bar counts: %s", exc)
    return {"assets": tf_map, "timeframes_by_asset": tf_map, "bar_counts": bar_counts}

@app.get("/api/data/datasets/{symbol}/ohlcv")
def api_ohlcv(symbol: str, timeframe: str = "M15", limit: int = 300, current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    bars = (
        db.query(OHLCVBar)
        .filter(OHLCVBar.symbol == symbol.upper(), OHLCVBar.timeframe == timeframe)
        .order_by(OHLCVBar.timestamp.desc())
        .limit(limit)
        .all()
    )
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "count": len(bars),
        "bars": [b.to_dict() for b in reversed(bars)],
    }

@app.get("/api/transcription/history")
def api_transcription(current_user: User = Depends(_get_current_user), db: Session = Depends(get_db)):
    anns = db.query(TradeAnnotation).order_by(TradeAnnotation.created_at.desc()).limit(200).all()
    return [a.to_dict() for a in anns]

@app.get("/api/settings")
def api_settings(current_user: User = Depends(_get_current_user)):
    from db.settings_service import settings_service
    return settings_service.get_all()

@app.post("/api/settings")
def api_settings_save(body: dict, current_user: User = Depends(_get_current_user)):
    from db.settings_service import settings_service
    settings_service.set_many(body)
    return {"saved": True, "keys": list(body.keys())}


# -- Executive Analytics endpoint ---------------------------------------------
@app.get("/api/v3/analytics")
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user)
) -> dict:
    log.info("Generating executive analytics")
    risk_free_rate = getattr(config.risk, 'risk_free_rate', 0.02)

    # Total AUM (latest equity)
    latest_snapshot = db.query(AccountSnapshot).order_by(AccountSnapshot.created_at.desc()).first()
    total_aum = latest_snapshot.equity if latest_snapshot else 0.0

    # Collect all snapshots
    snapshots = db.query(AccountSnapshot).order_by(AccountSnapshot.created_at.asc()).all()

    nav_series = []
    cumulative_return = 0.0
    sharpe_ratio = 0.0
    alpha = 0.0
    calmar_ratio = 0.0
    drawdown_events = []

    if snapshots:
        # Build nav_series with risk-free column
        first_snapshot = snapshots[0]
        initial_equity = first_snapshot.equity
        first_date = first_snapshot.created_at
        for s in snapshots:
            days_elapsed = (s.created_at - first_date).total_seconds() / 86400.0
            rf_val = initial_equity * ((1 + risk_free_rate) ** (days_elapsed / 365.0))
            nav_series.append({
                "date": s.created_at.isoformat(),
                "nav": s.equity,
                "risk_free": rf_val
            })

        # Build daily NAV series for metric calculations
        daily_dict = {}
        for s in snapshots:
            d = s.created_at.date()
            daily_dict[d] = s.equity  # last snapshot of the day wins

        if daily_dict:
            all_dates = sorted(daily_dict.keys())
            start_date = all_dates[0]
            end_date = all_dates[-1]
            # generate continuous date range
            current = start_date
            continuous_dates = []
            while current <= end_date:
                continuous_dates.append(current)
                current += timedelta(days=1)
            daily_filled = []
            current_nav = None
            for d in continuous_dates:
                if d in daily_dict:
                    current_nav = daily_dict[d]
                if current_nav is not None:
                    daily_filled.append((d, current_nav))

            if len(daily_filled) >= 2:
                # Compute cumulative return and CAGR
                first_nav = daily_filled[0][1]
                last_nav = daily_filled[-1][1]
                cumulative_return = (last_nav - first_nav) / first_nav if first_nav != 0 else 0.0
                days_total = (daily_filled[-1][0] - daily_filled[0][0]).days
                if days_total > 0 and first_nav > 0 and last_nav > 0:
                    cagr = (last_nav / first_nav) ** (365.0 / days_total) - 1.0
                else:
                    cagr = 0.0
                alpha = cagr - risk_free_rate

                # Sharpe ratio from daily returns
                returns = []
                daily_rf = risk_free_rate / 252.0
                for i in range(1, len(daily_filled)):
                    prev_nav = daily_filled[i-1][1]
                    curr_nav = daily_filled[i][1]
                    if prev_nav > 0:
                        ret = (curr_nav / prev_nav) - 1.0
                        returns.append(ret)
                if len(returns) >= 2:
                    mean_ret = sum(returns) / len(returns)
                    excess = [r - daily_rf for r in returns]
                    mean_excess = sum(excess) / len(excess)
                    if len(excess) > 1:
                        variance = sum((e - mean_excess) ** 2 for e in excess) / (len(excess) - 1)
                        std_excess = math.sqrt(variance) if variance > 0 else 0.0
                    else:
                        std_excess = 0.0
                    if std_excess > 0:
                        sharpe_ratio = mean_excess / std_excess * math.sqrt(252)
                else:
                    sharpe_ratio = 0.0

                # Max drawdown
                peak = daily_filled[0][1]
                max_dd = 0.0
                for _, nav in daily_filled:
                    if nav > peak:
                        peak = nav
                    else:
                        dd = (peak - nav) / peak
                        if dd > max_dd:
                            max_dd = dd
                calmar_ratio = cagr / max_dd if max_dd > 0 else 0.0

                # Drawdown events (last 10)
                events = []
                peak_nav = daily_filled[0][1]
                peak_date = daily_filled[0][0]
                in_drawdown = False
                max_dd_in_ep = 0.0
                trough_date = None
                peak_at_ep_start = None

                for i in range(1, len(daily_filled)):
                    d, nav = daily_filled[i]
                    if nav > peak_nav:
                        if in_drawdown:
                            recovery_date = d
                            duration_days = (trough_date - peak_at_ep_start).days
                            recovery_days = (recovery_date - trough_date).days
                            events.append({
                                "date": trough_date.isoformat(),
                                "drawdown": max_dd_in_ep,
                                "duration_days": duration_days,
                                "recovery_days": recovery_days
                            })
                            in_drawdown = False
                            max_dd_in_ep = 0.0
                        peak_nav = nav
                        peak_date = d
                    else:
                        dd = (peak_nav - nav) / peak_nav
                        if dd > max_dd_in_ep:
                            max_dd_in_ep = dd
                            trough_date = d
                        if not in_drawdown and dd > 0.001:
                            in_drawdown = True
                            peak_at_ep_start = peak_date
                events.sort(key=lambda e: e["date"], reverse=True)
                drawdown_events = events[:10]
            # else: insufficient daily points, metrics remain 0
    # else: no snapshots

    # Capital allocation from active strategies
    active_configs = db.query(StrategyConfig).filter_by(is_active=True).order_by(StrategyConfig.name).all()
    capital_allocation = []
    if active_configs:
        equal_alloc = 1.0 / len(active_configs)
        has_alloc = any(
            cfg.params.get('allocation') is not None or cfg.params.get('weight') is not None
            for cfg in active_configs
        )
        for cfg in active_configs:
            if has_alloc:
                alloc = cfg.params.get('allocation', cfg.params.get('weight'))
                if alloc is None:
                    alloc = equal_alloc
            else:
                alloc = equal_alloc
            capital_allocation.append({
                "strategy": cfg.name,
                "allocation": float(alloc)
            })

    # Strategy metrics
    strategy_metrics = []
    all_configs = db.query(StrategyConfig).order_by(StrategyConfig.name).all()
    for cfg in all_configs:
        sharpe = 0.0
        max_dd = 0.0
        net_pnl_r = 0.0
        trades_count = 0

        # Prefer latest completed backtest
        run = db.query(BacktestRun).filter(
            BacktestRun.strategy_name == cfg.name,
            BacktestRun.status == 'complete'
        ).order_by(BacktestRun.completed_at.desc()).first()

        if run:
            sharpe = run.sharpe_approx or 0.0
            max_dd = run.max_drawdown or 0.0
            net_pnl_r = run.net_pnl_r or 0.0
            trades_count = run.n_trades or 0
        else:
            # Aggregate from live trades
            trades = db.query(Trade).filter(Trade.strategy_name == cfg.name).all()
            trades_count = len(trades)
            net_pnl_r = sum(t.pnl_r for t in trades if t.pnl_r is not None)
            risk_frac = cfg.params.get('risk_per_trade', config.risk.risk_per_trade) if cfg.params else config.risk.risk_per_trade

            # Compute daily returns for Sharpe
            daily_returns = {}
            for t in trades:
                if t.pnl_r is not None and t.closed_at:
                    closed = t.closed_at
                    if closed.tzinfo is None:
                        closed = closed.replace(tzinfo=timezone.utc)
                    date_key = closed.date()
                    daily_returns[date_key] = daily_returns.get(date_key, 0.0) + (t.pnl_r * risk_frac)

            if daily_returns:
                dates = sorted(daily_returns.keys())
                returns = [daily_returns[d] for d in dates]
                if len(returns) >= 2:
                    mean = sum(returns) / len(returns)
                    if len(returns) > 1:
                        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
                        std = math.sqrt(variance) if variance > 0 else 0.0
                    else:
                        std = 0.0
                    if std > 0:
                        sharpe = mean / std * math.sqrt(252)

            # Max drawdown from equity curve
            sorted_trades = sorted(
                [t for t in trades if t.pnl_r is not None and t.opened_at],
                key=lambda t: t.opened_at
            )
            if sorted_trades:
                equity = 1.0
                peak = 1.0
                max_dd_local = 0.0
                for t in sorted_trades:
                    equity *= (1 + t.pnl_r * risk_frac)
                    if equity > peak:
                        peak = equity
                    if peak > 0:
                        dd = (peak - equity) / peak
                        if dd > max_dd_local:
                            max_dd_local = dd
                max_dd = max_dd_local

        strategy_metrics.append({
            "strategy": cfg.name,
            "sharpe_ratio": float(sharpe),
            "max_drawdown": float(max_dd),
            "net_pnl_r": float(net_pnl_r),
            "trades": trades_count
        })

    return {
        "cumulative_return": cumulative_return,
        "sharpe_ratio": sharpe_ratio,
        "alpha": alpha,
        "calmar_ratio": calmar_ratio,
        "nav_series": nav_series,
        "capital_allocation": capital_allocation,
        "strategy_metrics": strategy_metrics,
        "drawdown_events": drawdown_events,
        "total_aum": total_aum,
        "risk_free_rate": risk_free_rate
    }


# -- MT5 endpoints -------------------------------------------------------------
@app.get("/api/mt5/positions")
def api_mt5_positions(current_user: User = Depends(_get_current_user)):
    adapter = _mt5_adapter()
    if not adapter:
        return []
    try:
        positions = adapter.positions_get() or []
        for p in positions:
            p["account"] = str(config.mt5.login) if config.mt5.login else "default"
        return positions
    except Exception as exc:
        log.warning("MT5 positions fetch failed: %s", exc)
        return []

@app.get("/api/mt5/account")
def api_mt5_account(current_user: User = Depends(_get_current_user)):
    adapter = _mt5_adapter()
    if not adapter:
        return {"error": "MT5 adapter unavailable"}
    try:
        info = adapter.account_info() or {}
        info.setdefault("login", config.mt5.login)
        return info
    except Exception as exc:
        log.warning("MT5 account fetch failed: %s", exc)
        return {"error": str(exc)}

@app.get("/api/mt5/orders")
def api_mt5_orders(current_user: User = Depends(_get_current_user)):
    adapter = _mt5_adapter()
    if not adapter:
        return []
    try:
        orders = adapter.orders_get() or []
        for o in orders:
            o["account"] = str(config.mt5.login) if config.mt5.login else "default"
        return orders
    except Exception as exc:
        log.warning("MT5 orders fetch failed: %s", exc)
        return []

# -- Health + startup ----------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    log.info("Backend ready -- v2 routes loaded")

# -- Page renderers ------------------------------------------------------------
def _render_page(
    slug: str,
    title: str,
    active: str,
    request: Request,
) -> HTMLResponse:
    """Render a page template with auth token."""
    tpl = _get_templates()
    token = ""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    return tpl.TemplateResponse(
        request,
        f"pages/page_{slug}.html",
        {
            "title": title,
            "active": active,
            "page_title": title,
            "jwt_token": token,
        },
    )

@app.get("/v3/{page}", response_class=HTMLResponse)
def v3_page(page: str, request: Request):
    """Render a v3 template. Public route, no JWT required."""
    tpl = _get_templates()
    token = ""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    try:
        return tpl.TemplateResponse(
            request,
            f"v3/{page}.html",
            {
                "title": page.replace("_", " ").title(),
                "active": page,
                "page_title": page.replace("_", " ").title(),
                "jwt_token": token,
            },
        )
    except Exception as exc:
        log.error("Failed to render v3 template %s: %s", page, exc)
        raise HTTPException(status_code=404, detail="Page not found")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    path = Path(__file__).parent / "templates" / "login.html"
    html = path.read_text(encoding="utf-8")
    return HTMLResponse(html)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    tpl = _get_templates()
    token = ""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    return tpl.TemplateResponse(
        request,
        "v3/pages/mission_control.html",
        {
            "title": "Mission Control",
            "active": "mission_control",
            "page_title": "Mission Control",
            "jwt_token": token,
        },
    )

@app.get("/executive", response_class=HTMLResponse)
def executive(request: Request):
    return _render_page("executive", "Executive Analytics", "executive", request)

@app.get("/portfolio-risk", response_class=HTMLResponse)
def portfolio_risk(request: Request):
    return _render_page("portfolio_risk", "Portfolio Risk Monitor", "portfolio_risk", request)

@app.get("/multi-account", response_class=HTMLResponse)
def multi_account(request: Request):
    return _render_page("multi_account", "Multi-Account MT5", "multi_account", request)

@app.get("/trade-ops", response_class=HTMLResponse)
def trade_ops(request: Request):
    tpl = _get_templates()
    token = ""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    return tpl.TemplateResponse(
        request,
        "v3/pages/trade_operations.html",
        {
            "title": "Trade Operations",
            "active": "trade_ops",
            "page_title": "Trade Operations",
            "jwt_token": token,
        },
    )

@app.get("/risk-compliance", response_class=HTMLResponse)
def risk_compliance(request: Request):
    return _render_page("risk_compliance", "Risk & Compliance", "risk_compliance", request)

@app.get("/ml", response_class=HTMLResponse)
def ml(request: Request):
    return _render_page("ml", "ML Center", "ml", request)

@app.get("/ai-research", response_class=HTMLResponse)
def ai_research(request: Request):
    return _render_page("ai_research", "AI Research", "ai_research", request)

@app.get("/optimization", response_class=HTMLResponse)
def optimization(request: Request):
    return _render_page("optimization", "Optimization Hub", "optimization", request)

@app.get("/hypotheses", response_class=HTMLResponse)
def hypotheses_page(request: Request):
    return _render_page("hypotheses", "Hypotheses", "hypotheses", request)

@app.get("/research", response_class=HTMLResponse)
def research(request: Request):
    return _render_page("research", "Research Lab", "research", request)

@app.get("/strategies", response_class=HTMLResponse)
def strategies_page(request: Request):
    tpl = _get_templates()
    token = ""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    return tpl.TemplateResponse(
        request,
        "v3/pages/strategy_library.html",
        {
            "title": "Strategy Library",
            "active": "strategies",
            "page_title": "Strategy Library",
            "jwt_token": token,
        },
    )

@app.get("/backtest", response_class=HTMLResponse)
def backtest(request: Request):
    return _render_page("backtesting_center", "Backtesting Center", "backtesting_center", request)

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return v3_page("settings", request)

@app.get("/notifications", response_class=HTMLResponse)
def notifications_page(request: Request):
    return v3_page("notifications", request)
