"""quant/backtest_engine.py — bar-by-bar backtest engine.

No look-ahead: at bar i, only bars 0..i are visible to generate_signal().
SL/TP always from DynamicSLTPModel. Lot size always from PositionSizer.
Equity curve starts at 1.0.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from config.settings import config
from data.validator import validate
from execution.sl_tp_model import DynamicSLTPModel, SLTPResult
from execution.position_sizer import PositionSizer

log = logging.getLogger(__name__)


# ── Result types ──────────────────────────────────────────────────────────────


@dataclass
class TradeResult:
    """A single simulated trade."""
    entry_time: datetime
    exit_time: datetime
    side: str  # "BUY" or "SELL"
    entry: float
    sl: float
    tp1: float
    tp2: float
    close_price: float
    lot_size: float
    pnl_r: float
    pnl_dollars: float
    exit_reason: str  # "tp1", "tp2", "sl", "bar_exit"
    bars_held: int
    tag: str = ""


@dataclass
class BacktestResult:
    """Complete backtest output."""
    trades: list[TradeResult] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    drawdown_curve: list[float] = field(default_factory=list)
    monthly_returns: dict[str, float] = field(default_factory=dict)
    n_bars: int = 0
    initial_equity: float = 10_000.0
    final_equity: float = 10_000.0
    net_pnl_r: float = 0.0
    net_pnl_dollars: float = 0.0
    win_rate: float = 0.0
    profit_factor: float | None = None
    sharpe_approx: float | None = None
    max_drawdown: float | None = None
    n_wins: int = 0
    n_losses: int = 0
    p_value: float | None = None
    is_significant: bool | None = None


# ── Engine ────────────────────────────────────────────────────────────────────


class BacktestEngine:
    """Bar-by-bar event-loop backtester. No look-ahead."""

    def __init__(
        self,
        initial_equity: float | None = None,
        risk_per_trade: float | None = None,
        warmup_bars: int | None = None,
        execution: str = "OHLC",
    ) -> None:
        self.initial_equity = initial_equity or config.backtest.default_initial_equity
        self.risk_per_trade = risk_per_trade or config.backtest.default_risk_per_trade
        self.warmup = warmup_bars or config.backtest.warmup_bars
        self.execution = execution  # "OHLC" or "Every Tick"
        self.sltp = DynamicSLTPModel()
        self.sizer = PositionSizer()

    # ── Public API ─────────────────────────────────────────────────────────

    def run(
        self,
        df: pd.DataFrame,
        strategy_class: type,
        params: dict[str, Any],
        timeframe: str = "M15",
        symbol: str = "",
    ) -> BacktestResult:
        """Run a full backtest bar-by-bar.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV data with UTC DatetimeIndex. Must pass validation.
        strategy_class : type
            A BaseStrategy subclass (not an instance).
        params : dict
            Strategy parameters (merged defaults + overrides).
        timeframe : str
            Timeframe label (matches the key used in data dict).
        symbol : str
            Symbol for position sizing and SL/TP.

        Returns
        -------
        BacktestResult
        """
        # ── Validate input data ────────────────────────────────────────────
        if df is None or df.empty:
            log.error("BacktestEngine: empty DataFrame")
            return BacktestResult()

        report = validate(df, symbol=symbol, timeframe=timeframe)
        if not report.is_valid:
            log.error("BacktestEngine: data validation failed: %s", report.issues)
            return BacktestResult()

        n = len(df)
        if n < self.warmup + 1:
            log.error("BacktestEngine: insufficient bars: %d < warmup+1=%d", n, self.warmup + 1)
            return BacktestResult()

        # ── Instantiate strategy ────────────────────────────────────────────
        try:
            strategy = strategy_class(params)
        except Exception as exc:
            log.exception("BacktestEngine: strategy instantiation failed: %s", exc)
            return BacktestResult()

        trades: list[TradeResult] = []
        equity = [self.initial_equity]
        drawdown = [0.0]
        peak = self.initial_equity
        monthly: dict[str, float] = {}

        # Track open position (at most one at a time for simplicity)
        open_trade: TradeResult | None = None

        # ── Bar-by-bar loop — NO LOOK-AHEAD ────────────────────────────────
        # At bar i, only df.iloc[:i+1] is visible to the strategy.
        for i in range(self.warmup, n - 1):
            bar = df.iloc[i]
            bar_ts = df.index[i]

            # ── Check if open position is hit ─────────────────────────────
            if open_trade is not None:
                exit_result = self._check_exit(open_trade, bar, self.execution)
                if exit_result is not None:
                    # Close the trade
                    open_trade.close_price = exit_result["price"]
                    open_trade.exit_time = bar_ts
                    open_trade.pnl_r = exit_result["pnl_r"]
                    open_trade.pnl_dollars = exit_result["pnl_dollars"]
                    open_trade.exit_reason = exit_result["reason"]

                    # Update equity
                    equity.append(equity[-1] + open_trade.pnl_dollars)
                    trades.append(open_trade)

                    # Monthly tracking
                    month_key = bar_ts.strftime("%Y-%m")
                    monthly[month_key] = monthly.get(month_key, 0.0) + open_trade.pnl_r

                    # Drawdown tracking
                    if equity[-1] > peak:
                        peak = equity[-1]
                    dd = (peak - equity[-1]) / peak if peak > 0 else 0.0
                    drawdown.append(dd)

                    open_trade = None
                    continue  # don't open another trade on the same bar

            # ── Generate signal — ONLY past data visible ───────────────────
            # CLAUDE.md rule: slice_data = {tf: df.iloc[:i+1]}
            slice_data = {timeframe: df.iloc[: i + 1].copy()}

            signal = None
            try:
                signal = strategy.generate_signal(slice_data)
            except Exception as exc:
                log.exception("BacktestEngine: signal error at bar %d: %s", i, exc)

            if signal is None:
                # Carry equity forward (no trade)
                equity.append(equity[-1])
                if equity[-1] > peak:
                    peak = equity[-1]
                dd = (peak - equity[-1]) / peak if peak > 0 else 0.0
                drawdown.append(dd)
                continue

            # ── Compute SL/TP from DynamicSLTPModel ───────────────────────
            sltp_result: SLTPResult | None = None
            try:
                sltp_result = self.sltp.compute(
                    df=df.iloc[: i + 1],
                    side=signal.side.value,
                    entry=signal.entry,
                )
            except Exception as exc:
                log.warning("BacktestEngine: SL/TP compute failed at bar %d: %s", i, exc)

            if sltp_result is None or sltp_result.sl is None:
                log.debug("BacktestEngine: trade blocked by SL/TP at bar %d", i)
                equity.append(equity[-1])
                if equity[-1] > peak:
                    peak = equity[-1]
                dd = (peak - equity[-1]) / peak if peak > 0 else 0.0
                drawdown.append(dd)
                continue

            # ── Position sizing ────────────────────────────────────────────
            sl_dist = abs(signal.entry - sltp_result.sl)
            if sl_dist <= 0:
                log.debug("BacktestEngine: zero SL distance at bar %d", i)
                equity.append(equity[-1])
                if equity[-1] > peak:
                    peak = equity[-1]
                dd = (peak - equity[-1]) / peak if peak > 0 else 0.0
                drawdown.append(dd)
                continue

            lot_size = self.sizer.compute(
                account_equity=equity[-1],
                entry=signal.entry,
                sl=sltp_result.sl,
                symbol=symbol,
            )
            if lot_size is None or lot_size <= 0:
                log.debug("BacktestEngine: position sizer returned None at bar %d", i)
                equity.append(equity[-1])
                if equity[-1] > peak:
                    peak = equity[-1]
                dd = (peak - equity[-1]) / peak if peak > 0 else 0.0
                drawdown.append(dd)
                continue

            # ── Open trade ────────────────────────────────────────────────
            risk_per_lot = sl_dist
            risk_amount = lot_size * risk_per_lot * self._contract_size(symbol)

            open_trade = TradeResult(
                entry_time=bar_ts,
                exit_time=bar_ts,
                side=signal.side.value,
                entry=signal.entry,
                sl=sltp_result.sl,
                tp1=sltp_result.tp1,
                tp2=sltp_result.tp2,
                close_price=signal.entry,
                lot_size=lot_size,
                pnl_r=0.0,
                pnl_dollars=0.0,
                exit_reason="open",
                bars_held=0,
                tag=signal.tag or f"{strategy_class.__name__}.{signal.side.value.lower()}",
            )

            # ── Close the equity bar (no PnL yet) ────────────────────────
            equity.append(equity[-1])
            if equity[-1] > peak:
                peak = equity[-1]
            dd = (peak - equity[-1]) / peak if peak > 0 else 0.0
            drawdown.append(dd)

        # ── Close any remaining open trade at last bar ──────────────────────
        if open_trade is not None and n > 0:
            last_bar = df.iloc[-1]
            last_ts = df.index[-1]
            open_trade.close_price = last_bar["close"]
            open_trade.exit_time = last_ts
            open_trade.pnl_r = self._compute_pnl_r(
                open_trade.side, open_trade.entry,
                open_trade.close_price, open_trade.sl, open_trade.tp1, open_trade.tp2,
            )
            open_trade.pnl_dollars = open_trade.pnl_r * (equity[-1] * self.risk_per_trade)
            open_trade.exit_reason = "bar_exit"
            open_trade.bars_held = n - 1
            trades.append(open_trade)
            equity.append(equity[-1] + open_trade.pnl_dollars)
            month_key = last_ts.strftime("%Y-%m")
            monthly[month_key] = monthly.get(month_key, 0.0) + open_trade.pnl_r
            if equity[-1] > peak:
                peak = equity[-1]
            dd = (peak - equity[-1]) / peak if peak > 0 else 0.0
            drawdown.append(dd)

        # ── Compute summary metrics ────────────────────────────────────────
        result = BacktestResult(
            trades=trades,
            equity_curve=equity,
            drawdown_curve=drawdown,
            monthly_returns=monthly,
            n_bars=n,
            initial_equity=self.initial_equity,
            final_equity=equity[-1] if equity else self.initial_equity,
        )
        self._compute_metrics(result)
        return result

    # ── Private helpers ─────────────────────────────────────────────────────


    def _check_exit(
        self, trade: TradeResult, bar: pd.Series, execution: str
    ) -> dict | None:
        """Check if SL/TP1/TP2 is hit on this bar.

        OHLC mode: use bar OHLC to check.
        Every Tick mode: also use bar OHLC (simulated — intrabar resolution unavailable).
        """
        if trade.side == "BUY":
            high = bar["high"]
            low = bar["low"]
        else:
            high = bar["low"]
            low = bar["high"]

        # Check SL first (most dangerous)
        if trade.side == "BUY" and low <= trade.sl:
            return {
                "price": trade.sl,
                "pnl_r": -1.0,
                "pnl_dollars": -equity_at_exit(trade, self.initial_equity, self.risk_per_trade)
                if (equity_at_exit := _eq_helper(trade, self.initial_equity, self.risk_per_trade)) is not None
                else -(trade.lot_size * abs(trade.entry - trade.sl) * self._contract_size(_sym := "")),
                "reason": "sl",
            }
        if trade.side == "SELL" and high >= trade.sl:
            return {
                "price": trade.sl,
                "pnl_r": -1.0,
                "pnl_dollars": -(trade.lot_size * abs(trade.entry - trade.sl) * self._contract_size(_sym)),
                "reason": "sl",
            }

        # Check TP2
        if trade.side == "BUY" and high >= trade.tp2:
            rr2 = abs(trade.tp2 - trade.entry) / abs(trade.sl - trade.entry)
            return {
                "price": trade.tp2,
                "pnl_r": rr2,
                "pnl_dollars": trade.lot_size * (trade.tp2 - trade.entry) * self._contract_size(_sym := symbol_for_sl_tp(trade)),
                "reason": "tp2",
            }
        if trade.side == "SELL" and low <= trade.tp2:
            rr2 = abs(trade.entry - trade.tp2) / abs(trade.sl - trade.entry)
            return {
                "price": trade.tp2,
                "pnl_r": rr2,
                "pnl_dollars": trade.lot_size * (trade.entry - trade.tp2) * self._contract_size(_sym),
                "reason": "tp2",
            }

        # Check TP1 (partial close → move SL to entry, close 50%)
        if trade.side == "BUY" and high >= trade.tp1:
            rr1 = abs(trade.tp1 - trade.entry) / abs(trade.sl - trade.entry)
            net_r = 0.5 * rr1  # 50% closed at TP1, 50% at break-even
            return {
                "price": trade.tp1,
                "pnl_r": net_r,
                "pnl_dollars": trade.lot_size * (trade.tp1 - trade.entry) * 0.5 * self._contract_size(_sym := symbol_for_sl_tp(trade)),
                "reason": "tp1",
            }
        if trade.side == "SELL" and low <= trade.tp1:
            rr1 = abs(trade.entry - trade.tp1) / abs(trade.sl - trade.entry)
            net_r = 0.5 * rr1
            return {
                "price": trade.tp1,
                "pnl_r": net_r,
                "pnl_dollars": trade.lot_size * (trade.entry - trade.tp1) * 0.5 * self._contract_size(_sym),
                "reason": "tp1",
            }

        return None


    def _compute_pnl_r(
        self,
        side: str,
        entry: float,
        close: float,
        sl: float,
        tp1: float,
        tp2: float,
    ) -> float:
        """Compute R-multiple for an exit at `close` price."""
        sl_dist = abs(entry - sl)
        if sl_dist <= 0:
            return 0.0

        if side == "BUY":
            gross_r = (close - entry) / sl_dist
        else:
            gross_r = (entry - close) / sl_dist
        return round(gross_r, 6)


    def _compute_metrics(self, result: BacktestResult) -> None:
        """Fill in summary stats on the BacktestResult."""
        trades = result.trades
        n = len(trades)
        if n == 0:
            return

        wins = [t for t in trades if t.pnl_r > 0]
        losses = [t for t in trades if t.pnl_r < 0]
        result.n_wins = len(wins)
        result.n_losses = len(losses)
        result.win_rate = result.n_wins / n if n else 0.0

        # Net PnL
        result.net_pnl_r = sum(t.pnl_r for t in trades)
        total_r = result.net_pnl_r * (result.initial_equity * self.risk_per_trade)
        result.net_pnl_dollars = total_r
        result.final_equity = result.initial_equity + result.net_pnl_dollars

        # Profit factor
        gross_win = sum(t.pnl_r for t in wins)
        gross_loss = abs(sum(t.pnl_r for t in losses))
        if gross_loss > 0:
            result.profit_factor = round(gross_win / gross_loss, 4)
        else:
            result.profit_factor = None

        # Sharpe (simplified from R-multiples)
        pnl_r_list = [t.pnl_r for t in trades]
        if len(pnl_r_list) > 1:
            mean_r = sum(pnl_r_list) / len(pnl_r_list)
            var_r = sum((r - mean_r) ** 2 for r in pnl_r_list) / (len(pnl_r_list) - 1)
            std_r = var_r ** 0.5
            if std_r > 0:
                result.sharpe_approx = round(mean_r / std_r * (252 ** 0.5), 4)

        # Max drawdown
        if result.drawdown_curve:
            result.max_drawdown = round(max(result.drawdown_curve), 6)

        # Binomial significance test
        try:
            p_val = binomtest(result.n_wins, n, 0.5, alternative="greater").pvalue
            result.p_value = round(float(p_val), 6)
            result.is_significant = result.p_value < config.backtest.significance_threshold
        except Exception:
            pass


    def _contract_size(self, symbol: str) -> float:
        """Return contract size multiplier for PnL calculation."""
        # Forex: 100,000 standard lot; Metals: 100 oz; Crypto: 1 unit
        if symbol in ("XAUUSD", "XAGUSD"):
            return 100.0
        if symbol.endswith("USD") and symbol not in ("BTCUSD", "ETHUSD"):
            return 100_000.0  # forex
        return 1.0  # crypto, equity (simplified)


def _eq_helper(trade, initial, risk_pct):
    """Quick equity after a loss."""
    return initial * risk_pct

def symbol_for_sl_tp(trade: TradeResult) -> str:
    """Extract symbol hint from trade tag for contract size lookup."""
    return ""
