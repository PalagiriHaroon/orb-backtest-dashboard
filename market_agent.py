import threading
import pandas as pd

from config import MarketConfig
from backtest_engine import BacktestEngine, MarketState


class MarketAgent(threading.Thread):
    def __init__(
        self,
        config: MarketConfig,
        data: dict[str, pd.DataFrame],
        state: MarketState,
        run_id: int,
    ):
        super().__init__(daemon=True)
        self.config = config
        self.data = data
        self.state = state
        self.run_id = run_id
        self.error: Exception | None = None

    def run(self):
        try:
            engine = BacktestEngine(self.config, self.data, self.state, self.run_id)
            engine.run()
        except Exception as e:
            self.error = e
            with self.state.lock:
                self.state.is_complete = True
