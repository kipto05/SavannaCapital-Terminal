import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
os.environ['DATABASE_URL'] = 'postgresql://trading:trading@localhost:5432/tradingwf'

from db.session import SessionLocal
from db.models import BacktestRun, Trade

for seq in range(24):
    db = SessionLocal()
    rows = []
    for rid in [35, 36]:
        r = db.query(BacktestRun).filter_by(id=rid).first()
        n = db.query(Trade).filter_by(backtest_run_id=rid).count() if r else 0
        rows.append(f'run {rid}: status={r.status if r else "missing"} trades_db={n} n_trades_col={r.n_trades if r else "-"} net={r.net_pnl_r if r else "-"}')
    db.close()
    print(f'{time.strftime("%H:%M:%S")}  ' + ' | '.join(rows))
    time.sleep(5)
