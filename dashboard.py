import time
import plotext as plt

from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich import box

from backtest_engine import MarketState


class Dashboard:
    def __init__(self, india_state: MarketState, usa_state: MarketState):
        self.india = india_state
        self.usa = usa_state
        self.console = Console(force_terminal=True, color_system="auto")

    def build_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="body", ratio=3),
            Layout(name="footer", size=16),
        )
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        layout["footer"].split_row(
            Layout(name="chart_equity"),
            Layout(name="chart_drawdown"),
        )

        layout["header"].update(self._build_header())

        layout["left"].update(self._build_market_panel(self.india))
        layout["right"].update(self._build_market_panel(self.usa))

        layout["chart_equity"].update(self._build_equity_chart())
        layout["chart_drawdown"].update(self._build_drawdown_chart())

        return layout

    def _build_header(self) -> Panel:
        india_pct = int(self.india.progress * 100)
        usa_pct = int(self.usa.progress * 100)

        status = "COMPLETE" if self.india.is_complete and self.usa.is_complete else "RUNNING"

        header_text = Text()
        header_text.append("  ORB BACKTEST DASHBOARD", style="bold cyan")
        header_text.append("  |  Status: ", style="dim")
        color = "green" if status == "COMPLETE" else "yellow"
        header_text.append(status, style=f"bold {color}")
        header_text.append("\n")
        header_text.append(f"  India [{self.india.current_date}] ", style="blue")
        header_text.append(f"{india_pct}%", style="bold blue")
        header_text.append(f"  |  USA [{self.usa.current_date}] ", style="green")
        header_text.append(f"{usa_pct}%", style="bold green")

        return Panel(header_text, box=box.DOUBLE, style="bright_white")

    def _build_market_panel(self, state: MarketState) -> Panel:
        stats = Text()
        bias_color = "green" if state.bias == "BULLISH" else "red"
        stats.append(" Bias: ", style="dim")
        stats.append(f"{state.bias or '---'}", style=f"bold {bias_color}")

        cap = state.capital
        cap_color = "green" if cap >= state.starting_capital else "red"
        stats.append("  Capital: ", style="dim")
        stats.append(f"{state.currency_symbol}{cap:,.0f}", style=f"bold {cap_color}")
        stats.append("\n")

        stats.append(f" T:{state.total_trades}", style="bold white")
        stats.append(f" W:{state.wins}", style="bold green")
        stats.append(f" L:{state.losses}", style="bold red")
        stats.append(f" TS:{state.timestops}", style="bold yellow")
        wr_color = "green" if state.win_rate >= 50 else ("yellow" if state.win_rate >= 40 else "red")
        stats.append(f"  WR:{state.win_rate}%", style=f"bold {wr_color}")

        pnl_color = "green" if state.total_pnl >= 0 else "red"
        sign = "+" if state.total_pnl >= 0 else ""
        stats.append(f"  P&L:{sign}{state.currency_symbol}{state.total_pnl:,.0f}", style=f"bold {pnl_color}")

        table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style="bold cyan",
            expand=True,
            padding=(0, 0),
        )
        table.add_column("#", width=3, justify="right", style="dim")
        table.add_column("Date", width=6)
        table.add_column("Sym", width=8)
        table.add_column("Dir", width=4)
        table.add_column("Entry", justify="right", width=7)
        table.add_column("SL", justify="right", width=7)
        table.add_column("TP", justify="right", width=7)
        table.add_column("P&L", justify="right", width=8)
        table.add_column("Res", width=4)

        trades = list(state.recent_trades)

        for i, t in enumerate(reversed(trades[-10:])):
            if t.exit_reason == "TARGET":
                row_style = "green"
                result_text = "W"
            elif t.exit_reason == "STOPLOSS":
                row_style = "red"
                result_text = "L"
            else:
                row_style = "yellow"
                result_text = "T"

            pnl_str = f"{'+' if t.pnl >= 0 else ''}{t.pnl:,.0f}"
            date_str = str(t.date)
            short_date = date_str[5:10] if len(date_str) >= 10 else date_str

            table.add_row(
                str(len(trades) - i),
                short_date,
                t.symbol[:8],
                t.direction[:1],
                f"{t.entry:.1f}",
                f"{t.sl:.1f}",
                f"{t.target:.1f}",
                pnl_str,
                result_text,
                style=row_style,
            )

        title = "INDIA NSE" if state.market_name == "India" else "USA NYSE/NASDAQ"
        border = "blue" if state.market_name == "India" else "green"

        return Panel(
            Group(stats, table),
            title=f"[bold]{title}[/bold]",
            border_style=border,
            box=box.ROUNDED,
        )

    def _build_equity_chart(self) -> Panel:
        try:
            plt.clf()
            plt.clear_figure()
            plt.theme("dark")
            plt.plot_size(None, 12)

            with self.india.lock:
                india_eq = list(self.india.equity_curve)
            with self.usa.lock:
                usa_eq = list(self.usa.equity_curve)

            has_data = False

            if len(india_eq) > 2:
                step = max(1, len(india_eq) // 60)
                sampled = india_eq[::step]
                y = [p[1] for p in sampled]
                plt.plot(list(range(len(y))), y, label="India", color="blue")
                has_data = True

            if len(usa_eq) > 2:
                step = max(1, len(usa_eq) // 60)
                sampled = usa_eq[::step]
                y = [p[1] for p in sampled]
                plt.plot(list(range(len(y))), y, label="USA", color="green")
                has_data = True

            if not has_data:
                return Panel(
                    Text("  Waiting for data...", style="dim"),
                    title="[bold]Equity (% Return)[/bold]",
                    border_style="cyan",
                )

            plt.title("")
            plt.xlabel("")
            plt.ylabel("")
            chart_str = plt.build()
            return Panel(
                Text.from_ansi(chart_str),
                title="[bold]Equity (% Return)[/bold]",
                border_style="cyan",
            )
        except Exception:
            return Panel(
                Text("  Rendering...", style="dim"),
                title="[bold]Equity[/bold]",
                border_style="cyan",
            )

    def _build_drawdown_chart(self) -> Panel:
        try:
            plt.clf()
            plt.clear_figure()
            plt.theme("dark")
            plt.plot_size(None, 12)

            with self.india.lock:
                india_dd = list(self.india.drawdown_curve)
            with self.usa.lock:
                usa_dd = list(self.usa.drawdown_curve)

            has_data = False

            if len(india_dd) > 2:
                step = max(1, len(india_dd) // 60)
                sampled = india_dd[::step]
                y = [-p[1] for p in sampled]
                plt.plot(list(range(len(y))), y, label="India", color="blue")
                has_data = True

            if len(usa_dd) > 2:
                step = max(1, len(usa_dd) // 60)
                sampled = usa_dd[::step]
                y = [-p[1] for p in sampled]
                plt.plot(list(range(len(y))), y, label="USA", color="red")
                has_data = True

            if not has_data:
                return Panel(
                    Text("  Waiting for data...", style="dim"),
                    title="[bold]Drawdown %[/bold]",
                    border_style="magenta",
                )

            plt.title("")
            plt.xlabel("")
            plt.ylabel("")
            chart_str = plt.build()
            return Panel(
                Text.from_ansi(chart_str),
                title="[bold]Drawdown %[/bold]",
                border_style="magenta",
            )
        except Exception:
            return Panel(
                Text("  Rendering...", style="dim"),
                title="[bold]Drawdown %[/bold]",
                border_style="magenta",
            )

    def run(self):
        with Live(
            self.build_layout(),
            refresh_per_second=4,
            console=self.console,
            screen=True,
        ) as live:
            while not (self.india.is_complete and self.usa.is_complete):
                try:
                    live.update(self.build_layout())
                except Exception:
                    pass
                time.sleep(0.25)

            live.update(self.build_layout())
            time.sleep(3)
