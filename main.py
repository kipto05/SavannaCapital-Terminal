"""main.py — Entry point for the Savanna Capital Quant OS platform.

Usage:
python main.py --dashboard-only # dashboard only (no MT5)
python main.py --login 12345678 --password yourpass --server JustMarkets-Live
"""
from __future__ import annotations

import argparse
import logging
import threading
import time
from datetime import datetime, timezone

from config.settings import PlatformConfig
from db.session import SessionLocal
from db.models import AccountSnapshot
from strategies.registry import StrategyRegistry
from execution.mt5_adapter import MT5Adapter
from execution.order_manager import OrderManager
from execution.risk_manager import RiskManager
from execution.position_sizer import PositionSizer

log = logging.getLogger(__name__)


def _write_heartbeat() -> None:
    """Write current UTC timestamp to logs/engine_heartbeat."""
    try:
        from pathlib import Path as _Path
        hb_path = _Path(__file__).parent / "logs" / "engine_heartbeat"
        hb_path.parent.mkdir(parents=True, exist_ok=True)
        hb_path.write_text(
            str(datetime.now(timezone.utc).timestamp()), encoding="utf-8"
        )
    except Exception:
        pass


def _snapshot_account(db, adapter: MT5Adapter) -> None:
    """Persist a balance snapshot from current MT5 account info."""
    info = adapter.account_info()
    if info is None:
        return
    try:
        snap = AccountSnapshot(
            balance=float(info.get("balance", 0)),
            equity=float(info.get("equity", 0)),
            margin=float(info.get("margin", 0)),
            free_margin=float(info.get("margin_free", 0)),
            profit=float(info.get("profit", 0)),
            created_at=datetime.now(timezone.utc),
        )
        db.add(snap)
        db.flush()
        log.info(
            "Account snapshot: balance=%.2f equity=%.2f margin=%.2f profit=%.2f",
            snap.balance,
            snap.equity,
            snap.margin,
            snap.profit,
        )
    except Exception:
        log.exception("Account snapshot failed")


def _symbol(name: str) -> str:
    """Normalize for JustMarkets: append .m if not present."""
    n = name.strip().upper()
    if n.endswith(".M"):
        return n
    return n + ".M"


def _engine_loop(
    cfg: PlatformConfig, adapter: MT5Adapter, shutdown: threading.Event
) -> None:
    """Background trading engine loop. Runs until shutdown event is set."""
    import MetaTrader5 as mt5
    import pandas as pd

    risk = RiskManager()
    order_mgr = OrderManager(adapter)
    sizer = PositionSizer()

    # Seed strategy registry once
    with SessionLocal() as db:
        reg = StrategyRegistry(db)
        reg._seed_if_needed(db)
        _snapshot_account(db, adapter)

    last_snapshot = time.time()
    log.info(
        "Engine loop started — polling every %ds",
        cfg.engine.poll_interval_seconds,
    )

    while not shutdown.is_set():
        try:
            with SessionLocal() as db:
                reg = StrategyRegistry(db)
                enabled = reg.get_enabled()
                account_info = adapter.account_info()
                equity = (
                    float(account_info.get("equity", 10_000))
                    if account_info
                    else 10_000.0
                )

                for strat in enabled:
                    symbol = (
                        strat.meta.default_symbol
                        if strat.meta
                        else strat.name.replace("_", " ").title()
                    )
                    timeframe = (
                        strat.meta.typical_timeframes[0]
                        if strat.meta and strat.meta.typical_timeframes
                        else "M15"
                    )

                    # Fetch OHLCV from MT5
                    try:
                        mt5tf = getattr(
                            mt5, f"TIMEFRAME_{timeframe}", mt5.TIMEFRAME_M15
                        )
                        bars_raw = mt5.copy_rates_from_pos(
                            _symbol(symbol), mt5tf, 0, 300
                        )
                        if (
                            bars_raw is None
                            or len(bars_raw) < 50
                        ):
                            log.debug(
                                "Engine: %s — insufficient data (%d bars)",
                                symbol,
                                len(bars_raw) if bars_raw is not None else 0,
                            )
                            continue

                        df = pd.DataFrame(bars_raw)
                        df.rename(
                            columns={
                                "time": "timestamp",
                                "open": "open",
                                "high": "high",
                                "low": "low",
                                "close": "close",
                                "tick_volume": "volume",
                            },
                            inplace=True,
                        )
                        df["timestamp"] = pd.to_datetime(
                            df["timestamp"], unit="s", utc=True
                        )
                    except Exception as exc:
                        log.warning(
                            "Engine: %s — data fetch failed: %s",
                            symbol,
                            exc,
                        )
                        continue

                    # Resolve class and params
                    cls = reg.classes.get(strat.name)
                    if cls is None:
                        log.debug(
                            "Engine: class not found for %s", strat.name
                        )
                        continue

                    params = strat.params or {}
                    instance = cls(default_symbol=symbol, params=params)

                    try:
                        sig = instance.generate_signal({timeframe: df})
                    except Exception as exc:
                        log.exception(
                            "Engine: %s generate_signal error: %s",
                            strat.name,
                            exc,
                        )
                        continue

                    if sig is None:
                        continue

                    # Risk gate
                    block = risk.check_before_order(symbol, equity)
                    if block:
                        log.warning("Engine: order blocked — %s", block)
                        continue

                    # SL/TP
                    from execution.sl_tp_model import (  # local import
                        DynamicSLTPModel,
                    )

                    sltp = DynamicSLTPModel()
                    result = sltp.compute(
                        df=df, side=sig.side.value, entry=sig.entry
                    )
                    if result is None:
                        log.debug(
                            "Engine: %s — RR gate blocked trade",
                            strat.name,
                        )
                        continue

                    # Position sizing
                    lot_size = sizer.compute(
                        account_equity=equity,
                        entry=sig.entry,
                        sl=result.sl,
                        symbol=symbol,
                    )
                    if lot_size is None:
                        log.debug(
                            "Engine: %s — position sizing returned None",
                            strat.name,
                        )
                        continue

                    signal = {
                        "symbol": symbol,
                        "side": sig.side.value,
                        "entry": sig.entry,
                        "sl": result.sl,
                        "tp": result.tp2,
                        "tp1": result.tp1,
                        "tp2": result.tp2,
                        "lot_size": lot_size,
                        "strategy_name": strat.name,
                        "tag": sig.tag,
                        "timeframe": timeframe,
                        "sltp_result": result,
                    }

                    trade = order_mgr.submit(
                        signal, df={timeframe: df}, account_equity=equity
                    )
                    if trade is not None:
                        log.info(
                            "Engine: trade executed — %s %s lots=%.2f ticket=%s",
                            trade.symbol,
                            trade.side.value,
                            trade.lot_size,
                            trade.ticket,
                        )

            # Periodic account snapshot + heartbeat
            now = time.time()
            if (
                now - last_snapshot
                > cfg.engine.snapshot_interval_seconds
            ):
                _snapshot_account(db, adapter)
                last_snapshot = now

            _write_heartbeat()

        except Exception:
            log.exception("Engine loop error")

        # Sleep in small increments so shutdown() responds quickly
        for _ in range(int(cfg.engine.poll_interval_seconds * 10)):
            if shutdown.is_set():
                break
            time.sleep(0.1)

    log.info("Engine loop stopped")
    try:
        adapter.disconnect()
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Savanna Capital Quant OS")
    p.add_argument(
        "--dashboard-only",
        action="store_true",
        help="Skip MT5/engine",
    )
    p.add_argument(
        "--login", type=int, default=0, help="MT5 account login"
    )
    p.add_argument(
        "--password", default="", help="MT5 account password"
    )
    p.add_argument(
        "--server", default="", help="MT5 broker server"
    )
    return p.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()
    cfg = PlatformConfig.from_env()

    use_engine = False

    if not args.dashboard_only:
        mt5_login = args.login or cfg.mt5.login or 0
        mt5_password = args.password or cfg.mt5.password or ""
        mt5_server = args.server or cfg.mt5.server or ""

        if mt5_login == 0 or not mt5_password or not mt5_server:
            log.error(
                "MT5 credentials not set — pass --login --password --server or set env vars"
            )
            log.info("Falling back to dashboard-only mode")
        else:
            adapter = MT5Adapter()
            connected = adapter.connect()
            if connected:
                log.info(
                    "MT5 connected: login=%s server=%s",
                    mt5_login,
                    mt5_server,
                )
                shutdown_event = threading.Event()
                engine_thread = threading.Thread(
                    target=_engine_loop,
                    args=(cfg, adapter, shutdown_event),
                    daemon=True,
                    name="trading-engine",
                )
                engine_thread.start()
                use_engine = True
                # Write heartbeat immediately so dashboard sees engine as running
                _write_heartbeat()
            else:
                log.error("MT5 connection failed — falling back to dashboard-only mode")

    if not use_engine:
        log.info("Dashboard-only mode — skipping MT5 engine")

    import uvicorn

    # ── Existing v1 dashboard (never touch) ───────────────────────────
    v1_app = __import__("dashboard.app", fromlist=["app"]).app

    # ── New v2 API (all new features go here) ─────────────────────────
    v2_app = __import__("dashboard.v2.app", fromlist=["app"]).app
    v1_app.mount("/api/v2", v2_app)

    uvicorn.run(
        v1_app,
        host=cfg.dashboard.host,
        port=cfg.dashboard.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
