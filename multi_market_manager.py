# -*- coding: utf-8 -*-
"""
===================================
多市场数据源管理器
===================================

基于现有BaseFetcher扩展，增加智能市场路由功能
"""

import logging
from typing import Optional, List, Tuple
import pandas as pd

from data_provider.base import BaseFetcher, DataFetcherError
from market_types import Market

logger = logging.getLogger(__name__)


class MultiMarketDataFetcherManager:
    """
    多市场数据源管理器
    
    职责：
    1. 管理多个市场的数据源
    2. 智能路由：根据股票代码市场选择最合适的数据源
    3. 自动故障切换
    4. 提供统一的数据获取接口
    """
    
    def __init__(self, fetchers: Optional[List[BaseFetcher]] = None):
        """
        初始化多市场数据源管理器
        
        Args:
            fetchers: 数据源列表（可选，默认自动初始化）
        """
        self._fetchers: List[BaseFetcher] = []
        
        if fetchers:
            self._fetchers = sorted(fetchers, key=lambda f: f.priority)
        else:
            self._init_default_fetchers()
    
    def _init_default_fetchers(self) -> None:
        """初始化默认数据源列表"""
        try:
            # 导入所有数据源
            from data_provider.efinance_fetcher import EfinanceFetcher
            from data_provider.akshare_fetcher import AkshareFetcher
            from data_provider.tushare_fetcher import TushareFetcher
            from data_provider.baostock_fetcher import BaostockFetcher
            from data_provider.yfinance_fetcher import YfinanceFetcher
            from data_provider.us_stock_fetcher import USStockFetcher
            from data_provider.eu_stock_fetcher import EUStockFetcher
            from config import get_config
            
            config = get_config()
            
            # 创建所有数据源实例
            efinance = EfinanceFetcher()
            akshare = AkshareFetcher()
            tushare = TushareFetcher()
            baostock = BaostockFetcher()
            yfinance = YfinanceFetcher()
            
            # 多市场数据源
            alpha_vantage_key = getattr(config, 'alpha_vantage_key', None)
            us_stock = USStockFetcher(alpha_vantage_key=alpha_vantage_key)
            eu_stock = EUStockFetcher(alpha_vantage_key=alpha_vantage_key)
            
            # 初始化数据源列表
            self._fetchers = [
                efinance,
                akshare,
                tushare,
                baostock,
                yfinance,
                us_stock,
                eu_stock,
            ]
            
            # 按优先级排序
            self._fetchers.sort(key=lambda f: f.priority)
            
            # 构建优先级说明
            priority_info = ", ".join([f"{f.name}(P{f.priority})" for f in self._fetchers])
            logger.info(f"已初始化 {len(self._fetchers)} 个数据源（按优先级）: {priority_info}")
            
        except Exception as e:
            logger.error(f"初始化数据源失败: {e}")
            raise DataFetcherError(f"数据源初始化失败: {e}") from e
    
    def add_fetcher(self, fetcher: BaseFetcher) -> None:
        """添加数据源并重新排序"""
        self._fetchers.append(fetcher)
        self._fetchers.sort(key=lambda f: f.priority)
    
    def get_daily_data(
        self, 
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30
    ) -> Tuple[pd.DataFrame, str]:
        """
        获取日线数据（智能市场路由 + 自动切换数据源）
        
        路由策略：
        1. 识别股票代码所属市场
        2. 优先选择该市场的专用数据源
        3. 按优先级尝试数据源
        4. 捕获异常后自动切换到下一个
        5. 记录每个数据源的失败原因
        6. 所有数据源失败后抛出详细异常
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            days: 获取天数
            
        Returns:
            Tuple[DataFrame, str]: (数据, 成功的数据源名称)
            
        Raises:
            DataFetchError: 所有数据源都失败时抛出
        """
        try:
            # 导入市场识别模块
            market = Market.from_stock_code(stock_code)
            logger.debug(f"股票 {stock_code} 识别为 {market.get_display_name()}")
        except Exception as e:
            logger.warning(f"市场识别失败，使用通用路由: {e}")
            market = None
        
        errors = []
        
        # 智能排序：优先选择对应市场的数据源
        fetchers_to_try = self._fetchers.copy()
        
        if market:
            # 根据市场重新排序数据源
            market_priorities = {
                Market.CHINA_A: ['EfinanceFetcher', 'AkshareFetcher', 'TushareFetcher', 'BaostockFetcher'],
                Market.HONG_KONG: ['AkshareFetcher', 'YfinanceFetcher'],
                Market.US_NYSE: ['USStockFetcher', 'YfinanceFetcher'],
                Market.US_NASDAQ: ['USStockFetcher', 'YfinanceFetcher'],
                Market.US_AMEX: ['USStockFetcher', 'YfinanceFetcher'],
                Market.UK_LSE: ['EUStockFetcher', 'YfinanceFetcher'],
                Market.GER_XETRA: ['EUStockFetcher', 'YfinanceFetcher'],
                Market.FRA_EURONEXT: ['EUStockFetcher', 'YfinanceFetcher'],
                Market.SWX_SIX: ['EUStockFetcher', 'YfinanceFetcher'],
                Market.EURONEXT: ['EUStockFetcher', 'YfinanceFetcher'],
            }
            
            # 获取市场优先的数据源名称列表
            preferred_fetchers = market_priorities.get(market, [])
            
            # 重新排序：市场专用数据源在前，其他在后
            def get_fetcher_priority(fetcher):
                name = fetcher.name
                if name in preferred_fetchers:
                    return preferred_fetchers.index(name)  # 市场专用数据源优先
                else:
                    return len(preferred_fetchers) + fetcher.priority  # 其他按原优先级
            
            fetchers_to_try.sort(key=get_fetcher_priority)
        
        # 按顺序尝试数据源
        for fetcher in fetchers_to_try:
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
                errors.append(error_msg)
                # 继续尝试下一个数据源
                continue
        
        # 所有数据源都失败
        error_summary = f"所有数据源获取 {stock_code} 失败:\n" + "\n".join(errors)
        logger.error(error_summary)
        raise DataFetchError(error_summary)
    
    def get_realtime_quote(self, stock_code: str):
        """
        获取实时行情（支持多市场数据源）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            实时行情对象（类型因市场而异）
        """
        try:
            market = Market.from_stock_code(stock_code)
        except Exception as e:
            logger.warning(f"市场识别失败: {e}")
            market = None
        
        errors = []
        
        # 优先选择对应市场的数据源
        fetchers_to_try = self._fetchers.copy()
        
        if market:
            # 根据市场重新排序
            market_priorities = {
                Market.CHINA_A: ['EfinanceFetcher', 'AkshareFetcher'],
                Market.HONG_KONG: ['AkshareFetcher', 'YfinanceFetcher'],
                Market.US_NYSE: ['USStockFetcher', 'YfinanceFetcher'],
                Market.US_NASDAQ: ['USStockFetcher', 'YfinanceFetcher'],
                Market.US_AMEX: ['USStockFetcher', 'YfinanceFetcher'],
                Market.UK_LSE: ['EUStockFetcher', 'YfinanceFetcher'],
                Market.GER_XETRA: ['EUStockFetcher', 'YfinanceFetcher'],
                Market.FRA_EURONEXT: ['EUStockFetcher', 'YfinanceFetcher'],
                Market.SWX_SIX: ['EUStockFetcher', 'YfinanceFetcher'],
                Market.EURONEXT: ['EUStockFetcher', 'YfinanceFetcher'],
            }
            
            preferred_fetchers = market_priorities.get(market, [])
            
            def get_fetcher_priority(fetcher):
                name = fetcher.name
                if name in preferred_fetchers:
                    return preferred_fetchers.index(name)
                else:
                    return len(preferred_fetchers) + fetcher.priority
            
            fetchers_to_try.sort(key=get_fetcher_priority)
        
        # 按顺序尝试数据源
        for fetcher in fetchers_to_try:
            try:
                logger.debug(f"尝试使用 [{fetcher.name}] 获取 {stock_code} 实时行情...")
                
                # 检查是否支持实时行情
                if hasattr(fetcher, 'get_realtime_quote'):
                    quote = fetcher.get_realtime_quote(stock_code)
                    if quote:
                        logger.info(f"[{fetcher.name}] 成功获取 {stock_code} 实时行情")
                        return quote
                    
            except Exception as e:
                error_msg = f"[{fetcher.name}] 实时行情失败: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
        
        logger.warning(f"所有数据源获取 {stock_code} 实时行情失败")
        return None
    
    @property
    def available_fetchers(self) -> List[str]:
        """返回可用数据源名称列表"""
        return [f.name for f in self._fetchers]


# 创建全局实例
_global_manager: Optional[MultiMarketDataFetcherManager] = None


def get_multi_market_manager() -> MultiMarketDataFetcherManager:
    """获取全局多市场数据源管理器实例"""
    global _global_manager
    if _global_manager is None:
        _global_manager = MultiMarketDataFetcherManager()
    return _global_manager