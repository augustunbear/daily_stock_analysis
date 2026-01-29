# -*- coding: utf-8 -*-
"""
===================================
数据源策略层 - 包初始化（多市场支持）
===================================

import logging
logger = logging.getLogger(__name__)

本包实现策略模式管理多个数据源，支持全球股市：
1. 统一的数据获取接口
2. 自动故障切换
3. 防封禁流控策略
4. 多市场智能路由

数据源优先级（动态调整）：

【中国市场】
1. TushareFetcher (Priority 0) - 🔥 最高优先级（配置Token时）
2. EfinanceFetcher (Priority 0) - 高优先级，中国股专用
3. AkshareFetcher (Priority 1) - 中国股主要数据源
4. BaostockFetcher (Priority 3) - 中国股备用数据源
5. YfinanceFetcher (Priority 4) - 全球数据源（中国股兜底）

【美国市场】
1. USStockFetcher (Priority 10) - 🇺🇸 美股专用，高优先级
2. YfinanceFetcher (Priority 11) - 美股备用数据源

【欧洲市场】
1. EUStockFetcher (Priority 11) - 🇪🇺 欧股专用，高优先级
2. YfinanceFetcher (Priority 12) - 欧股备用数据源

【全球通用】
1. YfinanceFetcher (Priority 15) - 🌍 全球市场兜底数据源

提示：
- 优先级数字越小越优先
- 同市场专用数据源优先于通用数据源
- 自动根据股票代码市场智能选择数据源
"""

import logging
logger = logging.getLogger(__name__)

# 基础模块必须导入
from .base import BaseFetcher, DataFetcherManager

# 可选数据源，导入失败时提供占位符
try:
    from .efinance_fetcher import EfinanceFetcher
except ImportError as e:
    logger.warning(f"无法导入 EfinanceFetcher: {e}")
    EfinanceFetcher = None

try:
    from .akshare_fetcher import AkshareFetcher
except ImportError as e:
    logger.warning(f"无法导入 AkshareFetcher: {e}")
    AkshareFetcher = None

try:
    from .tushare_fetcher import TushareFetcher
except ImportError as e:
    logger.warning(f"无法导入 TushareFetcher: {e}")
    TushareFetcher = None

try:
    from .baostock_fetcher import BaostockFetcher
except ImportError as e:
    logger.warning(f"无法导入 BaostockFetcher: {e}")
    BaostockFetcher = None

try:
    from .yfinance_fetcher import YfinanceFetcher
except ImportError as e:
    logger.warning(f"无法导入 YfinanceFetcher: {e}")
    YfinanceFetcher = None

try:
    from .us_stock_fetcher import USStockFetcher
except ImportError as e:
    logger.warning(f"无法导入 USStockFetcher: {e}")
    USStockFetcher = None

try:
    from .eu_stock_fetcher import EUStockFetcher
except ImportError as e:
    logger.warning(f"无法导入 EUStockFetcher: {e}")
    EUStockFetcher = None

__all__ = [
    'BaseFetcher',
    'DataFetcherManager',
    'EfinanceFetcher',
    'AkshareFetcher',
    'TushareFetcher',
    'BaostockFetcher',
    'YfinanceFetcher',
    'USStockFetcher',
    'EUStockFetcher',
]
