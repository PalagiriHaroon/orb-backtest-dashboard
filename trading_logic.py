import math


def compute_opening_range(
    open_price: float, atr: float, fraction: float = 0.15
) -> tuple[float, float]:
    half = atr * fraction
    return open_price + half, open_price - half


def detect_breakout(
    day_high: float, day_low: float,
    or_high: float, or_low: float,
    bias: str,
) -> bool:
    if bias == "BULLISH":
        return day_high > or_high
    return day_low < or_low


def simulate_retracement_candle(
    or_high: float, or_low: float,
    day_high: float, day_low: float,
    atr: float, bias: str,
    high_frac: float = 0.12,
    low_frac: float = 0.02,
) -> dict | None:
    if bias == "BULLISH":
        retrace_high = or_high + atr * high_frac
        retrace_low = or_high + atr * low_frac
        if retrace_high > day_high or retrace_low < or_high:
            return None
        return {"high": retrace_high, "low": retrace_low}
    else:
        retrace_low = or_low - atr * high_frac
        retrace_high = or_low - atr * low_frac
        if retrace_low < day_low or retrace_high > or_low:
            return None
        return {"high": retrace_high, "low": retrace_low}


def compute_entry_sl_target(
    candle: dict, bias: str,
    sl_buffer_pct: float = 0.15,
    rr_ratio: float = 2.0,
) -> dict | None:
    candle_range = candle["high"] - candle["low"]
    if candle_range <= 0:
        return None

    if bias == "BULLISH":
        entry = candle["high"]
        sl = candle["low"] - sl_buffer_pct * candle_range
        risk = entry - sl
    else:
        entry = candle["low"]
        sl = candle["high"] + sl_buffer_pct * candle_range
        risk = sl - entry

    if risk <= 0:
        return None

    direction = "BUY CE" if bias == "BULLISH" else "BUY PE"
    if direction == "BUY CE":
        target = entry + rr_ratio * risk
    else:
        target = entry - rr_ratio * risk

    return {
        "entry": entry,
        "sl": sl,
        "target": target,
        "risk_per_share": risk,
        "direction": direction,
    }


def estimate_option_premium(stock_price: float, atr: float, fraction: float = 0.4) -> float:
    return atr * fraction


def compute_position_size(max_risk: float, premium: float) -> int:
    if premium <= 0:
        return 0
    return max(1, math.floor(max_risk / premium))


def determine_exit(
    entry: float, sl: float, target: float,
    day_high: float, day_low: float, day_close: float,
    direction: str,
) -> tuple[str, float]:
    if direction == "BUY CE":
        target_hit = day_high >= target
        sl_hit = day_low <= sl
        if target_hit and sl_hit:
            if day_close > entry:
                return "TARGET", target
            return "STOPLOSS", sl
        if target_hit:
            return "TARGET", target
        if sl_hit:
            return "STOPLOSS", sl
        return "TIMESTOP", day_close
    else:
        target_hit = day_low <= target
        sl_hit = day_high >= sl
        if target_hit and sl_hit:
            if day_close < entry:
                return "TARGET", target
            return "STOPLOSS", sl
        if target_hit:
            return "TARGET", target
        if sl_hit:
            return "STOPLOSS", sl
        return "TIMESTOP", day_close


def compute_pnl(
    entry: float, exit_price: float, lots: int, direction: str,
    premium: float = 0.0,
) -> float:
    if direction == "BUY CE":
        raw_pnl = (exit_price - entry) * lots
    else:
        raw_pnl = (entry - exit_price) * lots
    max_loss = -(premium * lots)
    return max(raw_pnl, max_loss)
