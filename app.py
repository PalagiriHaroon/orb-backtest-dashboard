import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import time
import threading

from config import INDIA_CONFIG, USA_CONFIG, BACKTEST_YEARS, DB_PATH, MarketConfig
from models import initialize_db, BacktestRun
from data_loader import download_universe, get_trading_dates
from orb_simulator import ORBDaySimulator

st.set_page_config(
    page_title="ORB Backtest Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
    .main > div { padding-top: 1rem; }
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #0f3460;
        text-align: center;
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; }
    .metric-label { font-size: 0.8rem; color: #8892b0; }
    .win { color: #00d4aa; }
    .loss { color: #ff6b6b; }
    .neutral { color: #ffd93d; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 10px;
        padding: 10px 15px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a2e;
        border-radius: 8px;
        padding: 8px 16px;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def make_config(base_config, starting_capital, risk_pct):
    return MarketConfig(
        name=base_config.name,
        currency_symbol=base_config.currency_symbol,
        starting_capital=starting_capital,
        risk_per_trade_pct=risk_pct,
        max_trades_per_day=base_config.max_trades_per_day,
        gap_threshold=base_config.gap_threshold,
        universe=base_config.universe,
    )


def run_backtest_for_market(config, data, results_dict, key):
    sim = ORBDaySimulator(config)
    dates = get_trading_dates(data)
    capital = config.starting_capital
    peak = capital
    trades_list = []
    equity = []
    drawdown = []
    total = wins = losses = timestops = 0

    for i, d in enumerate(dates):
        day_trades, bias = sim.simulate_day(d, data, capital)
        for t in day_trades:
            capital += t.pnl
            capital = round(capital, 2)
            total += 1
            if t.exit_reason == "TARGET":
                wins += 1
            elif t.exit_reason == "STOPLOSS":
                losses += 1
            else:
                timestops += 1
            trades_list.append({
                "Date": str(t.date),
                "Symbol": t.symbol,
                "Option": t.option_type,
                "Direction": t.direction,
                "Bias": t.bias,
                "Entry": t.entry,
                "SL": t.sl,
                "Target": t.target,
                "Exit": t.exit_price,
                "Premium": t.premium,
                "Lots": t.lots,
                "P&L": t.pnl,
                "Result": t.exit_reason,
            })

        if capital > peak:
            peak = capital
        dd = round((peak - capital) / peak * 100, 2) if peak > 0 else 0
        pct_ret = round((capital - config.starting_capital) / config.starting_capital * 100, 2)
        date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
        equity.append({"date": date_str, "return_pct": pct_ret, "capital": capital})
        drawdown.append({"date": date_str, "drawdown": dd})

        results_dict[key] = {
            "capital": capital,
            "total": total,
            "wins": wins,
            "losses": losses,
            "timestops": timestops,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "pnl": round(capital - config.starting_capital, 2),
            "trades": trades_list.copy(),
            "equity": equity.copy(),
            "drawdown": drawdown.copy(),
            "progress": (i + 1) / len(dates),
            "current_date": date_str,
            "peak": peak,
        }

    results_dict[key]["complete"] = True


def render_market_metrics(state, config):
    c1, c2, c3, c4, c5 = st.columns(5)
    pnl = state.get("pnl", 0)
    with c1:
        st.metric("Capital", f"{config.currency_symbol}{state.get('capital', config.starting_capital):,.0f}",
                   delta=f"{config.currency_symbol}{pnl:,.0f}")
    with c2:
        st.metric("Total Trades", state.get("total", 0))
    with c3:
        wr = state.get("win_rate", 0)
        st.metric("Win Rate", f"{wr}%",
                   delta=f"{state.get('wins', 0)}W / {state.get('losses', 0)}L")
    with c4:
        st.metric("Time Stops", state.get("timestops", 0))
    with c5:
        peak = state.get("peak", config.starting_capital)
        cap = state.get("capital", config.starting_capital)
        dd = round((peak - cap) / peak * 100, 1) if peak > 0 else 0
        st.metric("Max Drawdown", f"{dd}%")


def render_trades_table(trades, config):
    if not trades:
        st.info("No trades yet...")
        return

    df = pd.DataFrame(trades)

    def color_result(val):
        if val == "TARGET":
            return "background-color: rgba(0, 212, 170, 0.2); color: #00d4aa"
        elif val == "STOPLOSS":
            return "background-color: rgba(255, 107, 107, 0.2); color: #ff6b6b"
        return "background-color: rgba(255, 217, 61, 0.2); color: #ffd93d"

    def color_pnl(val):
        if val > 0:
            return "color: #00d4aa"
        elif val < 0:
            return "color: #ff6b6b"
        return ""

    styled = df.style.map(color_result, subset=["Result"])
    styled = styled.map(color_pnl, subset=["P&L"])
    styled = styled.format({
        "Entry": "{:.2f}",
        "SL": "{:.2f}",
        "Target": "{:.2f}",
        "Exit": "{:.2f}",
        "Premium": "{:.2f}",
        "P&L": "{:+,.2f}",
    })

    st.dataframe(
        styled,
        use_container_width=True,
        height=400,
        column_config={
            "P&L": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def build_equity_chart(india_eq, usa_eq):
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Equity Curve (% Return)", "Drawdown %"),
        row_heights=[0.6, 0.4],
    )

    if india_eq:
        df_i = pd.DataFrame(india_eq)
        fig.add_trace(go.Scatter(
            x=df_i["date"], y=df_i["return_pct"],
            name="India",
            line=dict(color="#3b82f6", width=2),
            fill="tozeroy",
            fillcolor="rgba(59, 130, 246, 0.1)",
        ), row=1, col=1)

    if usa_eq:
        df_u = pd.DataFrame(usa_eq)
        fig.add_trace(go.Scatter(
            x=df_u["date"], y=df_u["return_pct"],
            name="USA",
            line=dict(color="#10b981", width=2),
            fill="tozeroy",
            fillcolor="rgba(16, 185, 129, 0.1)",
        ), row=1, col=1)

    return fig


def build_full_chart(india_state, usa_state):
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Equity Curve (% Return)", "Drawdown %"),
        row_heights=[0.6, 0.4],
    )

    india_eq = india_state.get("equity", [])
    usa_eq = usa_state.get("equity", [])
    india_dd = india_state.get("drawdown", [])
    usa_dd = usa_state.get("drawdown", [])

    if india_eq:
        df = pd.DataFrame(india_eq)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["return_pct"],
            name="India (Equity)",
            line=dict(color="#3b82f6", width=2),
            fill="tozeroy",
            fillcolor="rgba(59, 130, 246, 0.1)",
        ), row=1, col=1)

    if usa_eq:
        df = pd.DataFrame(usa_eq)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["return_pct"],
            name="USA (Equity)",
            line=dict(color="#10b981", width=2),
            fill="tozeroy",
            fillcolor="rgba(16, 185, 129, 0.1)",
        ), row=1, col=1)

    if india_dd:
        df = pd.DataFrame(india_dd)
        fig.add_trace(go.Scatter(
            x=df["date"], y=[-d for d in df["drawdown"]],
            name="India (DD)",
            line=dict(color="#3b82f6", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(59, 130, 246, 0.1)",
        ), row=2, col=1)

    if usa_dd:
        df = pd.DataFrame(usa_dd)
        fig.add_trace(go.Scatter(
            x=df["date"], y=[-d for d in df["drawdown"]],
            name="USA (DD)",
            line=dict(color="#ef4444", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(239, 68, 68, 0.1)",
        ), row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=550,
        margin=dict(l=50, r=20, t=40, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(26,26,46,0.8)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(255,255,255,0.05)")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(255,255,255,0.05)")
    fig.update_yaxes(title_text="Return %", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown %", row=2, col=1)

    return fig


def main():
    st.title("📈 ORB Backtest Dashboard")
    st.caption(f"Opening Range Breakout Strategy | {BACKTEST_YEARS}-Year Backtest | Options Only (Buy CE/PE)")

    st.sidebar.header("Settings")
    risk_pct = st.sidebar.slider("Risk per Trade (%)", min_value=1, max_value=10, value=4, step=1) / 100
    st.sidebar.divider()
    st.sidebar.subheader("India")
    india_capital = st.sidebar.number_input("Starting Capital (₹)", min_value=10_000, max_value=10_000_000, value=100_000, step=10_000)
    st.sidebar.subheader("USA")
    usa_capital = st.sidebar.number_input("Starting Capital ($)", min_value=100, max_value=1_000_000, value=1_000, step=100)
    st.sidebar.divider()
    st.sidebar.caption("Options only — Buy CE (bullish) / Buy PE (bearish). No leverage. Max loss = premium paid.")

    india_cfg = make_config(INDIA_CONFIG, float(india_capital), risk_pct)
    usa_cfg = make_config(USA_CONFIG, float(usa_capital), risk_pct)

    if "results" not in st.session_state:
        st.session_state.results = {}
    if "running" not in st.session_state:
        st.session_state.running = False
    if "complete" not in st.session_state:
        st.session_state.complete = False
    if "india_data" not in st.session_state:
        st.session_state.india_data = None
    if "usa_data" not in st.session_state:
        st.session_state.usa_data = None

    if not st.session_state.complete:
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            run_btn = st.button("🚀 Run Backtest", type="primary", use_container_width=True)
        with col_info:
            st.info(f"Downloads {len(india_cfg.universe)} India + {len(usa_cfg.universe)} USA tickers, then backtests {BACKTEST_YEARS} years of daily data. Risk: {risk_pct*100:.0f}% per trade.")

        if run_btn and not st.session_state.running:
            st.session_state.running = True
            st.session_state.complete = False
            st.session_state.results = {}

            status = st.status("Downloading market data...", expanded=True)

            with status:
                st.write("Fetching India (NSE) tickers...")
                prog_india = st.progress(0, text="India: starting...")
                india_data = download_universe(
                    india_cfg.universe, BACKTEST_YEARS,
                    lambda done, total: prog_india.progress(done / total, text=f"India: {done}/{total} chunks")
                )
                prog_india.progress(1.0, text=f"India: {len(india_data)} tickers loaded")

                st.write("Fetching USA (NYSE/NASDAQ) tickers...")
                prog_usa = st.progress(0, text="USA: starting...")
                usa_data = download_universe(
                    usa_cfg.universe, BACKTEST_YEARS,
                    lambda done, total: prog_usa.progress(done / total, text=f"USA: {done}/{total} chunks")
                )
                prog_usa.progress(1.0, text=f"USA: {len(usa_data)} tickers loaded")

                status.update(label="Data downloaded! Running backtest...", state="running")

                st.write("Running India backtest...")
                results = {}
                run_backtest_for_market(india_cfg, india_data, results, "india")
                st.write(f"India complete: {results['india']['total']} trades")

                st.write("Running USA backtest...")
                run_backtest_for_market(usa_cfg, usa_data, results, "usa")
                st.write(f"USA complete: {results['usa']['total']} trades")

                status.update(label="Backtest complete!", state="complete")

            st.session_state.results = results
            st.session_state.complete = True
            st.session_state.running = False
            st.rerun()

    if st.session_state.complete and st.session_state.results:
        results = st.session_state.results
        india = results.get("india", {})
        usa = results.get("usa", {})

        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=BACKTEST_YEARS * 365)
        st.markdown(f"**Backtest Period:** `{start_date}` to `{end_date}`")

        st.divider()

        india_col, usa_col = st.columns(2)

        with india_col:
            st.subheader("🇮🇳 India NSE")
            render_market_metrics(india, india_cfg)

        with usa_col:
            st.subheader("🇺🇸 USA NYSE/NASDAQ")
            render_market_metrics(usa, usa_cfg)

        st.divider()

        st.subheader("Performance & Drawdown")
        chart = build_full_chart(india, usa)
        st.plotly_chart(chart, use_container_width=True)

        st.divider()

        st.subheader("Trade Log")
        tab_india, tab_usa, tab_all = st.tabs(["🇮🇳 India Trades", "🇺🇸 USA Trades", "📊 Combined"])

        with tab_india:
            render_trades_table(india.get("trades", []), india_cfg)

        with tab_usa:
            render_trades_table(usa.get("trades", []), usa_cfg)

        with tab_all:
            all_trades = []
            for t in india.get("trades", []):
                t_copy = t.copy()
                t_copy["Market"] = "India"
                all_trades.append(t_copy)
            for t in usa.get("trades", []):
                t_copy = t.copy()
                t_copy["Market"] = "USA"
                all_trades.append(t_copy)
            if all_trades:
                df = pd.DataFrame(all_trades).sort_values("Date", ascending=False)
                st.dataframe(df, use_container_width=True, height=500)

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("India Summary")
            summary_india = {
                "Starting Capital": f"₹{india_cfg.starting_capital:,.0f}",
                "Final Capital": f"₹{india.get('capital', 0):,.0f}",
                "Net P&L": f"₹{india.get('pnl', 0):,.0f}",
                "Return %": f"{india.get('pnl', 0) / india_cfg.starting_capital * 100:.1f}%",
                "Total Trades": str(india.get("total", 0)),
                "Win Rate": f"{india.get('win_rate', 0)}%",
                "Wins / Losses": f"{india.get('wins', 0)} / {india.get('losses', 0)}",
                "Risk per Trade": f"{risk_pct*100:.0f}%",
            }
            for k, v in summary_india.items():
                st.markdown(f"**{k}:** {v}")

        with col2:
            st.subheader("USA Summary")
            summary_usa = {
                "Starting Capital": f"${usa_cfg.starting_capital:,.0f}",
                "Final Capital": f"${usa.get('capital', 0):,.0f}",
                "Net P&L": f"${usa.get('pnl', 0):,.0f}",
                "Return %": f"{usa.get('pnl', 0) / usa_cfg.starting_capital * 100:.1f}%",
                "Total Trades": str(usa.get("total", 0)),
                "Win Rate": f"{usa.get('win_rate', 0)}%",
                "Wins / Losses": f"{usa.get('wins', 0)} / {usa.get('losses', 0)}",
                "Risk per Trade": f"{risk_pct*100:.0f}%",
            }
            for k, v in summary_usa.items():
                st.markdown(f"**{k}:** {v}")

        st.divider()
        st.caption("📊 ORB Backtest Dashboard | Paper Trading Only | Data from Yahoo Finance")

        if st.button("🔄 Re-run Backtest"):
            st.session_state.complete = False
            st.session_state.results = {}
            st.session_state.running = False
            st.rerun()


if __name__ == "__main__":
    main()
