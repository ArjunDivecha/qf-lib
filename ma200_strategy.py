# 200-Day Moving Average Strategy Implementation
# Goes long when asset is above 200-day MA, otherwise holds cash

import os
import json
import pandas as pd

from qf_lib.backtesting.events.time_event.regular_time_event.calculate_and_place_orders_event import \
    CalculateAndPlaceOrdersRegularEvent
from qf_lib.backtesting.order.execution_style import MarketOrder
from qf_lib.backtesting.order.time_in_force import TimeInForce
from qf_lib.backtesting.strategies.abstract_strategy import AbstractStrategy
from qf_lib.backtesting.trading_session.backtest_trading_session_builder import BacktestTradingSessionBuilder
from qf_lib.common.enums.frequency import Frequency
from qf_lib.common.enums.price_field import PriceField
from qf_lib.common.tickers.tickers import YFinanceTicker
from qf_lib.common.utils.dateutils.string_to_date import str_to_date
from qf_lib.data_providers.yfinance.yfinance_data_provider import YFinanceDataProvider
from qf_lib.documents_utils.document_exporting.pdf_exporter import PDFExporter
from qf_lib.documents_utils.excel.excel_exporter import ExcelExporter
from qf_lib.settings import Settings
from qf_lib.starting_dir import set_starting_dir_abs_path

# Set the starting directory
set_starting_dir_abs_path("/Users/macbook2024/Dropbox/AAA Backup/A Working/QF/qf-lib")

class MA200Strategy(AbstractStrategy):
    """
    Strategy that goes long when an asset is above its 200-day moving average and holds cash otherwise.
    """
    
    def __init__(self, ts, tickers):
        super().__init__(ts)
        self.broker = ts.broker
        self.order_factory = ts.order_factory
        self.data_provider = ts.data_provider
        self.tickers = tickers
        print(f"Initialized strategy with {len(tickers)} tickers")

    def calculate_and_place_orders(self):
        print("calculate_and_place_orders called")
        # Get current positions
        positions = self.broker.get_positions()
        current_positions = {p.ticker(): p.quantity() for p in positions}
        print(f"Current positions: {current_positions}")
        
        # Calculate signals for each ticker
        signals = {}
        successful_tickers = 0
        for ticker in self.tickers:
            try:
                # Get price history (need at least 200 days)
                prices = self.data_provider.historical_price(ticker, PriceField.Close, 250)
                
                # Calculate 200-day moving average
                if len(prices) >= 200:
                    ma_200 = prices.tail(200).mean()
                    current_price = prices.iloc[-1]
                    
                    # Generate signal: 1.0 if above MA, 0.0 if below
                    signals[ticker] = 1.0 if current_price > ma_200 else 0.0
                    print(f"{ticker}: Price={current_price:.2f}, MA200={ma_200:.2f}, Signal={signals[ticker]}")
                    successful_tickers += 1
                else:
                    # Not enough data - hold cash
                    signals[ticker] = 0.0
                    print(f"{ticker}: Not enough data ({len(prices)} points), Signal=0.0")
            except Exception as e:
                # In case of any error, hold cash for this ticker
                print(f"Error processing {ticker}: {e}")
                signals[ticker] = 0.0
        
        print(f"Successfully processed {successful_tickers} out of {len(self.tickers)} tickers")
        
        # Normalize signals to equal weight
        total_signal = sum(signals.values())
        if total_signal > 0:
            normalized_signals = {ticker: signal/total_signal for ticker, signal in signals.items() if signal > 0}
        else:
            normalized_signals = {ticker: 0.0 for ticker in self.tickers}
        
        print(f"Normalized signals: {normalized_signals}")
        
        # Create orders based on signals
        orders = self.order_factory.target_percent_orders(normalized_signals, MarketOrder(), TimeInForce.DAY)
        
        # Cancel any open orders and place the newly created ones
        self.broker.cancel_all_open_orders()
        if orders:
            print(f"Placing {len(orders)} orders")
            self.broker.place_orders(orders)
        else:
            print("No orders to place")

def main():
    # Read tickers from AssetList.xlsx
    df = pd.read_excel('/Users/macbook2024/Dropbox/AAA Backup/A Working/QF/qf-lib/AssetList.xlsx')
    tickers = [YFinanceTicker(ticker) for ticker in df['Ticker'].tolist()]
    print(f"Loaded {len(tickers)} tickers from AssetList.xlsx")
    
    # Create minimal settings configuration
    config = {
        "output_directory": "output"
    }
    
    # Write config to temporary file
    config_path = "/tmp/qf_settings.json"
    with open(config_path, 'w') as f:
        json.dump(config, f)
    
    # Settings
    backtest_name = '200-Day MA Strategy'
    start_date = str_to_date("2020-01-03")
    end_date = str_to_date("2025-07-24")  # Current date

    # Create settings object
    settings = Settings(settings_path=config_path)
    
    # Create data provider
    data_provider = YFinanceDataProvider()
    
    # Create exporters
    pdf_exporter = PDFExporter(settings)
    excel_exporter = ExcelExporter(settings)

    # Build the trading session
    session_builder = BacktestTradingSessionBuilder(settings, pdf_exporter, excel_exporter)
    session_builder.set_frequency(Frequency.DAILY)
    session_builder.set_backtest_name(backtest_name)
    session_builder.set_data_provider(data_provider)

    ts = session_builder.build(start_date, end_date)
    print("Trading session built")

    # Create and run strategy
    strategy = MA200Strategy(ts, tickers)
    CalculateAndPlaceOrdersRegularEvent.set_daily_default_trigger_time()
    CalculateAndPlaceOrdersRegularEvent.exclude_weekends()
    strategy.subscribe(CalculateAndPlaceOrdersRegularEvent)
    
    print("Starting trading session...")
    ts.start_trading()
    print("Trading session completed.")
    
    # Clean up temporary config file
    os.remove(config_path)
    
    # Ensure proper exit
    import sys
    sys.exit(0)

if __name__ == "__main__":
    main()