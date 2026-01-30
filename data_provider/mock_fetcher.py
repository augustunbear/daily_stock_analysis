# -*- coding: utf-8 -*-
"""
内置模拟数据源 - 当没有真实数据源时使用
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class MockFetcher:
    """模拟数据源"""
    
    name = "MockFetcher"
    priority = 999  # 最低优先级
    
    def get_daily_data(self, stock_code, start_date=None, end_date=None, days=30):
        """生成模拟数据"""
        
        logger.info(f"[MockFetcher] 生成 {stock_code} 的模拟数据")
        
        # 处理日期范围
        if end_date is None:
            end_date = datetime.now()
        else:
            end_date = pd.to_datetime(end_date)
        
        if start_date is None:
            start_date = end_date - timedelta(days=days*2)  # 多取一些，确保有足够的交易日
        else:
            start_date = pd.to_datetime(start_date)
        
        # 生成日期序列（只包含工作日）
        dates = pd.bdate_range(start=start_date, end=end_date)
        
        # 取最后N天
        dates = dates[-min(len(dates), days):]
        
        # 生成模拟价格数据
        np.random.seed(hash(stock_code) % 2**32)  # 确保每个股票的数据一致
        
        # 根据股票类型设置基础价格
        if stock_code.startswith(('600', '000', '300', '688')):  # A股
            stock_names = {
                '600519': '贵州茅台',
                '000001': '平安银行',
                '300750': '宁德时代',
                '002594': '比亚迪',
                '000002': '万科A',
            }
            base_price = stock_names.get(stock_code, np.random.uniform(10, 500))
            
        elif stock_code.isalpha():  # 美股
            stock_names = {
                'AAPL': 'Apple Inc.',
                'TSLA': 'Tesla Inc.',
                'MSFT': 'Microsoft Corporation',
                'GOOGL': 'Alphabet Inc.',
                'AMZN': 'Amazon.com Inc.',
            }
            base_price = stock_names.get(stock_code, np.random.uniform(50, 1000))
            
        elif stock_code.endswith(('.L', '.DE', '.PA', '.SW', '.AS')):  # 欧股
            base_price = np.random.uniform(5, 200)
            
        else:  # 其他
            base_price = np.random.uniform(10, 500)
        
        # 生成价格序列
        n_days = len(dates)
        returns = np.random.normal(0, 0.02, n_days)  # 日收益率
        returns[0] = 0  # 第一天没有变化
        
        prices = [base_price]
        for ret in returns[1:]:
            # 防止价格为负
            new_price = prices[-1] * (1 + ret)
            if new_price > 0:
                prices.append(new_price)
            else:
                prices.append(prices[-1] * 0.99)  # 最多跌1%
        
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
            
            volume = int(np.random.uniform(1000000, 50000000))
            
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
        
        # 计算量比
        avg_volume = df['volume'].rolling(window=5, min_periods=1).mean()
        df['volume_ratio'] = df['volume'] / avg_volume.shift(1)
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
        
        logger.info(f"[MockFetcher] 成功生成 {stock_code} 数据：{len(df)} 条，最新价格 {df['close'].iloc[-1]:.2f}")
        
        return df
    
    def get_realtime_quote(self, stock_code):
        """获取模拟实时行情"""
        
        stock_names = {
            '600519': '贵州茅台',
            '000001': '平安银行', 
            '300750': '宁德时代',
            '002594': '比亚迪',
            '000002': '万科A',
            'AAPL': 'Apple Inc.',
            'TSLA': 'Tesla Inc.',
            'MSFT': 'Microsoft Corporation',
            'GOOGL': 'Alphabet Inc.',
            'AMZN': 'Amazon.com Inc.',
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