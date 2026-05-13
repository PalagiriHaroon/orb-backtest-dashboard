import time
import yfinance as yf
import pandas as pd
import numpy as np
from config import ATR_PERIOD


def compute_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["PrevClose"] = df["Close"].shift(1)
    df["GapPct"] = (df["Open"] - df["PrevClose"]) / df["PrevClose"]
    high_low = df["High"] - df["Low"]
    high_pc = (df["High"] - df["PrevClose"]).abs()
    low_pc = (df["Low"] - df["PrevClose"]).abs()
    df["TR"] = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(window=ATR_PERIOD, min_periods=ATR_PERIOD).mean()
    df.dropna(subset=["ATR", "PrevClose"], inplace=True)
    return df


def download_universe(
    tickers: list[str], years: int = 5, progress_callback=None
) -> dict[str, pd.DataFrame]:
    result = {}
    chunk_size = 25
    chunks = [tickers[i : i + chunk_size] for i in range(0, len(tickers), chunk_size)]
    total_chunks = len(chunks)

    for idx, chunk in enumerate(chunks):
        try:
            raw = yf.download(
                chunk,
                period=f"{years}y",
                group_by="ticker",
                threads=True,
                progress=False,
            )
            if raw.empty:
                continue

            if len(chunk) == 1:
                ticker = chunk[0]
                df = raw.copy()
                if len(df) >= 200:
                    df = compute_derived_columns(df)
                    if not df.empty:
                        result[ticker] = df
            else:
                for ticker in chunk:
                    try:
                        if ticker in raw.columns.get_level_values(0):
                            df = raw[ticker].dropna(how="all").copy()
                            if len(df) >= 200:
                                df = compute_derived_columns(df)
                                if not df.empty:
                                    result[ticker] = df
                    except (KeyError, TypeError):
                        continue
        except Exception:
            continue

        if progress_callback:
            progress_callback(idx + 1, total_chunks)
        time.sleep(0.3)

    return result


def get_trading_dates(data: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    all_dates = set()
    for df in data.values():
        all_dates.update(df.index.tolist())
    return sorted(all_dates)
