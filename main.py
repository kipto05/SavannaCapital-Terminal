"""main.py -- Entry point for the Savanna Capital Quant OS platform.

Usage:
python main.py --dashboard-only  # dashboard only (no MT5)
python main.py --login 12345678 --password yourpass --server JustMarkets-Live
"""
from __future__ import annotations

import argparse
import logging
import threading
import time

from config.settings import PlatformConfig
from strategies.registry import StrategyRegistry
from execution.mt5_adapter import MT5Adapter
from db.session import SessionLocal
from execution.notification_service import NotificationService

log = logging.getLogger(__name__)

# Notification cleanup background job configuration
NOTIFICATION_CLEANUP_MAX_RETRIES = 10


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
    p.add_argument(
        "--path", default="", help="MT5 terminal executable path"
    )
    return p.parse_args()


if __name__ == "__main__":
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
                "MT5 credentials not set - pass --login --password --server or set env vars"
            )
            log.info("Falling back to dashboard-only mode")
        else:
            adapter = MT5Adapter()
            if args.path:
                adapter.cfg.path = args.path
            if adapter.connect():
                log.info(
                    "MT5 connected: login=%d server=%s",
                    mt5_login,
                    mt5_server,
                )

                # Seed strategy registry from DB
                with SessionLocal() as db:
                    reg = StrategyRegistry(db)
                    reg._seed_if_needed(db)

                # Start engine loop in background thread
                from engine.engine_loop import EngineLoop
                loop = EngineLoop(cfg, adapter)
                engine_thread = threading.Thread(
                    target=loop.run,
                    args=(),
                    daemon=True,
                    name="trading-engine",
                )
                engine_thread.start()
                use_engine = True
            else:
                log.error(
                    "MT5 connection failed - falling back to dashboard-only mode"
                )

    if not use_engine:
        log.info("Dashboard-only mode - skipping MT5 engine")

    # Start notification cleanup background job if retention is configured
    if cfg.notification.retention_days > 0:
        def _notification_cleanup_loop():
            retry_count = 0
            while True:
                try:
                    db = SessionLocal()
                    ns = NotificationService(db)
                    deleted = ns.cleanup_old_notifications(cfg.notification.retention_days)
                    log.info("Notification cleanup: deleted %d old notifications", deleted)
                    db.close()
                    retry_count = 0  # reset on success
                except Exception as exc:
                    log.warning(
                        "Notification cleanup attempt failed (attempt %d/%d): %s",
                        retry_count + 1,
                        NOTIFICATION_CLEANUP_MAX_RETRIES,
                        exc,
                        exc_info=True,
                    )
                    retry_count += 1
                    if retry_count >= NOTIFICATION_CLEANUP_MAX_RETRIES:
                        log.error(
                            "Notification cleanup: max retries (%d) exceeded. Exiting thread.",
                            NOTIFICATION_CLEANUP_MAX_RETRIES,
                        )
                        break
                time.sleep(cfg.notification.cleanup_interval_seconds)

        cleanup_thread = threading.Thread(target=_notification_cleanup_loop, daemon=True)
        cleanup_thread.start()
        log.info(
            "Notification cleanup job started (retention=%d days)",
            cfg.notification.retention_days,
        )

    import uvicorn

    # Existing v1 dashboard (never touch)
    v1_app = __import__("dashboard.app", fromlist=["app"]).app

    # New v2 API (all new features go here)
    v2_app = __import__("dashboard.v2.app", fromlist=["app"]).app
    v1_app.mount("/api/v2", v2_app)

    uvicorn.run(
        v1_app,
        host=cfg.dashboard.host,
        port=cfg.dashboard.port,
        log_level="info",
    )