"""scripts/fetch_gold_5m_to_db.py — pull real XAUUSD M5 bars from MT5 into ohlcv_bars.

Usage:
    .\venv\Scripts\python.exe scripts\fetch_gold_5m_to_db.py

Requires:
    - JustMarkets MT5 terminal open and connected
    - DATABASE_URL set (for DB insert)
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


def main() -> int:
    from config.settings import config
    from data.repository import fetch_ohlcv
    from data.validator import validate
    from db.models import OHLCVBar
    from db.session import SessionLocal

    symbol = "XAUUSD"
    timeframe = "M5"
    days_back = 30

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days_back)

    log.info(
        "Fetching %s %s from %s to %s ...",
        symbol,
        timeframe,
        start_dt.date(),
        end_dt.date(),
    )

    df = fetch_ohlcv(symbol, timeframe, start=start_dt, end=end_dt)
    if df is None or df.empty:
        log.error("MT5 returned no data")
        return 1

    log.info("Fetched %d bars from MT5", len(df))

    report = validate(df, symbol=symbol, timeframe=timeframe)
    if not report.is_valid:
        log.error("Validation FAILED: %s", report.issues)
        return 1
    log.info("Data validated OK, %d issues", len(report.issues))
    log.info("Fetched %d bars total", len(df))

    session = SessionLocal()
    try:
        inserted = 0
        skipped = 0
        for ts, row in df.iterrows():
            bar_dt = ts.to_pydatetime()
            if bar_dt.tzinfo is None:
                bar_dt = bar_dt.replace(tzinfo=timezone.utc)

            exists = (
                session.query(OHLCVBar.id)
                .filter(
                    OHLCVBar.symbol == symbol,
                    OHLCVBar.timeframe == timeframe,
                    OHLCVBar.timestamp == bar_dt,
                )
                .first()
            )
            if exists:
                skipped += 1
                continue

            session.add(
                OHLCVBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=bar_dt,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0) or 0),
                    tick_volume=int(row.get("tick_volume", 0) or 0),
                    spread=int(row.get("spread", 0) or 0),
                )
            )
            inserted += 1

        session.commit()
        total = inserted + skipped
        log.info(
            "Inserted %d bars, skipped %d existing — %d total in DB",
            inserted,
            skipped,
            total,
        )
    except Exception as exc:
        session.rollback()
        log.exception("DB insert failed: %s", exc)
        return 1
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
