# -*- coding: utf-8 -*-
"""
===================================
USStockFetcher - 美股数据源 (Priority 10)
===================================

数据来源：Yahoo Finance, Alpha Vantage, Polygon.io
特点：美股专用数据源，支持实时行情、财报、盘后盘前交易
优先级：10（美股专用，高优先级）

关键策略：
1. 多数据源备份（Yahoo Finance为主，Alpha Vantage为备选）
2. 支持盘前盘后交易数据
3. 美股特有的估值指标（EPS, P/E Ratio等）
4. 财报日历和重要事件提醒
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS
from market_types import Market, normalize_stock_code, Market

logger = logging.getLogger(__name__)


@dataclass
class USRealtimeQuote:
    """美股实时行情数据"""
    
    code: str
    name: str = ""
    
    # 基础价格数据
    price: float = 0.0           # 最新价
    change_pct: float = 0.0      # 涨跌幅(%)
    change_amount: float = 0.0   # 涨跌额
    
    # 盘前盘后数据
    pre_market_price: float = 0.0     # 盘前价格
    pre_market_change: float = 0.0   # 盘前涨跌
    after_market_price: float = 0.0  # 盘后价格
    after_market_change: float = 0.0 # 盘后涨跌
    
    # 量价指标
    volume: int = 0               # 成交量
    avg_volume: int = 0           # 平均成交量
    volume_ratio: float = 0.0     # 量比
    
    # 估值指标
    pe_ratio: float = 0.0         # 市盈率(TTM)
    eps: float = 0.0             # 每股收益(TTM)
    market_cap: float = 0.0       # 市值
    dividend_yield: float = 0.0   # 股息率
    
    # 技术指标
    day_high: float = 0.0         # 日最高
    day_low: float = 0.0          # 日最低
    week_52_high: float = 0.0     # 52周最高
    week_52_low: float = 0.0      # 52周最低
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'change_pct': self.change_pct,
            'change_amount': self.change_amount,
            'pre_market_price': self.pre_market_price,
            'pre_market_change': self.pre_market_change,
            'after_market_price': self.after_market_price,
            'after_market_change': self.after_market_change,
            'volume': self.volume,
            'avg_volume': self.avg_volume,
            'volume_ratio': self.volume_ratio,
            'pe_ratio': self.pe_ratio,
            'eps': self.eps,
            'market_cap': self.market_cap,
            'dividend_yield': self.dividend_yield,
            'day_high': self.day_high,
            'day_low': self.day_low,
            'week_52_high': self.week_52_high,
            'week_52_low': self.week_52_low,
        }


@dataclass
class EarningsInfo:
    """财报信息"""
    
    code: str
    earnings_date: Optional[str] = None    # 财报日期
    eps_estimate: float = 0.0              # EPS预期
    eps_actual: float = 0.0                # EPS实际
    revenue_estimate: float = 0.0          # 营收预期
    revenue_actual: float = 0.0            # 营收实际
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'earnings_date': self.earnings_date,
            'eps_estimate': self.eps_estimate,
            'eps_actual': self.eps_actual,
            'revenue_estimate': self.revenue_estimate,
            'revenue_actual': self.revenue_actual,
        }


class USStockFetcher(BaseFetcher):
    """
    美股数据源实现
    
    优先级：10（美股专用，高优先级）
    数据来源：Yahoo Finance 为主，Alpha Vantage 为备选
    
    关键特性：
    - 支持美股所有主要交易所
    - 盘前盘后交易数据
    - 实时估值指标
    - 财报日历提醒
    """
    
    name = "USStockFetcher"
    priority = 10  # 美股专用高优先级
    
    def __init__(self, alpha_vantage_key: Optional[str] = None):
        """
        初始化美股数据源
        
        Args:
            alpha_vantage_key: Alpha Vantage API Key（可选，作为备用数据源）
        """
        self.alpha_vantage_key = alpha_vantage_key
        self._price_cache: Dict[str, Any] = {}
        self._cache_timeout = 60  # 缓存60秒
    
    def _supports_market(self, stock_code: str) -> bool:
        """检查是否支持该股票的市场"""
        market = Market.from_stock_code(stock_code)
        return market in [Market.US_NYSE, Market.US_NASDAQ, Market.US_AMEX]
    
    def _get_yahoo_symbol(self, stock_code: str) -> str:
        """
        获取Yahoo Finance格式的股票代码
        
        Args:
            stock_code: 股票代码，如 'AAPL', 'AAPL.NASDAQ'
            
        Returns:
            Yahoo Finance标准代码，如 'AAPL'
        """
        code = stock_code.upper().strip()
        
        # 移除后缀
        if '.' in code:
            code = code.split('.')[0]
        
        return code
    
    def _fetch_alpha_vantage_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        使用Alpha Vantage获取历史数据（备用数据源）
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            历史数据DataFrame
        """
        if not self.alpha_vantage_key:
            raise DataFetchError("未配置Alpha Vantage API Key")
        
        from alpha_vantage.timeseries import TimeSeries
        
        ts = TimeSeries(key=self.alpha_vantage_key)
        
        try:
            # 获取日线数据
            data, meta_data = ts.get_daily_adjusted(
                symbol=symbol,
                outputsize='full'
            )
            
            # 转换为DataFrame
            df = pd.DataFrame.from_dict(data, orient='index')
            df.index = pd.to_datetime(df.index)
            df.columns = [
                'open', 'high', 'low', 'close', 
                'adj_close', 'volume', 'dividend', 'split_coeff'
            ]
            
            # 按日期范围筛选
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            
            return df
            
        except Exception as e:
            raise DataFetchError(f"Alpha Vantage获取{symbol}失败: {e}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从Yahoo Finance获取美股历史数据
        
        Args:
            stock_code: 美股代码，如 'AAPL', 'TSLA'
            start_date: 开始日期，格式 'YYYY-MM-DD'
            end_date: 结束日期，格式 'YYYY-MM-DD'
            
        Returns:
            原始数据DataFrame
        """
        # 检查市场支持
        if not self._supports_market(stock_code):
            raise DataFetchError(f"USStockFetcher不支持{stock_code}的市场")
        
        # 转换为Yahoo格式
        symbol = self._get_yahoo_symbol(stock_code)
        
        import yfinance as yf
        
        try:
            logger.info(f"[API调用] yfinance.download({symbol}, {start_date}, {end_date})")
            
            # 下载历史数据
            df = yf.download(
                tickers=symbol,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,  # 自动调整（复权）
                prepost=True,      # 包含盘前盘后数据
            )
            
            if df.empty:
                logger.warning(f"Yahoo Finance未查询到{symbol}的数据，尝试Alpha Vantage")
                return self._fetch_alpha_vantage_data(symbol, start_date, end_date)
            
            logger.info(f"[API返回] {symbol}成功获取{len(df)}条数据")
            return df
            
        except Exception as e:
            logger.warning(f"Yahoo Finance获取{symbol}失败: {e}，尝试Alpha Vantage")
            try:
                return self._fetch_alpha_vantage_data(symbol, start_date, end_date)
            except Exception as e2:
                raise DataFetchError(f"所有数据源获取{symbol}失败: Yahoo: {e}, Alpha Vantage: {e2}") from e2
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化美股数据
        
        Yahoo Finance返回格式：
        Open, High, Low, Close, Volume, Adj Close
        
        标准化为：date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()
        
        # 重置索引，将日期从索引变为列
        if df.index.name in ['Date', None]:
            df = df.reset_index()
        
        # 列名映射
        column_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'Adj Close': 'adj_close',
        }
        
        # 处理可能的其他列名
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns:
                df = df.rename(columns={old_name: new_name})
        
        # 确保有close列（优先使用Adj Close）
        if 'adj_close' in df.columns:
            df['close'] = df['adj_close']
        
        # 计算涨跌幅
        if 'close' in df.columns:
            df['pct_chg'] = df['close'].pct_change() * 100
            df['pct_chg'] = df['pct_chg'].fillna(0).round(2)
        
        # 计算成交额
        if 'volume' in df.columns and 'close' in df.columns:
            df['amount'] = df['volume'] * df['close']
        else:
            df['amount'] = 0
        
        # 添加股票代码
        df['code'] = stock_code
        
        # 选择需要的列
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]
        
        return df
    
    def get_realtime_quote(self, stock_code: str) -> Optional[USRealtimeQuote]:
        """
        获取美股实时行情
        
        包含盘前盘后数据、估值指标等美股特有信息
        
        Args:
            stock_code: 美股代码
            
        Returns:
            USRealtimeQuote对象
        """
        if not self._supports_market(stock_code):
            logger.warning(f"USStockFetcher不支持{stock_code}的实时行情")
            return None
        
        symbol = self._get_yahoo_symbol(stock_code)
        
        # 检查缓存
        current_time = time.time()
        cache_key = f"quote_{symbol}"
        if cache_key in self._price_cache:
            cached_data = self._price_cache[cache_key]
            if current_time - cached_data['timestamp'] < self._cache_timeout:
                logger.debug(f"[缓存命中] {symbol} 实时行情")
                return cached_data['quote']
        
        try:
            import yfinance as yf
            
            # 创建Ticker对象
            ticker = yf.Ticker(symbol)
            
            # 获取基本信息
            info = ticker.info
            
            # 获取当前价格数据
            history = ticker.history(period="1d", interval="1m", prepost=True)
            
            if history.empty or info is None:
                logger.warning(f"无法获取{symbol}的实时数据")
                return None
            
            # 获取最新数据
            latest = history.iloc[-1]
            
            quote = USRealtimeQuote(
                code=stock_code,
                name=info.get('shortName', ''),
                price=float(latest.get('Close', 0)),
                change_pct=float(info.get('regularMarketChangePercent', 0)),
                change_amount=float(info.get('regularMarketChange', 0)),
                
                # 盘前盘后数据
                pre_market_price=float(info.get('preMarketPrice', 0)),
                pre_market_change=float(info.get('preMarketChangePercent', 0)),
                after_market_price=float(info.get('postMarketPrice', 0)),
                after_market_change=float(info.get('postMarketChangePercent', 0)),
                
                # 量价数据
                volume=int(info.get('regularMarketVolume', 0)),
                avg_volume=int(info.get('averageVolume', 0)),
                volume_ratio=float(info.get('averageVolume', 1)) / max(1, float(info.get('regularMarketVolume', 1))),
                
                # 估值指标
                pe_ratio=float(info.get('trailingPE', 0)),
                eps=float(info.get('trailingEps', 0)),
                market_cap=float(info.get('marketCap', 0)),
                dividend_yield=float(info.get('dividendYield', 0)) * 100,  # 转换为百分比
                
                # 技术指标
                day_high=float(info.get('regularMarketDayHigh', 0)),
                day_low=float(info.get('regularMarketDayLow', 0)),
                week_52_high=float(info.get('fiftyTwoWeekHigh', 0)),
                week_52_low=float(info.get('fiftyTwoWeekLow', 0)),
            )
            
            # 缓存结果
            self._price_cache[cache_key] = {
                'quote': quote,
                'timestamp': current_time
            }
            
            logger.info(f"[美股实时] {symbol} {quote.name}: 价格=${quote.price:.2f}, "
                       f"涨跌={quote.change_pct:.2f}%, PE={quote.pe_ratio:.2f}")
            return quote
            
        except Exception as e:
            logger.error(f"获取{symbol}实时行情失败: {e}")
            return None
    
    def get_earnings_info(self, stock_code: str) -> Optional[EarningsInfo]:
        """
        获取财报信息
        
        Args:
            stock_code: 美股代码
            
        Returns:
            EarningsInfo对象
        """
        if not self._supports_market(stock_code):
            return None
        
        symbol = self._get_yahoo_symbol(stock_code)
        
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            
            # 获取财报日历
            calendar = ticker.calendar
            
            if calendar is None or calendar.empty:
                logger.debug(f"{symbol} 暂无财报日程")
                return None
            
            latest = calendar.iloc[0] if not calendar.empty else None
            
            if latest is None:
                return None
            
            earnings = EarningsInfo(
                code=stock_code,
                earnings_date=str(latest.get('Earnings Date', '')),
                eps_estimate=float(latest.get('EPS Estimate', 0)),
                revenue_estimate=float(latest.get('Revenue Estimate', 0)),
            )
            
            logger.info(f"[财报信息] {symbol}: 财报日期={earnings.earnings_date}, "
                       f"EPS预期={earnings.eps_estimate}")
            return earnings
            
        except Exception as e:
            logger.error(f"获取{symbol}财报信息失败: {e}")
            return None
    
    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        获取美股增强数据
        
        包含历史数据、实时行情、财报信息
        
        Args:
            stock_code: 美股代码
            days: 历史数据天数
            
        Returns:
            增强数据字典
        """
        result = {
            'code': stock_code,
            'daily_data': None,
            'realtime_quote': None,
            'earnings_info': None,
        }
        
        # 获取历史数据
        try:
            df = self.get_daily_data(stock_code, days=days)
            result['daily_data'] = df
        except Exception as e:
            logger.error(f"获取{stock_code}历史数据失败: {e}")
        
        # 获取实时行情
        result['realtime_quote'] = self.get_realtime_quote(stock_code)
        
        # 获取财报信息
        result['earnings_info'] = self.get_earnings_info(stock_code)
        
        return result


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = USStockFetcher()
    
    # 测试美股历史数据
    print("=" * 50)
    print("测试美股历史数据获取")
    print("=" * 50)
    
    test_stocks = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN.NASDAQ"]
    
    for stock in test_stocks:
        try:
            df = fetcher.get_daily_data(stock, days=30)
            print(f"[{stock}] 获取成功，共 {len(df)} 条数据")
            if not df.empty:
                print(f"  最新数据: {df['close'].iloc[-1]:.2f}")
        except Exception as e:
            print(f"[{stock}] 获取失败: {e}")
    
    # 测试实时行情
    print("\n" + "=" * 50)
    print("测试美股实时行情获取")
    print("=" * 50)
    
    for stock in ["AAPL", "TSLA"]:
        quote = fetcher.get_realtime_quote(stock)
        if quote:
            print(f"[{stock}] {quote.name}: ${quote.price:.2f} ({quote.change_pct:+.2f}%)")
            if quote.pre_market_price > 0:
                print(f"  盘前: ${quote.pre_market_price:.2f} ({quote.pre_market_change:+.2f}%)")
        else:
            print(f"[{stock}] 未获取到实时行情")
    
    # 测试财报信息
    print("\n" + "=" * 50)
    print("测试财报信息获取")
    print("=" * 50)
    
    for stock in ["AAPL", "MSFT"]:
        earnings = fetcher.get_earnings_info(stock)
        if earnings and earnings.earnings_date:
            print(f"[{stock}] 下次财报: {earnings.earnings_date}, EPS预期: {earnings.eps_estimate:.2f}")
        else:
            print(f"[{stock}] 暂无财报信息")