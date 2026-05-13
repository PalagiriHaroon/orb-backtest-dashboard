import datetime
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich.text import Text
from rich import box

from config import INDIA_CONFIG, USA_CONFIG, DB_PATH, BACKTEST_YEARS
from models import initialize_db, BacktestRun
from data_loader import download_universe
from backtest_engine import MarketState
from market_agent import MarketAgent
from dashboard import Dashboard


def main():
    console = Console(force_terminal=True, color_system="auto")
    console.clear()

    banner = Text()
    banner.append("\n  ORB BACKTEST ENGINE\n", style="bold cyan")
    banner.append(f"  Opening Range Breakout | {BACKTEST_YEARS}-Year Backtest\n", style="dim")
    banner.append(f"  India (NSE) + USA (NYSE/NASDAQ)\n", style="dim")
    console.print(Panel(banner, box=box.DOUBLE, border_style="cyan"))

    console.print("\n[bold]Initializing database...[/bold]")
    initialize_db(DB_PATH)

    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=BACKTEST_YEARS * 365)

    run_record = BacktestRun.create(
        period_start=start_date,
        period_end=end_date,
        india_starting_capital=INDIA_CONFIG.starting_capital,
        usa_starting_capital=USA_CONFIG.starting_capital,
    )

    india_data = {}
    usa_data = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        india_task = progress.add_task(
            "[blue]Downloading India (NSE) data...", total=100
        )
        usa_task = progress.add_task(
            "[green]Downloading USA (NYSE) data...", total=100
        )

        def india_progress(done, total):
            progress.update(india_task, completed=int(done / total * 100))

        def usa_progress(done, total):
            progress.update(usa_task, completed=int(done / total * 100))

        console.print(f"\n[dim]Fetching {len(INDIA_CONFIG.universe)} India tickers...[/dim]")
        india_data = download_universe(
            INDIA_CONFIG.universe, BACKTEST_YEARS, india_progress
        )
        progress.update(india_task, completed=100)
        console.print(f"[green]  India: {len(india_data)} tickers loaded[/green]")

        console.print(f"[dim]Fetching {len(USA_CONFIG.universe)} USA tickers...[/dim]")
        usa_data = download_universe(
            USA_CONFIG.universe, BACKTEST_YEARS, usa_progress
        )
        progress.update(usa_task, completed=100)
        console.print(f"[green]  USA: {len(usa_data)} tickers loaded[/green]")

    if not india_data and not usa_data:
        console.print("[bold red]No data downloaded. Check internet connection.[/bold red]")
        return

    console.print(f"\n[bold cyan]Starting backtest ({start_date} -> {end_date})...[/bold cyan]")
    console.print("[dim]Dashboard launching in 2 seconds...[/dim]\n")

    import time
    time.sleep(2)

    india_state = MarketState(
        market_name="India",
        currency_symbol=INDIA_CONFIG.currency_symbol,
        capital=INDIA_CONFIG.starting_capital,
        starting_capital=INDIA_CONFIG.starting_capital,
        peak_capital=INDIA_CONFIG.starting_capital,
    )

    usa_state = MarketState(
        market_name="USA",
        currency_symbol=USA_CONFIG.currency_symbol,
        capital=USA_CONFIG.starting_capital,
        starting_capital=USA_CONFIG.starting_capital,
        peak_capital=USA_CONFIG.starting_capital,
    )

    india_agent = MarketAgent(INDIA_CONFIG, india_data, india_state, run_record.id)
    usa_agent = MarketAgent(USA_CONFIG, usa_data, usa_state, run_record.id)

    india_agent.start()
    usa_agent.start()

    dashboard = Dashboard(india_state, usa_state)
    dashboard.run()

    india_agent.join(timeout=5)
    usa_agent.join(timeout=5)

    run_record.india_final_capital = india_state.capital
    run_record.usa_final_capital = usa_state.capital
    run_record.india_total_trades = india_state.total_trades
    run_record.usa_total_trades = usa_state.total_trades
    run_record.status = "COMPLETED"
    run_record.save()

    console.clear()
    console.print(Panel(
        Text("\n  BACKTEST COMPLETE\n", style="bold green"),
        box=box.DOUBLE,
        border_style="green",
    ))

    summary = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    summary.add_column("Metric", style="dim")
    summary.add_column("India (NSE)", justify="right")
    summary.add_column("USA (NYSE)", justify="right")

    from rich.table import Table

    summary.add_row("Starting Capital",
                     f"₹{INDIA_CONFIG.starting_capital:,.0f}",
                     f"${USA_CONFIG.starting_capital:,.0f}")
    summary.add_row("Final Capital",
                     f"₹{india_state.capital:,.2f}",
                     f"${usa_state.capital:,.2f}")
    summary.add_row("P&L",
                     f"₹{india_state.total_pnl:,.2f}",
                     f"${usa_state.total_pnl:,.2f}")
    summary.add_row("Return %",
                     f"{india_state.total_pnl / INDIA_CONFIG.starting_capital * 100:.1f}%",
                     f"{usa_state.total_pnl / USA_CONFIG.starting_capital * 100:.1f}%")
    summary.add_row("Total Trades",
                     str(india_state.total_trades),
                     str(usa_state.total_trades))
    summary.add_row("Wins / Losses",
                     f"{india_state.wins} / {india_state.losses}",
                     f"{usa_state.wins} / {usa_state.losses}")
    summary.add_row("Win Rate",
                     f"{india_state.win_rate}%",
                     f"{usa_state.win_rate}%")
    summary.add_row("Time Stops",
                     str(india_state.timestops),
                     str(usa_state.timestops))

    console.print(summary)
    console.print(f"\n[dim]Results saved to {DB_PATH}[/dim]")
    console.print("[dim]Press Ctrl+C to exit.[/dim]\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
