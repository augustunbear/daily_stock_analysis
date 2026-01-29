# -*- coding: utf-8 -*-
"""
简单数据源 - 用于测试
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class SimpleFetcher:
    """简单测试数据源"""
    
    name = "SimpleFetcher"
    priority = 1
    
    def get_daily_data(self, stock_code, start_date=None, end_date=None, days=30):
        """生成测试数据"""
        
        # 如果没有指定日期范围，使用默认值
        if end_date is None:
            end_date = datetime.now()
        else:
            end_date = pd.to_datetime(end_date)
        
        if start_date is None:
            start_date = end_date - timedelta(days=days)
        else:
            start_date = pd.to_datetime(start_date)
        
        # 生成日期序列（只包含工作日）
        dates = pd.bdate_range(start=start_date, end=end_date)
        
        # 生成模拟价格数据
        np.random.seed(hash(stock_code) % 2**32)  # 确保每个股票的数据一致
        
        base_price = 100.0
        if stock_code.startswith(('600', '000', '300', '688')):  # A股
            base_price = np.random.uniform(10, 500)  # A股价格范围
        elif stock_code.isalpha():  # 美股
            base_price = np.random.uniform(50, 1000)  # 美股价格范围
        
        # 生成价格序列
        n_days = len(dates)
        returns = np.random.normal(0, 0.02, n_days)  # 日收益率
        returns[0] = 0  # 第一天没有变化
        
        prices = [base_price]
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        # 生成OHLC数据
        data = []
        for i, date in enumerate(dates):
            close_price = prices[i]
            # 模拟日内波动
            daily_vol = abs(np.random.normal(0, 0.02))
            high = close_price * (1 + daily_vol)
            low = close_price * (1 - daily_vol)
            open_price = low + (high - low) * np.random.random()
            
            # 确保OHLC逻辑正确
            high = max(high, open_price, close_price)
            low = min(low, open_price, close_price)
            
            volume = int(np.random.uniform(1000000, 10000000))
            
            data.append({
                'date': date,
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close_price, 2),
                'volume': volume,
                'amount': volume * close_price,
                'pct_chg': round(returns[i] * 100, 2)
            })
        
        df = pd.DataFrame(data)
        
        # 添加技术指标
        df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
        df['ma10'] = df['close'].rolling(window=10, min_periods=1).mean()
        df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
        
        avg_volume = df['volume'].rolling(window=5, min_periods=1).mean()
        df['volume_ratio'] = df['volume'] / avg_volume.shift(1)
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
        
        return df
    
    def get_realtime_quote(self, stock_code):
        """获取模拟实时行情"""
        
        # 生成基础信息
        stock_names = {
            '600519': '贵州茅台',
            '000001': '平安银行', 
            '300750': '宁德时代',
            'AAPL': 'Apple Inc.',
            'TSLA': 'Tesla Inc.',
            'VOD.L': 'Vodafone Group',
            'SAP.DE': 'SAP SE',
            'MSFT': 'Microsoft Corporation',
        }
        
        name = stock_names.get(stock_code, f'Stock {stock_code}')
        
        # 获取最新价格
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

def test_simple_data():
    """测试简单数据源"""
    
    print('=== Simple Data Source Test ===')
    
    fetcher = SimpleFetcher()
    
    test_stocks = ['600519', 'AAPL', 'TSLA']
    
    for stock in test_stocks:
        print(f'\\nTesting {stock}...')
        
        # 测试历史数据
        df = fetcher.get_daily_data(stock, days=10)
        
        if df is not None and not df.empty:
            print(f'  Success! Shape: {df.shape}')
            print(f'  Latest price: {df[\"close\"].iloc[-1]:.2f}')
            print(f'  Date range: {df[\"date\"].min().strftime(\"%Y-%m-%d\")} to {df[\"date\"].max().strftime(\"%Y-%m-%d\")}')
            print(f'  Sample data:')
            print(df.tail(2)[['date', 'open', 'high', 'low', 'close', 'volume', 'pct_chg']].to_string())
        else:
            print(f'  Failed - empty data')
        
        # 测试实时行情
        quote = fetcher.get_realtime_quote(stock)
        if quote:
            print(f'  Quote: {quote[\"name\"]} ({quote[\"code\"]}) - {quote[\"price\"]} ({quote[\"change_pct\"]:+.2f}%)')
        else:
            print(f'  Quote failed')

if __name__ == '__main__':
    test_simple_data()