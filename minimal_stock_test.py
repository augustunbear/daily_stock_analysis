# -*- coding: utf-8 -*-
"""
最简化的股票数据测试
展示每个股票的基本信息和价格走势
"""

import sys
from datetime import datetime, timedelta

def generate_stock_data(stock_code, days=10):
    """生成简单的股票数据"""
    print(f"Generating data for {stock_code}...")
    
    # 简单的股票名称映射
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
    
    name = stock_names.get(stock_code, f'Stock {stock_code}')
    
    # 生成日期
    end_date = datetime.now()
    dates = []
    for i in range(days):
        date = end_date - timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))
    
    dates.reverse()  # 从最早到最新
    
    # 生成价格数据（简单递增）
    if stock_code.startswith(('600', '000', '300', '688')):  # A股
        base_price = 150.0 if stock_code == '600519' else 20.0
        price_change = 5.0 if stock_code == '600519' else 2.0
    elif stock_code.isalpha():  # 美股
        base_price = 150.0 if stock_code == 'AAPL' else 80.0
        price_change = 3.0 if stock_code == 'AAPL' else 5.0
    else:  # 其他
        base_price = 100.0
        price_change = 2.0
    
    prices = []
    current_price = base_price
    
    for i in range(days):
        # 模拟价格波动
        change = (hash(stock_code + str(i)) % 20 - 10) / 100.0 * price_change
        current_price = max(1.0, current_price * (1 + change))
        prices.append(round(current_price, 2))
    
    # 生成其他数据
    data = []
    for i in range(days):
        price = prices[i]
        # 模拟成交量（基于价格变化）
        volume = int(1000000 + hash(stock_code + str(i)) % 5000000)
        
        data.append({
            'date': dates[i],
            'open': price,
            'high': price * 1.02,
            'low': price * 0.98,
            'close': price,
            'volume': volume,
            'pct_change': round((price - (prices[i-1] if i > 0 else price)) / (prices[i-1] if i > 0 else price) * 100, 2),
        'ma5': round(sum(prices[max(0, i-4):i+1]) / min(i+1, 5), 2),
        'ma10': round(sum(prices[max(0, i-9):i+1]) / min(i+1, 10), 2),
        'ma20': round(sum(prices[max(0, i-19):i+1]) / min(i+1, 20), 2)
        })
    
    return data, name

def analyze_stock(stock_code):
    """分析单只股票"""
    try:
        data, name = generate_stock_data(stock_code, days=30)
        
        print(f"Stock: {name} ({stock_code})")
        print(f"Source: Mock Data Generator")
        print(f"Records: {len(data)}")
        print(f"Date range: {data[0]['date']} to {data[-1]['date']}")
        
        latest = data[-1]
        print(f"Latest price: {latest['close']:.2f}")
        print(f"Daily change: {latest['pct_change']:+.2f}%")
        print(f"MA5: {latest['ma5']:.2f}")
        print(f"MA10: {latest['ma10']:.2f}")
        print(f"MA20: {latest['ma20']:.2f}")
        print(f"Volume: {latest['volume']:,}")
        
        # 趋势分析
        ma5, ma10, ma20 = latest['ma5'], latest['ma10'], latest['ma20']
        close = latest['close']
        
        if close > ma5 > ma10 > ma20:
            trend = "Uptrend"
            signal = "BUY"
        elif close < ma5 < ma10 < ma20:
            trend = "Downtrend"
            signal = "SELL"
        else:
            trend = "Sideways"
            signal = "HOLD"
        
        print(f"Trend: {trend}")
        print(f"Signal: {signal}")
        
        # 价格合理性
        if stock_code.startswith(('600', '000', '300', '688')):
            price_range = "10-500"
            if 10 <= close <= 500:
                price_check = "✅ Price in normal range"
            else:
                price_check = f"⚠️ Price abnormal: {close:.2f} (normal: {price_range})"
        elif stock_code.isalpha():
            price_range = "50-2000"
            if 50 <= close <= 2000:
                price_check = "✅ Price in normal range"
            else:
                price_check = f"⚠️ Price abnormal: ${close:.2f} (normal: ${price_range})"
        else:
            price_range = "Unknown"
            price_check = "🔍 Price range unknown"
        
        print(f"Price check: {price_check}")
        print("-" * 50)
        
        return True
        
    except Exception as e:
        print(f"❌ Error analyzing {stock_code}: {e}")
        return False

def main():
    """主函数"""
    print("Stock Market Analysis Tool")
    print("=" * 50)
    print("Using mock data for demonstration")
    print("=" * 50)
    
    test_stocks = [
        "600519",  # A-share
        "000001",  # A-share
        "300750",  # A-share
        "AAPL",    # US stock
        "TSLA",    # US stock
        "MSFT",    # US stock
        "VOD.L",   # UK stock
        "SAP.DE",  # German stock
    ]
    
    print(f"Analyzing {len(test_stocks)} stocks...")
    print("=" * 50)
    
    success_count = 0
    
    for i, stock in enumerate(test_stocks, 1):
        print(f"[{i}/{len(test_stocks)}] {stock}")
        
        if analyze_stock(stock):
            success_count += 1
    
    print("\n" + "=" * 50)
    print("Analysis Summary")
    print("=" * 50)
    print(f"Successfully analyzed: {success_count}/{len(test_stocks)} stocks")
    
    if success_count == len(test_stocks):
        print("✅ All stocks analyzed successfully!")
    else:
        failed_count = len(test_stocks) - success_count
        print(f"⚠️  {failed_count} stocks failed analysis")
    
    print("\nImportant Notes:")
    print("• This is a demonstration using mock data")
    print("• Prices are simulated and not real market data")
    print("• For real stock analysis, install real data sources")
    print("• Check the data source configuration in documentation")

if __name__ == "__main__":
    main()