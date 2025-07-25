# Example using yfinance data with a simple moving average strategy

import matplotlib.pyplot as plt
import os
import json

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

plt.ion()  # required for dynamic chart, keep before other imports

class SimpleMAStrategy(AbstractStrategy):
    """
    Simple moving average strategy using yfinance data.
    Buys when short-term MA crosses above long-term MA, sells when it crosses below.
    """

    def __init__(self, ts, ticker):
        super().__init__(ts)
        self.broker = ts.broker
        self.order_factory = ts.order_factory
        self.data_provider = ts.data_provider
        self.ticker = ticker

    def calculate_and_place_orders(self):
        # Compute the moving averages
        long_ma_len = 20
        short_ma_len = 5

        # Use data handler to download last 20 daily close prices and use them to compute the moving averages
        long_ma_series = self.data_provider.historical_price(self.ticker, PriceField.Close, long_ma_len)
        long_ma_price = long_ma_series.mean()

        short_ma_series = long_ma_series.tail(short_ma_len)
        short_ma_price = short_ma_series.mean()

        # Get current positions
        positions = self.broker.get_positions()
        # Check if we have a position in our ticker
        current_position = next((p for p in positions if p.ticker() == self.ticker), None)
        
        # If we have a position, check if we should exit
        if current_position and abs(current_position.quantity()) > 0:
            if short_ma_price < long_ma_price:
                # Place a sell Market Order, adjusting the position to zero
                orders = self.order_factory.target_percent_orders({self.ticker: 0.0}, 
                                                                 MarketOrder(), TimeInForce.DAY)
                self.broker.place_orders(orders)
        else:
            # If we don't have a position, check if we should enter
            if short_ma_price > long_ma_price:
                # Place a buy Market Order, adjusting the position to 100% of the portfolio
                orders = self.order_factory.target_percent_orders({self.ticker: 1.0}, 
                                                                 MarketOrder(), TimeInForce.DAY)
                self.broker.place_orders(orders)

def main():
    # Create minimal settings configuration
    config = {
        "output_directory": "output"
    }
    
    # Write config to temporary file
    config_path = "/tmp/qf_settings.json"
    with open(config_path, 'w') as f:
        json.dump(config, f)
    
    # settings
    backtest_name = 'Simple MA Strategy with YFinance Data'
    start_date = str_to_date("2020-01-01")
    end_date = str_to_date("2023-12-31")
    ticker = YFinanceTicker("AAPL")

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

    # Create and run strategy
    strategy = SimpleMAStrategy(ts, ticker)
    CalculateAndPlaceOrdersRegularEvent.set_daily_default_trigger_time()
    CalculateAndPlaceOrdersRegularEvent.exclude_weekends()
    strategy.subscribe(CalculateAndPlaceOrdersRegularEvent)

    ts.start_trading()
    
    # Clean up temporary config file
    os.remove(config_path)

if __name__ == "__main__":
    main()
