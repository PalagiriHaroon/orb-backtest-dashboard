import threading
import time
from dataclasses import dataclass, field

import pandas as pd

from config import MarketConfig
from orb_simulator import ORBDaySimulator, TradeResult
from data_loader import get_trading_dates
from models import Trade, DailyEquity, BacktestRun


@dataclass
class MarketState:
    market_name: str
    currency_symbol: str = ""
    current_date: str = ""
    bias: str = ""
    capital: float = 0.0
    starting_capital: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    timestops: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    recent_trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    drawdown_curve: list = field(default_factory=list)
    peak_capital: float = 0.0
    is_complete: bool = False
    progress: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


class BacktestEngine:
    def __init__(
        self,
        config: MarketConfig,
        data: dict[str, pd.DataFrame],
        state: MarketState,
        run_id: int,
    ):
        self.config = config
        self.data = data
        self.state = state
        self.run_id = run_id
        self.simulator = ORBDaySimulator(config)
        self.capital = config.starting_capital
        self.peak_capital = config.starting_capital
        self.dates = get_trading_dates(data)

    def run(self):
        total_days = len(self.dates)
        if total_days == 0:
            with self.state.lock:
                self.state.is_complete = True
            return

        for i, date in enumerate(self.dates):
            trades, bias = self.simulator.simulate_day(date, self.data, self.capital)

            for t in trades:
                self.capital += t.pnl
                self.capital = round(self.capital, 2)

            if self.capital > self.peak_capital:
                self.peak_capital = self.capital

            dd_pct = 0.0
            if self.peak_capital > 0:
                dd_pct = round(
                    (self.peak_capital - self.capital) / self.peak_capital * 100, 2
                )

            date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)

            self._update_state(date_str, trades, bias, dd_pct, (i + 1) / total_days)
            self._save_to_db(trades, date_str, dd_pct)

            time.sleep(0.015)

        with self.state.lock:
            self.state.is_complete = True

    def _update_state(self, date_str, trades, bias, dd_pct, progress):
        with self.state.lock:
            self.state.current_date = date_str
            if bias:
                self.state.bias = bias
            self.state.capital = self.capital
            self.state.progress = progress

            for t in trades:
                self.state.total_trades += 1
                if t.exit_reason == "TARGET":
                    self.state.wins += 1
                elif t.exit_reason == "STOPLOSS":
                    self.state.losses += 1
                else:
                    self.state.timestops += 1

            if self.state.total_trades > 0:
                self.state.win_rate = round(
                    self.state.wins / self.state.total_trades * 100, 1
                )

            self.state.total_pnl = round(
                self.capital - self.state.starting_capital, 2
            )

            for t in trades:
                self.state.recent_trades.append(t)
            self.state.recent_trades = self.state.recent_trades[-15:]

            pct_return = round(
                (self.capital - self.state.starting_capital)
                / self.state.starting_capital
                * 100,
                2,
            )
            self.state.equity_curve.append((date_str, pct_return))
            self.state.drawdown_curve.append((date_str, dd_pct))

    def _save_to_db(self, trades, date_str, dd_pct):
        try:
            for t in trades:
                Trade.create(
                    run=self.run_id,
                    date=t.date,
                    market=t.market,
                    symbol=t.symbol,
                    bias=t.bias,
                    direction=t.direction,
                    or_high=t.or_high,
                    or_low=t.or_low,
                    entry=t.entry,
                    sl=t.sl,
                    target=t.target,
                    exit_price=t.exit_price,
                    exit_reason=t.exit_reason,
                    shares=t.shares,
                    risk_amount=t.risk_amount,
                    pnl=t.pnl,
                    pnl_pct=t.pnl_pct,
                    capital_after=self.capital,
                )
            DailyEquity.create(
                run=self.run_id,
                date=date_str,
                market=self.config.name,
                capital=self.capital,
                drawdown_pct=dd_pct,
                trades_today=len(trades),
                bias=trades[0].bias if trades else None,
            )
        except Exception:
            pass
