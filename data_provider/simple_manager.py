# -*- coding: utf-8 -*-
"""
==================================
多市场数据源管理器（简化版本）
==================================
"""

import logging
from typing import Optional, List, Tuple
import pandas as pd

# 配置日志
logger = logging.getLogger(__name__)

class DataFetchError(Exception):
    """数据获取异常"""
    pass

class MockFetcher:
    """模拟数据源"""
    
    name = "MockFetcher"
    priority = 999  # 最低优先级
    
    def get_daily_data(self, stock_code, start_date=None, end_date=None, days=30):
        """生成模拟数据"""
        
        from datetime import datetime, timedelta
        import numpy as np
        
        logger.info(f"[MockFetcher] 生成 {stock_code} 的模拟数据")
        
        # 处理日期范围
        if end_date is None:
            end_date = datetime.now()
        else:
            end_date = pd.to_datetime(end_date)
        
        if start_date is None:
            start_date = end_date - timedelta(days=days*2)
        else:
            start_date = pd.to_datetime(start_date)
        
        # 生成日期序列（只包含工作日）
        dates = pd.bdate_range(start=start_date, end=end_date)
        dates = dates[-min(len(dates), days):]
        
        # 生成模拟价格数据
        np.random.seed(hash(stock_code) % 2**32)
        
        # 根据股票类型设置基础价格
        stock_names = {
            '600519': '贵州茅台',
            '000001': '平安银行',
            '300750': '宁德时代',
            'AAPL': 'Apple Inc.',
            'TSLA': 'Tesla Inc.',
        }
        
        if stock_code.startswith(('600', '000', '300', '688')):
            base_price = stock_names.get(stock_code, np.random.uniform(10, 500))
        elif stock_code.isalpha():
            base_price = stock_names.get(stock_code, np.random.uniform(50, 1000))
        else:
            base_price = np.random.uniform(10, 500)
        
        # 生成价格序列
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
        
        # 生成OHLC数据
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
        
        logger.info(f"[MockFetcher] 成功生成 {stock_code} 数据：{len(df)} 条，最新价格 {df['close'].iloc[-1]:.2f}")
        
        return df


class DataFetcherManager:
    """数据源管理器"""
    
    def __init__(self):
        """初始化数据源管理器"""
        self._fetchers = []
        
        # 添加模拟数据源
        mock_fetcher = MockFetcher()
        self._fetchers.append(mock_fetcher)
        
        logger.info(f"已初始化 {len(self._fetchers)} 个数据源: {self.available_fetchers}")
    
    @property
    def available_fetchers(self) -> List[str]:
        """返回可用数据源名称列表"""
        return [f.name for f in self._fetchers]
    
    def get_daily_data(
        self, 
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30
    ) -> Tuple[pd.DataFrame, str]:
        """获取日线数据"""
        
        for fetcher in self._fetchers:
            try:
                logger.info(f"尝试使用 [{fetcher.name}] 获取 {stock_code}...")
                df = fetcher.get_daily_data(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    days=days
                )
                
                if df is not None and not df.empty:
                    logger.info(f"[{fetcher.name}] 成功获取 {stock_code}")
                    return df, fetcher.name
                    
            except Exception as e:
                error_msg = f"[{fetcher.name}] 失败: {str(e)}"
                logger.warning(error_msg)
                continue
        
        # 所有数据源都失败
        error_summary = f"所有数据源获取 {stock_code} 失败"
        logger.error(error_summary)
        raise DataFetchError(error_summary)
    
    def get_realtime_quote(self, stock_code):
        """获取实时行情"""
        try:
            if self._fetchers and hasattr(self._fetchers[0], 'get_realtime_quote'):
                return self._fetchers[0].get_realtime_quote(stock_code)
        except Exception as e:
            logger.error(f"获取 {stock_code} 实时行情失败: {e}")
        
        return None