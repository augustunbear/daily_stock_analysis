# -*- coding: utf-8 -*-
"""
简化版主程序 - 专注于数据获取和展示
"""

import logging
import sys
import os
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def setup_data_source():
    """设置数据源"""
    
    # 直接使用内嵌的模拟数据源
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    
    class InlineMockFetcher:
        name = "InlineMockFetcher"
        priority = 999
        
        def get_daily_data(self, stock_code, start_date=None, end_date=None, days=30):
            logger.info(f"[InlineMockFetcher] Generating mock data for {stock_code}")
            
            # Process date range
            if end_date is None:
                end_date = datetime.now()
            else:
                end_date = pd.to_datetime(end_date)
            
            if start_date is None:
                start_date = end_date - timedelta(days=days*2)
            else:
                start_date = pd.to_datetime(start_date)
            
            # Generate date sequence
            dates = pd.bdate_range(start=start_date, end=end_date)
            dates = dates[-min(len(dates), days):]
            
            # Generate mock price data
            np.random.seed(hash(stock_code) % 2**32)
            
            stock_names = {
                '600519': 'Kweichow Moutai',
                '000001': 'Ping An Bank',
                '300750': 'CATL',
                'AAPL': 'Apple Inc.',
                'TSLA': 'Tesla Inc.',
                'MSFT': 'Microsoft Corporation',
                'VOD.L': 'Vodafone Group',
                'SAP.DE': 'SAP SE',
            }
            
            if stock_code.startswith(('600', '000', '300', '688')):
                base_price = stock_names.get(stock_code, np.random.uniform(10, 500))
            elif stock_code.isalpha():
                base_price = stock_names.get(stock_code, np.random.uniform(50, 1000))
            else:
                base_price = np.random.uniform(10, 500)
            
            # Generate price series
            n_days = len(dates)
            returns = np.random.normal(0, 0.02, n_days)
            returns[0] = 0
            
            prices = [base_price]
            for ret in returns[1:]:
                new_price = prices[-1] * (1 + ret)
                if new_price > 0:
                    prices.append(new_price)
                else:
                    prices.append(prices[-1] * 0.99)
            
            # Generate OHLC data
            data = []
            for i, date in enumerate(dates):
                close_price = prices[i]
                daily_vol = abs(np.random.normal(0, 0.02))
                high = close_price * (1 + daily_vol)
                low = close_price * (1 - daily_vol)
                open_price = low + (high - low) * np.random.random()
                
                high = max(high, open_price, close_price)
                low = min(low, open_price, close_price)
                
                volume = int(np.random.uniform(1000000, 50000000))
                
                data.append({
                    'date': date,
                    'open': float(round(open_price, 2)),
                    'high': float(round(high, 2)),
                    'low': float(round(low, 2)),
                    'close': float(round(close_price, 2)),
                    'volume': int(volume),
                    'amount': float(volume * close_price),
                    'pct_chg': float(round(returns[i] * 100, 2))
                })
            
            df = pd.DataFrame(data)
            
            # Add technical indicators
            df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
            df['ma10'] = df['close'].rolling(window=10, min_periods=1).mean()
            df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
            
            avg_volume = df['volume'].rolling(window=5, min_periods=1).mean()
            df['volume_ratio'] = df['volume'] / avg_volume.shift(1)
            df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
            
            logger.info(f"[InlineMockFetcher] Successfully generated {stock_code} data: {len(df)} records, latest price {df['close'].iloc[-1]:.2f}")
            
            return df
        
        def get_realtime_quote(self, stock_code):
            stock_names = {
                '600519': 'Kweichow Moutai',
                '000001': 'Ping An Bank',
                '300750': 'CATL',
                'AAPL': 'Apple Inc.',
                'TSLA': 'Tesla Inc.',
                'MSFT': 'Microsoft Corporation',
            }
            
            name = stock_names.get(stock_code, f'Stock {stock_code}')
            
            df = self.get_daily_data(stock_code, days=1)
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                price = latest['close']
                change_pct = latest['pct_chg']
                volume = latest['volume']
            else:
                price = 100.0
                change_pct = 0.0
                volume = 5000000
            
            return {
                'code': stock_code,
                'name': name,
                'price': round(price, 2),
                'change_pct': round(change_pct, 2),
                'volume': int(volume),
                'source': self.name
            }
    
    # Create mock manager
    class MockManager:
        def __init__(self):
            self._fetchers = [InlineMockFetcher()]
        
        @property
        def available_fetchers(self):
            return [f.name for f in self._fetchers]
        
        def get_daily_data(self, stock_code, **kwargs):
            return self._fetchers[0].get_daily_data(stock_code, **kwargs)
        
        def get_realtime_quote(self, stock_code):
            return self._fetchers[0].get_realtime_quote(stock_code)
    
    try:
        manager = MockManager()
        logger.info(f"Mock data source setup successful: {manager.available_fetchers}")
        return manager, "InlineMock"
    except Exception as e:
        logger.error(f"Mock data source setup failed: {e}")
        return None, "Failed"

def format_stock_info(stock_code, df, source):
    """Format stock information"""
    if df is None or df.empty:
        return f"ERROR: {stock_code}: Data retrieval failed"
    
    # Basic info
    latest = df.iloc[-1]
    info = []
    
    # Header
    info.append(f"Stock: {stock_code} Data Report")
    info.append(f"Data source: {source}")
    info.append(f"Data records: {len(df)}")
    info.append("")
    
    # Price info
    info.append("Price information:")
    info.append(f"   Latest price: {latest['close']:.2f}")
    info.append(f"   Daily change: {latest['pct_chg']:+.2f}%")
    info.append(f"   Open: {latest['open']:.2f}")
    info.append(f"   High: {latest['high']:.2f}")
    info.append(f"   Low: {latest['low']:.2f}")
    info.append("")
    
    # Volume info
    info.append("Volume information:")
    info.append(f"   Volume: {latest['volume']:,}")
    info.append(f"   Amount: {latest['amount']:,.0f}")
    info.append(f"   Volume ratio: {latest.get('volume_ratio', 1.0):.2f}")
    info.append("")
    
    # Technical indicators
    info.append("Technical indicators:")
    info.append(f"   MA5: {latest['ma5']:.2f}")
    info.append(f"   MA10: {latest['ma10']:.2f}")
    info.append(f"   MA20: {latest['ma20']:.2f}")
    info.append("")
    
    # Trend analysis
    ma5 = latest['ma5']
    ma10 = latest['ma10']
    ma20 = latest['ma20']
    close = latest['close']
    
    trend_info = []
    if close > ma5 > ma10 > ma20:
        trend_info.append("Bullish alignment")
        trend = "Uptrend"
    elif close < ma5 < ma10 < ma20:
        trend_info.append("Bearish alignment")
        trend = "Downtrend"
    else:
        trend_info.append("Consolidation")
        trend = "Sideways"
    
    info.append("Trend analysis:")
    info.extend(f"   {item}" for item in trend_info)
    info.append(f"   Current trend: {trend}")
    info.append("")
    
    # Time range
    date_range = f"{df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}"
    info.append(f"Time range: {date_range}")
    info.append("")
    
    # Price reasonableness check
    price = latest['close']
    stock_names = {
        '600519': 'Kweichow Moutai',
        '000001': 'Ping An Bank',
        '300750': 'CATL',
        'AAPL': 'Apple Inc.',
        'TSLA': 'Tesla Inc.',
        'MSFT': 'Microsoft Corporation',
        'VOD.L': 'Vodafone Group',
        'SAP.DE': 'SAP SE',
    }
    
    stock_name = stock_names.get(stock_code, f"Stock {stock_code}")
    
    if stock_code.startswith(('600', '000', '300', '688')):  # A-shares
        if 10 <= price <= 500:
            price_check = "Price normal"
        else:
            price_check = f"WARNING: Price abnormal: {price:.2f} (normal range: 10-500)"
    elif stock_code.isalpha():  # US stocks
        if 10 <= price <= 2000:
            price_check = "Price normal"
        else:
            price_check = f"WARNING: Price abnormal: ${price:.2f} (normal range: $10-2000)"
    else:  # Other
        price_check = "Unknown price range"
    
    info.append("Data quality check:")
    info.append(f"   {price_check}")
    info.append(f"   Company name: {stock_name}")
    
    return "\n".join(info)

def analyze_single_stock(manager, stock_code):
    """Analyze single stock"""
    logger.info(f"Starting analysis of {stock_code}")
    
    try:
        # Get data
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        df, source = manager.get_daily_data(stock_code, start_date=start_date, end_date=end_date, days=30)
        
        # Format and output info
        report = format_stock_info(stock_code, df, source)
        print(report)
        
        # Try to get real-time quote
        if hasattr(manager, 'get_realtime_quote'):
            quote = manager.get_realtime_quote(stock_code)
            if quote:
                print(f"Real-time quote: {quote['name']} ({quote['code']})")
                print(f"   Current price: {quote['price']:.2f}")
                print(f"   Daily change: {quote['change_pct']:+.2f}%")
                print(f"   Data source: {quote.get('source', 'Unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"Analysis of {stock_code} failed: {e}")
        return False

def main():
    """Main function"""
    print("Stock Data Acquisition and Analysis Tool")
    print("=" * 50)
    
    # Setup data source
    manager, source_type = setup_data_source()
    if manager is None:
        print("Failed to setup data source, program exit")
        return
    
    # Test stock list
    test_stocks = [
        "600519",  # Kweichow Moutai - A-share
        "000001",  # Ping An Bank - A-share
        "300750",  # CATL - A-share
        "AAPL",    # Apple - US stock
        "TSLA",    # Tesla - US stock
        "VOD.L",   # Vodafone - UK stock
        "SAP.DE",  # SAP - German stock
    ]
    
    print(f"\nStarting analysis of {len(test_stocks)} stocks")
    print("=" * 50)
    
    success_count = 0
    total_count = len(test_stocks)
    
    for i, stock in enumerate(test_stocks, 1):
        print(f"\n[{i}/{total_count}] Currently analyzing: {stock}")
        print("-" * 40)
        
        if analyze_single_stock(manager, stock):
            success_count += 1
    
    # Summary report
    print("\n" + "=" * 50)
    print("Analysis Summary")
    print("=" * 50)
    print(f"Successfully analyzed: {success_count}/{total_count} stocks")
    print(f"Data source type: {source_type}")
    
    if success_count == total_count:
        print("All stocks analyzed successfully!")
    else:
        print(f"Warning: {total_count - success_count} stocks failed analysis")
    
    print("\nNotes:")
    print("- Currently using mock data for demonstration")
    print("- To get real data, please install corresponding dependency packages")
    print("- For real data source configuration, please refer to documentation")

if __name__ == "__main__":
    main()