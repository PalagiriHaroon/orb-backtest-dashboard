from dataclasses import dataclass, field

BACKTEST_YEARS = 5
ATR_PERIOD = 14
RISK_REWARD_RATIO = 2.0
SL_BUFFER_PCT = 0.15
OR_ATR_FRACTION = 0.15
RETRACEMENT_ATR_HIGH = 0.12
RETRACEMENT_ATR_LOW = 0.02
PREMIUM_ATR_FRACTION = 0.4
DB_PATH = "backtest_results.db"


@dataclass
class MarketConfig:
    name: str
    currency_symbol: str
    starting_capital: float
    risk_per_trade_pct: float
    max_trades_per_day: int
    gap_threshold: float
    universe: list[str] = field(default_factory=list)


INDIA_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "WIPRO.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "BAJFINANCE.NS", "HCLTECH.NS", "NTPC.NS",
    "POWERGRID.NS", "TITAN.NS", "ONGC.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS",
    "JSWSTEEL.NS", "TATASTEEL.NS", "COALINDIA.NS", "TECHM.NS", "NESTLEIND.NS",
    "BAJAJFINSV.NS", "DRREDDY.NS", "CIPLA.NS", "BPCL.NS", "GRASIM.NS",
    "DIVISLAB.NS", "EICHERMOT.NS", "INDUSINDBK.NS", "TATACONSUM.NS",
    "APOLLOHOSP.NS", "BRITANNIA.NS", "HEROMOTOCO.NS", "VEDL.NS", "HINDALCO.NS",
    "M&M.NS", "DABUR.NS", "GODREJCP.NS", "PIDILITIND.NS", "SIEMENS.NS",
    "HAVELLS.NS", "TRENT.NS", "BANKBARODA.NS", "IOC.NS", "ADANIENT.NS",
    "HDFCLIFE.NS", "SBILIFE.NS", "ICICIPRULI.NS", "PNB.NS", "CANBK.NS",
    "RECLTD.NS", "PFC.NS", "BHEL.NS", "IRFC.NS", "HAL.NS", "BEL.NS",
    "JIOFIN.NS", "SHRIRAMFIN.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS",
    "TATAPOWER.NS", "NHPC.NS", "GAIL.NS", "SAIL.NS", "IDFCFIRSTB.NS",
]

USA_UNIVERSE = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "BRK-B",
    "UNH", "JNJ", "JPM", "V", "PG", "XOM", "HD", "CVX", "MA", "ABBV",
    "MRK", "PEP", "KO", "LLY", "AVGO", "COST", "TMO", "MCD", "WMT",
    "ACN", "CSCO", "DHR", "ABT", "CRM", "NKE", "ADBE", "TXN", "PM",
    "NEE", "UPS", "RTX", "HON", "LOW", "QCOM", "INTC", "AMGN", "BA",
    "CAT", "GS", "BLK", "ISRG", "SYK", "ADP", "MDLZ", "AMD", "DE",
    "GILD", "BKNG", "PYPL", "T", "VZ", "CL", "DUK", "SO", "PNC",
    "USB", "SCHW", "MS", "AXP", "SPGI", "CB", "CME", "NOW",
    "ORCL", "IBM", "UBER",
]

INDIA_CONFIG = MarketConfig(
    name="India",
    currency_symbol="₹",
    starting_capital=100_000.0,
    risk_per_trade_pct=0.04,
    max_trades_per_day=3,
    gap_threshold=0.03,
    universe=INDIA_UNIVERSE,
)

USA_CONFIG = MarketConfig(
    name="USA",
    currency_symbol="$",
    starting_capital=1_000.0,
    risk_per_trade_pct=0.04,
    max_trades_per_day=3,
    gap_threshold=0.03,
    universe=USA_UNIVERSE,
)
