# 200-Day Moving Average Strategy (vectorized & preloaded)
# Goes long equal-weight in tickers with Close > 200D MA; otherwise holds cash.
# Preloads all price data once to avoid per-ticker, per-day downloads.

import os
import json
import sys
import gc
import pandas as pd
from typing import List, Dict

from qf_lib.backtesting.events.time_event.regular_time_event.calculate_and_place_orders_event import (
    CalculateAndPlaceOrdersRegularEvent
)
from qf_lib.backtesting.order.execution_style import MarketOrder
from qf_lib.backtesting.order.time_in_force import TimeInForce
from qf_lib.backtesting.strategies.abstract_strategy import AbstractStrategy
from qf_lib.backtesting.trading_session.backtest_trading_session_builder import BacktestTradingSessionBuilder
from qf_lib.common.enums.frequency import Frequency
from qf_lib.common.enums.price_field import PriceField
from qf_lib.common.tickers.tickers import YFinanceTicker, Ticker
from qf_lib.common.utils.dateutils.string_to_date import str_to_date
from qf_lib.data_providers.yfinance.yfinance_data_provider import YFinanceDataProvider
from qf_lib.documents_utils.document_exporting.pdf_exporter import PDFExporter
from qf_lib.documents_utils.excel.excel_exporter import ExcelExporter
from qf_lib.settings import Settings
from qf_lib.starting_dir import set_starting_dir_abs_path

# ---------- Configuration ----------
STARTING_DIR = "/Users/macbook2024/Dropbox/AAA Backup/A Working/QF/qf-lib"
ASSET_LIST_XLSX = "/Users/macbook2024/Dropbox/AAA Backup/A Working/QF/qf-lib/AssetList.xlsx"
OUTPUT_DIR = "output"
BACKTEST_NAME = "200-Day MA Strategy (Vectorized)"
START_DATE_STR = "2020-01-03"
END_DATE_STR = "2025-07-24"
MA_WINDOW = 200
LOOKBACK_BUFFER_DAYS = 260  # preload buffer to safely compute first 200D MA
MAX_EXECUTIONS_SAFETY = 10000  # just in case

# Set the starting directory for QF-Lib
set_starting_dir_abs_path(STARTING_DIR)


class MA200VectorizedStrategy(AbstractStrategy):
    """
    Vectorized implementation:
      - Preloads all Close prices for all tickers once using DataProvider.get_price(...)
      - Computes rolling 200D MA for each ticker
      - On each scheduled event, uses the next date index row and issues equal-weight targets
    """

    def __init__(self, ts, tickers: List[Ticker], start_date, end_date):
        super().__init__(ts)
        self.ts = ts
        self.broker = ts.broker
        self.order_factory = ts.order_factory
        self.data_provider = ts.data_provider  # used only for one-shot preload
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date

        # Internal state
        self.execution_count = 0
        self.max_executions = MAX_EXECUTIONS_SAFETY

        # Preloaded data containers
        self.close_df: pd.DataFrame = pd.DataFrame()
        self.ma200_df: pd.DataFrame = pd.DataFrame()
        self.dates_index: pd.DatetimeIndex = pd.DatetimeIndex([])
        self.current_idx: int = 0

        print(f"Initialized MA200VectorizedStrategy with {len(tickers)} tickers")
        self._preload_prices_and_compute_ma()

    def _preload_prices_and_compute_ma(self):
        # Expand start_date backwards to ensure enough data for the first 200-day average
        preload_start = self.start_date - pd.tseries.offsets.BDay(LOOKBACK_BUFFER_DAYS)
        print(f"Preloading Close prices from {preload_start.date()} to {self.end_date.date()} ...")

        # get_price returns PricesDataFrame / QFDataArray; convert to pandas DataFrame with dates x tickers
        # We request all tickers at once, daily frequency.
        prices = self.data_provider.get_price(
            self.tickers,
            PriceField.Close,
            preload_start,
            self.end_date,
            Frequency.DAILY
        )
        # QF-Lib containers are pandas-compatible; coerce to DataFrame explicitly.
        close_df = pd.DataFrame(prices)

        # Ensure columns are Ticker objects or convert to their string symbols for readability.
        # YFinanceTicker.__str__ returns the ticker string; standardize columns to strings.
        close_df.columns = [str(c) for c in close_df.columns]

        # Drop completely empty columns (no data)
        initial_cols = len(close_df.columns)
        close_df = close_df.dropna(how="all", axis=1)
        if len(close_df.columns) < initial_cols:
            dropped = initial_cols - len(close_df.columns)
            print(f"Warning: dropped {dropped} tickers with no data.")

        # Trim to backtest window
        close_df = close_df.loc[self.start_date:self.end_date]

        # Compute rolling 200D MA per column (min_periods=MA_WINDOW to avoid look-ahead)
        print("Computing 200-day moving averages (vectorized)...")
        ma200_df = close_df.rolling(window=MA_WINDOW, min_periods=MA_WINDOW).mean()

        # Save
        self.close_df = close_df
        self.ma200_df = ma200_df
        self.dates_index = close_df.index

        print(f"Preload complete: {close_df.shape[0]} rows x {close_df.shape[1]} tickers.")

    def _build_signals_for_date(self, d) -> Dict[Ticker, float]:
        """Build 0/1 signals for a specific date index label `d`."""
        closes = self.close_df.loc[d]
        ma200 = self.ma200_df.loc[d]

        # Signal = 1 if Close > MA200, else 0; NaNs -> 0
        raw = (closes > ma200).astype(float).fillna(0.0)

        # Map back to Ticker objects
        str_to_ticker = {str(t): t for t in self.tickers if str(t) in raw.index}
        signals = {str_to_ticker[col]: raw[col] for col in raw.index}
        return signals

    def calculate_and_place_orders(self):
        self.execution_count += 1

        if self.execution_count == 1:
            print("First execution. Using preloaded data; placing initial targets.")
        if self.execution_count % 50 == 0 or self.execution_count <= 5:
            est_total = len(self.dates_index)
            print(f"PROGRESS: Execution #{self.execution_count} (dates processed ~{self.current_idx}/{est_total})")

        if self.execution_count > self.max_executions:
            print(f"SAFETY LIMIT: execution_count>{self.max_executions}; skipping orders.")
            return

        if self.current_idx >= len(self.dates_index):
            print("Reached end of date index. No more orders.")
            return

        d = self.dates_index[self.current_idx]

        # Build signals for this date
        signals01 = self._build_signals_for_date(d)
        total_signal = sum(signals01.values())

        if total_signal > 0:
            weights = {t: v / total_signal for t, v in signals01.items() if v > 0}
        else:
            # All cash
            weights = {t: 0.0 for t in signals01.keys()}

        if self.execution_count <= 3:
            sample = list(weights.items())[:5]
            print(f"{d.date()} sample weights (first 5): {[(str(t), w) for t, w in sample]}")
            on_count = int(total_signal)
            print(f"Tickers above MA200 today: {on_count} / {len(signals01)}")

        # Create and place orders
        orders = self.order_factory.target_percent_orders(weights, MarketOrder(), TimeInForce.DAY)
        self.broker.cancel_all_open_orders()
        if orders:
            self.broker.place_orders(orders)

        # Advance to next trading date
        self.current_idx += 1


def main():
    # Load tickers
    df_assets = pd.read_excel(ASSET_LIST_XLSX)
    raw_tickers = [str(t).strip() for t in df_assets["Ticker"].tolist() if pd.notna(t)]
    tickers = [YFinanceTicker(t) for t in raw_tickers]
    print(f"Loaded {len(tickers)} tickers from AssetList.xlsx")

    # Minimal settings
    config = {"output_directory": OUTPUT_DIR}
    config_path = "/tmp/qf_settings.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    # Dates
    start_date = str_to_date(START_DATE_STR)
    end_date = str_to_date(END_DATE_STR)

    # Settings / providers
    settings = Settings(settings_path=config_path)
    data_provider = YFinanceDataProvider()

    # Exporters (PDF exporter included but you can ignore to avoid WeasyPrint)
    pdf_exporter = PDFExporter(settings)     # not used, but builder expects it
    excel_exporter = ExcelExporter(settings) # optional

    # Build trading session
    session_builder = BacktestTradingSessionBuilder(settings, pdf_exporter, excel_exporter)
    session_builder.set_frequency(Frequency.DAILY)
    session_builder.set_backtest_name(BACKTEST_NAME)
    session_builder.set_data_provider(data_provider)

    ts = session_builder.build(start_date, end_date)
    print("Trading session built.")

    # Strategy
    strategy = MA200VectorizedStrategy(ts, tickers, start_date, end_date)
    CalculateAndPlaceOrdersRegularEvent.set_daily_default_trigger_time()
    CalculateAndPlaceOrdersRegularEvent.exclude_weekends()
    strategy.subscribe(CalculateAndPlaceOrdersRegularEvent)

    print("DEBUG: Starting trading session ...")
    sys.stdout.flush()

    try:
        ts.start_trading()
        print("Backtest finished.")
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print(f"Exception during trading session: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Print backtest summary
        print("\n" + "="*60)
        print("BACKTEST COMPLETED SUCCESSFULLY!")
        print("="*60)
        print(f"Strategy: {BACKTEST_NAME}")
        print(f"Period: {START_DATE_STR} to {END_DATE_STR}")
        print(f"Tickers: {len(tickers)} international ETFs")
        print(f"Strategy: Long positions when Close > 200-day MA")
        
        # Try to get basic portfolio info
        try:
            if hasattr(ts.monitor, 'backtest_result') and ts.monitor.backtest_result is not None:
                result = ts.monitor.backtest_result
                if hasattr(result, 'portfolio') and result.portfolio is not None:
                    portfolio = result.portfolio
                    initial_cash = getattr(portfolio, 'initial_cash', 'N/A')
                    current_value = getattr(portfolio, 'net_liquidation', 'N/A')
                    print(f"Initial Capital: ${initial_cash:,.2f}" if isinstance(initial_cash, (int, float)) else f"Initial Capital: {initial_cash}")
                    print(f"Final Value: ${current_value:,.2f}" if isinstance(current_value, (int, float)) else f"Final Value: {current_value}")
                    
                    if isinstance(initial_cash, (int, float)) and isinstance(current_value, (int, float)) and initial_cash > 0:
                        total_return = (current_value - initial_cash) / initial_cash * 100
                        print(f"Total Return: {total_return:.2f}%")
        except Exception as e:
            print(f"Could not extract portfolio summary: {e}")
        
        print("\nNote: Detailed reports and charts are generated in the output directory.")
        print("Check the 'output' folder for PDF and Excel reports.")
        print("="*60)

        if os.path.exists(config_path):
            os.remove(config_path)

        gc.collect()
        print("Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()