from dataclasses import dataclass
import datetime
import pandas as pd

from config import MarketConfig, OR_ATR_FRACTION, SL_BUFFER_PCT, RISK_REWARD_RATIO
from trading_logic import (
    compute_opening_range,
    detect_breakout,
    simulate_retracement_candle,
    compute_entry_sl_target,
    compute_position_size,
    determine_exit,
    compute_pnl,
)


@dataclass
class TradeResult:
    date: datetime.date
    market: str
    symbol: str
    bias: str
    direction: str
    or_high: float
    or_low: float
    entry: float
    sl: float
    target: float
    exit_price: float
    exit_reason: str
    shares: int
    risk_amount: float
    pnl: float
    pnl_pct: float


class ORBDaySimulator:
    def __init__(self, config: MarketConfig):
        self.config = config

    def simulate_day(
        self,
        date: pd.Timestamp,
        universe_data: dict[str, pd.DataFrame],
        current_capital: float,
    ) -> tuple[list[TradeResult], str]:
        gainers, losers = self._pre_scan(date, universe_data)
        if not gainers and not losers:
            return [], ""

        bias = self._determine_bias(gainers, losers)
        candidates = self._select_stocks(bias, gainers, losers)

        trades = []
        for ticker, gap_pct, row in candidates[: self.config.max_trades_per_day]:
            trade = self._simulate_stock(date, ticker, row, bias, current_capital)
            if trade:
                trades.append(trade)
                current_capital += trade.pnl

        return trades, bias

    def _pre_scan(self, date, universe_data):
        gainers = []
        losers = []

        for ticker, df in universe_data.items():
            if date not in df.index:
                continue
            row = df.loc[date]
            gap = row.get("GapPct", None)
            atr = row.get("ATR", None)
            if gap is None or atr is None or pd.isna(gap) or pd.isna(atr):
                continue
            if abs(gap) > self.config.gap_threshold:
                continue
            if gap > 0.001:
                gainers.append((ticker, gap, row))
            elif gap < -0.001:
                losers.append((ticker, gap, row))

        gainers.sort(key=lambda x: x[1], reverse=True)
        losers.sort(key=lambda x: x[1])
        return gainers, losers

    def _determine_bias(self, gainers, losers):
        top_g = gainers[:5]
        top_l = losers[:5]
        avg_gain = sum(x[1] for x in top_g) / len(top_g) if top_g else 0
        avg_loss = sum(abs(x[1]) for x in top_l) / len(top_l) if top_l else 0

        if not top_l:
            return "BULLISH"
        if not top_g:
            return "BEARISH"
        return "BULLISH" if avg_gain >= avg_loss else "BEARISH"

    def _select_stocks(self, bias, gainers, losers):
        if bias == "BULLISH":
            return gainers[:3]
        return losers[:3]

    def _simulate_stock(self, date, ticker, row, bias, capital):
        open_p = float(row["Open"])
        high = float(row["High"])
        low = float(row["Low"])
        close = float(row["Close"])
        atr = float(row["ATR"])

        if atr <= 0 or open_p <= 0:
            return None

        or_high, or_low = compute_opening_range(open_p, atr, OR_ATR_FRACTION)

        if not detect_breakout(high, low, or_high, or_low, bias):
            return None

        candle = simulate_retracement_candle(or_high, or_low, high, low, atr, bias)
        if candle is None:
            return None

        setup = compute_entry_sl_target(candle, bias, SL_BUFFER_PCT, RISK_REWARD_RATIO)
        if setup is None:
            return None

        entry = setup["entry"]
        sl = setup["sl"]
        target = setup["target"]
        risk_per_share = setup["risk_per_share"]
        direction = setup["direction"]

        shares = compute_position_size(self.config.max_risk_per_trade, risk_per_share)
        if shares <= 0:
            return None

        exit_reason, exit_price = determine_exit(
            entry, sl, target, high, low, close, direction
        )
        pnl = compute_pnl(entry, exit_price, shares, direction)
        pnl_pct = (pnl / (entry * shares) * 100) if entry * shares > 0 else 0.0

        clean_symbol = ticker.replace(".NS", "")

        return TradeResult(
            date=date.date() if hasattr(date, "date") else date,
            market=self.config.name,
            symbol=clean_symbol,
            bias=bias,
            direction=direction,
            or_high=round(or_high, 2),
            or_low=round(or_low, 2),
            entry=round(entry, 2),
            sl=round(sl, 2),
            target=round(target, 2),
            exit_price=round(exit_price, 2),
            exit_reason=exit_reason,
            shares=shares,
            risk_amount=round(risk_per_share * shares, 2),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
        )
