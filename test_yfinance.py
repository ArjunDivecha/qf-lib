import pandas as pd
from qf_lib.common.tickers.tickers import YFinanceTicker
from qf_lib.common.enums.price_field import PriceField
from qf_lib.common.utils.dateutils.string_to_date import str_to_date
from qf_lib.data_providers.yfinance.yfinance_data_provider import YFinanceDataProvider

# Test script to verify YFinanceDataProvider is working
def main():
    # Create data provider
    data_provider = YFinanceDataProvider()
    
    # Test with a single ticker
    ticker = YFinanceTicker("SPY")
    start_date = str_to_date("2020-01-03")
    end_date = str_to_date("2020-01-31")
    
    # Get price history
    prices = data_provider.historical_price(ticker, PriceField.Close, 250)
    print(f"Got {len(prices)} price points for {ticker}")
    if len(prices) > 0:
        print(f"Latest price: {prices.iloc[-1]}")
    
    # Test with multiple tickers
    tickers = [YFinanceTicker("SPY"), YFinanceTicker("QQQ")]
    for ticker in tickers:
        try:
            prices = data_provider.historical_price(ticker, PriceField.Close, 250)
            print(f"{ticker}: Got {len(prices)} price points")
        except Exception as e:
            print(f"Error with {ticker}: {e}")

if __name__ == "__main__":
    main()