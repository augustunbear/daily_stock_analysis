# -*- coding: utf-8 -*-
"""
===================================
EUStockFetcher - 欧洲股市数据源 (Priority 11)
===================================

数据来源：Yahoo Finance, Alpha Vantage, Investing.com
特点：欧洲主要交易所专用数据源，支持多币种、多时区
优先级：11（欧洲股专用，高优先级）

关键策略：
1. 多数据源备份（Yahoo Finance为主）
2. 支持欧洲主要交易所（伦敦、法兰克福、巴黎、苏黎世等）
3. 自动处理货币转换和时间差异
4. 欧洲股市特有的监管信息（FCA, BaFin等）
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import re

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
class EURealtimeQuote:
    """欧洲股市实时行情数据"""
    
    code: str
    name: str = ""
    exchange: str = ""          # 交易所名称
    currency: str = ""         # 货币代码
    
    # 基础价格数据
    price: float = 0.0           # 最新价
    change_pct: float = 0.0      # 涨跌幅(%)
    change_amount: float = 0.0   # 涨跌额
    
    # 量价指标
    volume: int = 0               # 成交量
    avg_volume: int = 0           # 平均成交量
    volume_ratio: float = 0.0     # 量比
    
    # 估值指标（欧洲股市格式）
    pe_ratio: float = 0.0         # 市盈率
    market_cap: float = 0.0       # 市值（本地货币）
    market_cap_usd: float = 0.0   # 市值（美元）
    dividend_yield: float = 0.0   # 股息率
    
    # 技术指标
    day_high: float = 0.0         # 日最高
    day_low: float = 0.0          # 日最低
    week_52_high: float = 0.0     # 52周最高
    week_52_low: float = 0.0      # 52周最低
    
    # 欧洲特有信息
    sector: str = ""              # 行业分类
    country: str = ""             # 国家
    regulatory_info: str = ""      # 监管信息
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'exchange': self.exchange,
            'currency': self.currency,
            'price': self.price,
            'change_pct': self.change_pct,
            'change_amount': self.change_amount,
            'volume': self.volume,
            'avg_volume': self.avg_volume,
            'volume_ratio': self.volume_ratio,
            'pe_ratio': self.pe_ratio,
            'market_cap': self.market_cap,
            'market_cap_usd': self.market_cap_usd,
            'dividend_yield': self.dividend_yield,
            'day_high': self.day_high,
            'day_low': self.day_low,
            'week_52_high': self.week_52_high,
            'week_52_low': self.week_52_low,
            'sector': self.sector,
            'country': self.country,
            'regulatory_info': self.regulatory_info,
        }


class EUStockFetcher(BaseFetcher):
    """
    欧洲股市数据源实现
    
    优先级：11（欧洲股专用，高优先级）
    数据来源：Yahoo Finance 为主，Alpha Vantage 为备选
    
    支持的交易所：
    - 伦敦证券交易所 (LSE)
    - 德国法兰克福交易所 (XETRA)
    - 法国泛欧交易所 (EURONEXT)
    - 瑞士证券交易所 (SWX)
    - 泛欧交易所阿姆斯特丹 (EURONEXT AMS)
    """
    
    name = "EUStockFetcher"
    priority = 11  # 欧洲股专用高优先级
    
    def __init__(self, alpha_vantage_key: Optional[str] = None):
        """
        初始化欧洲股数据源
        
        Args:
            alpha_vantage_key: Alpha Vantage API Key（可选，作为备用数据源）
        """
        self.alpha_vantage_key = alpha_vantage_key
        self._price_cache: Dict[str, Any] = {}
        self._cache_timeout = 60  # 缓存60秒
        
        # 欧洲交易所映射
        self.exchange_mappings = {
            Market.UK_LSE: {
                'yahoo_suffix': '.L',
                'name': 'London Stock Exchange',
                'currency': 'GBP',
                'country': 'United Kingdom',
                'regulator': 'FCA'
            },
            Market.GER_XETRA: {
                'yahoo_suffix': '.DE',
                'name': 'Deutsche Börse Xetra',
                'currency': 'EUR',
                'country': 'Germany',
                'regulator': 'BaFin'
            },
            Market.FRA_EURONEXT: {
                'yahoo_suffix': '.PA',
                'name': 'Euronext Paris',
                'currency': 'EUR',
                'country': 'France',
                'regulator': 'AMF'
            },
            Market.SWX_SIX: {
                'yahoo_suffix': '.SW',
                'name': 'SIX Swiss Exchange',
                'currency': 'CHF',
                'country': 'Switzerland',
                'regulator': 'FINMA'
            },
            Market.EURONEXT: {
                'yahoo_suffix': '.AS',
                'name': 'Euronext Amsterdam',
                'currency': 'EUR',
                'country': 'Netherlands',
                'regulator': 'AFM'
            }
        }
    
    def _supports_market(self, stock_code: str) -> bool:
        """检查是否支持该股票的市场"""
        market = Market.from_stock_code(stock_code)
        return market in self.exchange_mappings.keys()
    
    def _get_yahoo_symbol(self, stock_code: str) -> str:
        """
        获取Yahoo Finance格式的欧洲股票代码
        
        Args:
            stock_code: 欧洲股票代码，如 'VOD.L', 'SAP.DE'
            
        Returns:
            Yahoo Finance标准代码
        """
        code = stock_code.upper().strip()
        
        # 如果已经包含正确后缀，直接返回
        for market, config in self.exchange_mappings.items():
            if code.endswith(config['yahoo_suffix']):
                return code
        
        # 否则根据市场推断后缀
        market = Market.from_stock_code(stock_code)
        if market in self.exchange_mappings:
            # 移除现有后缀，添加正确后缀
            base_code = re.sub(r'\.[A-Z]+$', '', code)
            suffix = self.exchange_mappings[market]['yahoo_suffix']
            return f"{base_code}{suffix}"
        
        return code
    
    def _get_exchange_info(self, stock_code: str) -> Dict[str, str]:
        """
        获取股票的交易所信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            交易所信息字典
        """
        market = Market.from_stock_code(stock_code)
        return self.exchange_mappings.get(market, {
            'name': 'Unknown',
            'currency': 'EUR',
            'country': 'Unknown',
            'regulator': 'Unknown'
        })
    
    def _fetch_alpha_vantage_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        使用Alpha Vantage获取欧洲股票历史数据（备用数据源）
        
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
        从Yahoo Finance获取欧洲股票历史数据
        
        Args:
            stock_code: 欧洲股票代码，如 'VOD.L', 'SAP.DE'
            start_date: 开始日期，格式 'YYYY-MM-DD'
            end_date: 结束日期，格式 'YYYY-MM-DD'
            
        Returns:
            原始数据DataFrame
        """
        # 检查市场支持
        if not self._supports_market(stock_code):
            raise DataFetchError(f"EUStockFetcher不支持{stock_code}的市场")
        
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
                auto_adjust=True,
                prepost=False,  # 欧股一般无盘前盘后
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
        标准化欧洲股票数据
        
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
        
        # 计算成交额（本地货币）
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
    
    def get_realtime_quote(self, stock_code: str) -> Optional[EURealtimeQuote]:
        """
        获取欧洲股票实时行情
        
        Args:
            stock_code: 欧洲股票代码
            
        Returns:
            EURealtimeQuote对象
        """
        if not self._supports_market(stock_code):
            logger.warning(f"EUStockFetcher不支持{stock_code}的实时行情")
            return None
        
        symbol = self._get_yahoo_symbol(stock_code)
        exchange_info = self._get_exchange_info(stock_code)
        
        # 检查缓存
        current_time = time.time()
        cache_key = f"quote_{symbol}"
        if cache_key in self._price_cache:
            cached_data = self._price_cache[cache_key]
            if current_time - cached_data['timestamp'] < self._cache_timeout:
                logger.debug(f"[缓存命中] {symbol} 实时行情")
                return cached_data['quote']
        quote = None

        if self.alpha_vantage_key:
            try:
                quote = self._fetch_alpha_vantage_quote(symbol, stock_code, exchange_info)
            except Exception as e:
                logger.warning(f"Alpha Vantage获取{symbol}失败: {e}，尝试Yahoo Finance")

        if quote is None:
            try:
                quote = self._fetch_yahoo_realtime_quote(symbol, stock_code, exchange_info)
            except Exception as e:
                logger.error(f"Yahoo Finance获取{symbol}实时行情失败: {e}")
                return None

        if quote is None:
            return None

        self._price_cache[cache_key] = {
            'quote': quote,
            'timestamp': current_time
        }

        logger.info(f"[欧洲股实时] {symbol} {quote.name}: {quote.currency}{quote.price:.2f}, "
                   f"涨跌={quote.change_pct:.2f}%")
        return quote

    def _fetch_alpha_vantage_quote(
        self,
        symbol: str,
        stock_code: str,
        exchange_info: Dict[str, str]
    ) -> EURealtimeQuote:
        if not self.alpha_vantage_key:
            raise DataFetchError("未配置Alpha Vantage API Key")

        import requests

        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.alpha_vantage_key,
        }
        response = requests.get("https://www.alphavantage.co/query", params=params, timeout=10)
        data = response.json()
        quote_data = data.get("Global Quote") or {}

        if not quote_data:
            raise DataFetchError("Alpha Vantage未返回实时行情")

        price = float(quote_data.get("05. price", 0) or 0)
        change_amount = float(quote_data.get("09. change", 0) or 0)
        change_pct_str = str(quote_data.get("10. change percent", "0"))
        change_pct = float(change_pct_str.replace("%", "") or 0)
        volume = int(float(quote_data.get("06. volume", 0) or 0))

        return EURealtimeQuote(
            code=stock_code,
            name=symbol,
            exchange=exchange_info['name'],
            currency=exchange_info['currency'],
            price=price,
            change_pct=change_pct,
            change_amount=change_amount,
            volume=volume,
            avg_volume=0,
            volume_ratio=0.0,
            pe_ratio=0.0,
            market_cap=0.0,
            market_cap_usd=0.0,
            dividend_yield=0.0,
            day_high=float(quote_data.get("03. high", 0) or 0),
            day_low=float(quote_data.get("04. low", 0) or 0),
            week_52_high=0.0,
            week_52_low=0.0,
            sector="",
            country=exchange_info['country'],
            regulatory_info=f"{exchange_info['regulator']} regulated",
        )

    def _fetch_yahoo_realtime_quote(
        self,
        symbol: str,
        stock_code: str,
        exchange_info: Dict[str, str]
    ) -> Optional[EURealtimeQuote]:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        info = {}
        try:
            info = ticker.fast_info or {}
        except Exception:
            info = {}
        if not info:
            info = ticker.info or {}

        price = info.get('last_price') or info.get('regularMarketPrice') or info.get('currentPrice') or 0
        prev_close = info.get('previous_close') or info.get('regularMarketPreviousClose') or 0
        change_amount = info.get('regularMarketChange')
        if change_amount is None and prev_close:
            change_amount = price - prev_close
        change_pct = info.get('regularMarketChangePercent')
        if change_pct is None and prev_close:
            change_pct = (price - prev_close) / prev_close * 100

        volume = info.get('last_volume') or info.get('regularMarketVolume') or 0
        avg_volume = info.get('ten_day_average_volume') or info.get('averageVolume') or 0
        volume_ratio = (volume / avg_volume) if avg_volume else 0

        market_cap_local = float(info.get('market_cap') or info.get('marketCap') or 0)
        currency_usd_rate = {
            'GBP': 1.25,
            'EUR': 1.08,
            'CHF': 1.15
        }.get(exchange_info['currency'], 1.0)

        dividend_yield = info.get('dividend_yield') or info.get('dividendYield') or 0
        if dividend_yield and dividend_yield <= 1:
            dividend_yield = dividend_yield * 100

        return EURealtimeQuote(
            code=stock_code,
            name=info.get('shortName') or info.get('longName') or symbol,
            exchange=exchange_info['name'],
            currency=exchange_info['currency'],
            price=float(price or 0),
            change_pct=float(change_pct or 0),
            change_amount=float(change_amount or 0),
            volume=int(volume or 0),
            avg_volume=int(avg_volume or 0),
            volume_ratio=float(volume_ratio or 0),
            pe_ratio=float(info.get('pe_ratio') or info.get('trailingPE') or 0),
            market_cap=market_cap_local,
            market_cap_usd=market_cap_local / currency_usd_rate if currency_usd_rate else 0.0,
            dividend_yield=float(dividend_yield or 0),
            day_high=float(info.get('day_high') or info.get('regularMarketDayHigh') or 0),
            day_low=float(info.get('day_low') or info.get('regularMarketDayLow') or 0),
            week_52_high=float(info.get('week_52_high') or info.get('fiftyTwoWeekHigh') or 0),
            week_52_low=float(info.get('week_52_low') or info.get('fiftyTwoWeekLow') or 0),
            sector=info.get('sector', ''),
            country=exchange_info['country'],
            regulatory_info=f"{exchange_info['regulator']} regulated",
        )
    
    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        获取欧洲股票增强数据
        
        包含历史数据、实时行情
        
        Args:
            stock_code: 欧洲股票代码
            days: 历史数据天数
            
        Returns:
            增强数据字典
        """
        result = {
            'code': stock_code,
            'daily_data': None,
            'realtime_quote': None,
        }
        
        # 获取历史数据
        try:
            df = self.get_daily_data(stock_code, days=days)
            result['daily_data'] = df
        except Exception as e:
            logger.error(f"获取{stock_code}历史数据失败: {e}")
        
        # 获取实时行情
        result['realtime_quote'] = self.get_realtime_quote(stock_code)
        
        return result
    
    def get_market_indices(self, market: Market) -> List[Dict[str, str]]:
        """
        获取欧洲主要市场指数
        
        Args:
            market: 市场枚举
            
        Returns:
            指数列表
        """
        indices = {
            Market.UK_LSE: [
                {"code": "^UKX", "name": "FTSE 100", "symbol": "UKX"},
                {"code": "^MCX", "name": "FTSE 250", "symbol": "MCX"},
            ],
            Market.GER_XETRA: [
                {"code": "^GDAXI", "name": "DAX", "symbol": "DAX"},
                {"code": "^MDAXI", "name": "MDAX", "symbol": "MDAX"},
            ],
            Market.FRA_EURONEXT: [
                {"code": "^FCHI", "name": "CAC 40", "symbol": "CAC 40"},
            ],
            Market.SWX_SIX: [
                {"code": "^SSMI", "name": "SMI", "symbol": "SMI"},
            ],
            Market.EURONEXT: [
                {"code": "^AEX", "name": "AEX", "symbol": "AEX"},
            ],
        }
        
        return indices.get(market, [])


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = EUStockFetcher()
    
    # 测试欧洲股票历史数据
    print("=" * 50)
    print("测试欧洲股票历史数据获取")
    print("=" * 50)
    
    test_stocks = ["VOD.L", "SAP.DE", "ASML.AS", "NESN.SW", "MC.PA"]
    
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
    print("测试欧洲股票实时行情获取")
    print("=" * 50)
    
    for stock in ["VOD.L", "SAP.DE"]:
        quote = fetcher.get_realtime_quote(stock)
        if quote:
            print(f"[{stock}] {quote.name}: {quote.currency}{quote.price:.2f} ({quote.change_pct:+.2f}%)")
            print(f"  交易所: {quote.exchange}, 国家: {quote.country}")
        else:
            print(f"[{stock}] 未获取到实时行情")
    
    # 测试指数信息
    print("\n" + "=" * 50)
    print("测试欧洲市场指数获取")
    print("=" * 50)
    
    for market in [Market.UK_LSE, Market.GER_XETRA, Market.FRA_EURONEXT]:
        indices = fetcher.get_market_indices(market)
        print(f"{market.get_display_name()} 指数:")
        for idx in indices:
            print(f"  - {idx['name']} ({idx['symbol']})")
