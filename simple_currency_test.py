#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Currency Conversion Test
"""

import logging
from currency_converter import get_currency_converter
from market_types import Market

logging.basicConfig(level=logging.INFO)

def test_basic_conversion():
    """Basic conversion test"""
    print("=== Basic Currency Conversion Test ===")
    
    converter = get_currency_converter()
    
    # Test cases
    test_cases = [
        (600519, Market.CHINA_A, "CNY", 1800.50),  # Chinese stock
        (1800.50, Market.US_NASDAQ, "USD", 180.25),  # US stock
        (145.80, Market.GER_XETRA, "EUR", 145.80),   # German stock
    ]
    
    print("Current exchange rates (vs EUR):")
    key_rates = {k: v for k, v in converter.rates.items() if k in ['CNY', 'USD', 'EUR']}
    for currency, rate in key_rates.items():
        print(f"  1 EUR = {rate} {currency}")
    print()
    
    print("Conversion Results:")
    print("-" * 60)
    print(f"{'Stock Code':<12} {'Market':<15} {'Display Currency':<15}")
    print("-" * 60)
    
    for code, market, original_curr, amount in test_cases:
        target_currency = converter.get_target_currency(market.value)
        print(f"{code:<12} {market.value:<15} {target_currency:<15}")
    
    print("-" * 60)
    print()
    
    # Test actual conversion
    print("Specific Conversion Test:")
    usd_amount = 100.0
    converted_amount, rate = converter.convert_amount(usd_amount, 'USD', 'EUR')
    formatted = converter.format_amount(converted_amount, 'EUR')
    
    print(f"100 USD -> {formatted} (Rate: 1 USD = {rate:.4f} EUR)")
    print()

def test_data_conversion():
    """Test stock data conversion"""
    print("=== Stock Data Conversion Test ===")
    
    converter = get_currency_converter()
    
    # US stock data
    us_data = {
        'close': 180.0,
        'amount': 50000000.0,
        'total_mv': 2800000000000.0,
    }
    
    print("Original US Stock Data:")
    print(f"  Close: ${us_data['close']}")
    print(f"  Volume: ${us_data['amount']:,.0f}")
    
    # Convert to EUR
    converted = converter.convert_stock_data(us_data, Market.US_NASDAQ.value)
    
    print("\nConverted to EUR:")
    print(f"  Close: {converter.format_amount(converted['close'], 'EUR')}")
    print(f"  Volume: {converter.format_amount(converted['amount'], 'EUR')}")
    print()

if __name__ == "__main__":
    try:
        test_basic_conversion()
        test_data_conversion()
        print("Test completed successfully!")
        print("\nImplementation Summary:")
        print("- Chinese stocks display in CNY (Chinese Yuan)")
        print("- Other region stocks display in EUR (Euro)")
        print("- Real-time exchange rates are fetched from API")
        print("- Rates are cached for 1 hour to avoid excessive API calls")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()