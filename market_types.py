# -*- coding: utf-8 -*-
"""
===================================
市场枚举和工具模块
===================================

定义支持的市场类型和相关工具函数
"""

from enum import Enum
from typing import Optional, Dict, Any, List
import re
import logging
import datetime

logger = logging.getLogger(__name__)


class Market(Enum):
    """股票市场枚举"""
    
    # 中国市场
    CHINA_A = "CN_A"          # A股市场
    HONG_KONG = "HK"          # 港股市场
    
    # 美国市场
    US_NYSE = "US_NYSE"       # 纽约证券交易所
    US_NASDAQ = "US_NASDAQ"   # 纳斯达克
    US_AMEX = "US_AMEX"       # 美国证券交易所
    
    # 欧洲市场
    UK_LSE = "UK_LSE"         # 伦敦证券交易所
    GER_XETRA = "GER_XETRA"   # 德国法兰克福交易所
    FRA_EURONEXT = "FRA_EURONEXT"  # 法国泛欧交易所
    SWX_SIX = "SWX_SIX"       # 瑞士证券交易所
    EURONEXT = "EURONEXT"     # 泛欧交易所（阿姆斯特丹）
    
    @classmethod
    def from_stock_code(cls, stock_code: str) -> 'Market':
        """
        根据股票代码推断市场
        
        Args:
            stock_code: 股票代码，如 '600519', 'AAPL', '0005.HK'
            
        Returns:
            对应的市场枚举
        """
        code = stock_code.upper().strip()
        
        # 港股识别
        if code.endswith('.HK') or (len(code) <= 5 and code.isdigit() and code.startswith('0')):
            return Market.HONG_KONG
        
        # A股识别
        if len(code) == 6 and code.isdigit():
            if code.startswith(('600', '601', '603', '688')):  # 沪市
                return Market.CHINA_A
            elif code.startswith(('000', '002', '300')):  # 深市
                return Market.CHINA_A
        
        # 美股识别
        if '.' in code:
            suffix = code.split('.')[-1]
            if suffix in ['NYSE', 'NASDAQ', 'AMEX']:
                return Market[f"US_{suffix}"]
        elif code.isalpha() and len(code) <= 5:
            # 无后缀的字母代码，默认为纳斯达克
            return Market.US_NASDAQ
        
        # 欧股识别（欧洲股票代码格式多样）
        if code.endswith('.L') or code.endswith('.LSE'):
            return Market.UK_LSE
        elif code.endswith('.DE') or code.endswith('.ETR'):
            return Market.GER_XETRA
        elif code.endswith('.PA') or code.endswith('.EN'):
            return Market.FRA_EURONEXT
        elif code.endswith('.SW') or code.endswith('.SI'):
            return Market.SWX_SIX
        elif code.endswith('.AS') or code.endswith('.NA'):
            return Market.EURONEXT
        
        # 默认情况，尝试通过前缀判断
        logger.warning(f"无法确定股票代码 {stock_code} 的市场，默认为A股")
        return Market.CHINA_A
    
    def get_display_name(self) -> str:
        """获取市场显示名称"""
        names = {
            Market.CHINA_A: "A股",
            Market.HONG_KONG: "港股",
            Market.US_NYSE: "美股(纽交所)",
            Market.US_NASDAQ: "美股(纳斯达克)",
            Market.US_AMEX: "美股(美交所)",
            Market.UK_LSE: "英股(伦敦)",
            Market.GER_XETRA: "德股(法兰克福)",
            Market.FRA_EURONEXT: "法股(泛欧)",
            Market.SWX_SIX: "瑞士股",
            Market.EURONEXT: "泛欧交易所",
        }
        return names.get(self, str(self))
    
    def get_currency(self) -> str:
        """获取市场主要货币"""
        currencies = {
            Market.CHINA_A: "CNY",
            Market.HONG_KONG: "HKD",
            Market.US_NYSE: "USD",
            Market.US_NASDAQ: "USD",
            Market.US_AMEX: "USD",
            Market.UK_LSE: "GBP",
            Market.GER_XETRA: "EUR",
            Market.FRA_EURONEXT: "EUR",
            Market.SWX_SIX: "CHF",
            Market.EURONEXT: "EUR",
        }
        return currencies.get(self, "USD")
    
    def get_timezone(self) -> str:
        """获取市场时区"""
        timezones = {
            Market.CHINA_A: "Asia/Shanghai",
            Market.HONG_KONG: "Asia/Hong_Kong",
            Market.US_NYSE: "America/New_York",
            Market.US_NASDAQ: "America/New_York",
            Market.US_AMEX: "America/New_York",
            Market.UK_LSE: "Europe/London",
            Market.GER_XETRA: "Europe/Berlin",
            Market.FRA_EURONEXT: "Europe/Paris",
            Market.SWX_SIX: "Europe/Zurich",
            Market.EURONEXT: "Europe/Amsterdam",
        }
        return timezones.get(self, "UTC")


class MarketRegion(Enum):
    """市场区域枚举"""
    
    ASIA = "ASIA"      # 亚洲
    AMERICAS = "AMERICAS"  # 美洲
    EUROPE = "EUROPE"  # 欧洲
    
    @classmethod
    def from_market(cls, market: Market) -> 'MarketRegion':
        """根据市场获取区域"""
        asia_markets = {Market.CHINA_A, Market.HONG_KONG}
        americas_markets = {Market.US_NYSE, Market.US_NASDAQ, Market.US_AMEX}
        
        if market in asia_markets:
            return cls.ASIA
        elif market in americas_markets:
            return cls.AMERICAS
        else:
            return cls.EUROPE


def normalize_stock_code(stock_code: str, target_market: Optional[Market] = None) -> str:
    """
    标准化股票代码格式
    
    Args:
        stock_code: 原始股票代码
        target_market: 目标市场（可选），如果提供则转换为该市场的标准格式
        
    Returns:
        标准化后的股票代码
    """
    code = stock_code.upper().strip()
    
    if target_market is None:
        target_market = Market.from_stock_code(code)
    
    # 移除现有后缀
    if '.' in code:
        code = code.split('.')[0]
    
    # 根据目标市场添加标准后缀
    if target_market in [Market.US_NYSE, Market.US_NASDAQ, Market.US_AMEX]:
        # 美股通常不需要后缀，但如果有明确指定，则添加
        if target_market == Market.US_NYSE:
            return f"{code}.NYSE"
        elif target_market == Market.US_NASDAQ:
            return f"{code}.NASDAQ"
        elif target_market == Market.US_AMEX:
            return f"{code}.AMEX"
        return code
    
    elif target_market == Market.HONG_KONG:
        # 港股统一为5位数字
        if code.isdigit():
            return code.zfill(5)
        return code
    
    elif target_market in [Market.UK_LSE, Market.GER_XETRA, Market.FRA_EURONEXT, 
                          Market.SWX_SIX, Market.EURONEXT]:
        # 欧股添加相应后缀
        suffixes = {
            Market.UK_LSE: ".L",
            Market.GER_XETRA: ".DE",
            Market.FRA_EURONEXT: ".PA",
            Market.SWX_SIX: ".SW",
            Market.EURONEXT: ".AS"
        }
        return f"{code}{suffixes.get(target_market, '')}"
    
    else:
        # A股保持6位数字
        if code.isdigit():
            return code.zfill(6)
        return code


def is_market_trading_hours(market: Market, current_time: Optional[datetime] = None) -> bool:
    """
    检查指定市场是否在交易时间内
    
    Args:
        market: 市场
        current_time: 当前时间（可选），默认使用系统当前时间
        
    Returns:
        是否在交易时间内
    """
    from datetime import datetime
    
    if current_time is None:
        current_time = datetime.now()
    
    # 如果没有pytz，使用本地时间
    if pytz:
        # 将时间转换为目标市场时区
        market_tz = pytz.timezone(market.get_timezone())
        local_time = current_time.astimezone(market_tz)
    else:
        local_time = current_time
    
    # 检查是否为工作日
    if local_time.weekday() >= 5:  # 周六、周日
        return False
    
    # 各市场的交易时间
    trading_hours = {
        Market.CHINA_A: (9, 15, 15, 0),      # 9:30-11:30, 13:00-15:00
        Market.HONG_KONG: (9, 30, 16, 0),    # 9:30-12:00, 13:00-16:00
        Market.US_NYSE: (9, 30, 16, 0),     # 9:30-16:00 (EST)
        Market.US_NASDAQ: (9, 30, 16, 0),   # 9:30-16:00 (EST)
        Market.US_AMEX: (9, 30, 16, 0),     # 9:30-16:00 (EST)
        Market.UK_LSE: (8, 0, 16, 30),       # 8:00-16:30
        Market.GER_XETRA: (9, 0, 17, 30),   # 9:00-17:30
        Market.FRA_EURONEXT: (9, 0, 17, 30), # 9:00-17:30
    }
    
    if market not in trading_hours:
        logger.warning(f"未知市场 {market} 的交易时间")
        return False
    
    start_hour, start_min, end_hour, end_min = trading_hours[market]
    
    # 检查是否在交易时间内
    current_minutes = local_time.hour * 60 + local_time.minute
    start_minutes = start_hour * 60 + start_min
    end_minutes = end_hour * 60 + end_min
    
    return start_minutes <= current_minutes <= end_minutes


def get_market_indices(market: Market) -> List[Dict[str, Any]]:
    """
    获取主要市场指数
    
    Args:
        market: 市场
        
    Returns:
        指数列表，每个指数包含代码、名称等信息
    """
    indices = {
        Market.CHINA_A: [
            {"code": "000001.SH", "name": "上证指数", "symbol": "SH000001"},
            {"code": "399001.SZ", "name": "深证成指", "symbol": "SZ399001"},
            {"code": "399006.SZ", "name": "创业板指", "symbol": "SZ399006"},
        ],
        Market.HONG_KONG: [
            {"code": "HSI", "name": "恒生指数", "symbol": "^HSI"},
            {"code": "HSCEI", "name": "恒生国企指数", "symbol": "^HSCEI"},
            {"code": "HSTECH", "name": "恒生科技指数", "symbol": "^HSTECH"},
        ],
        Market.US_NYSE: [
            {"code": "DJI", "name": "道琼斯指数", "symbol": "^DJI"},
            {"code": "SPX", "name": "标普500指数", "symbol": "^GSPC"},
        ],
        Market.US_NASDAQ: [
            {"code": "IXIC", "name": "纳斯达克指数", "symbol": "^IXIC"},
            {"code": "NDX", "name": "纳斯达克100指数", "symbol": "^NDX"},
        ],
        Market.UK_LSE: [
            {"code": "UKX", "name": "富时100指数", "symbol": "^UKX"},
            {"code": "MCX", "name": "富时250指数", "symbol": "^MCX"},
        ],
        Market.GER_XETRA: [
            {"code": "DAX", "name": "德国DAX指数", "symbol": "^GDAXI"},
            {"code": "MDAX", "name": "德国MDAX指数", "symbol": "^MDAXI"},
        ],
    }
    
    return indices.get(market, [])


def validate_stock_code_format(stock_code: str, market: Market) -> bool:
    """
    验证股票代码格式是否符合指定市场规范
    
    Args:
        stock_code: 股票代码
        market: 目标市场
        
    Returns:
        是否符合格式要求
    """
    patterns = {
        Market.CHINA_A: r'^\d{6}$',
        Market.HONG_KONG: r'^\d{4,5}$',
        Market.US_NYSE: r'^[A-Z]{1,5}(\.NYSE)?$',
        Market.US_NASDAQ: r'^[A-Z]{1,5}(\.NASDAQ)?$',
        Market.US_AMEX: r'^[A-Z]{1,5}(\.AMEX)?$', 
        Market.UK_LSE: r'^[A-Z]{1,5}\.L$',
        Market.GER_XETRA: r'^[A-Z]{1,5}\.DE$',
        Market.FRA_EURONEXT: r'^[A-Z]{1,5}\.PA$',
        Market.SWX_SIX: r'^[A-Z]{1,5}\.SW$',
        Market.EURONEXT: r'^[A-Z]{1,5}\.AS$',
    }
    
    pattern = patterns.get(market)
    if not pattern:
        return False
    
    return bool(re.match(pattern, stock_code.upper()))


if __name__ == "__main__":
    # 测试代码
    test_codes = [
        "600519",      # A股
        "AAPL",        # 美股
        "0005.HK",     # 港股
        "VOD.L",       # 英股
        "SAP.DE",      # 德股
    ]
    
    print("=== 市场识别测试 ===")
    for code in test_codes:
        market = Market.from_stock_code(code)
        print(f"{code} -> {market.get_display_name()} ({market.value})")
    
    print("\n=== 交易时间检查 ===")
    from datetime import datetime
    current = datetime.now()
    for market in [Market.CHINA_A, Market.US_NASDAQ, Market.UK_LSE]:
        is_trading = is_market_trading_hours(market, current)
        print(f"{market.get_display_name()}: {'交易中' if is_trading else '休市'}")
    
    print("\n=== 指数获取测试 ===")
    for market in [Market.CHINA_A, Market.US_NASDAQ, Market.UK_LSE]:
        indices = get_market_indices(market)
        print(f"{market.get_display_name()} 指数:")
        for idx in indices:
            print(f"  - {idx['name']} ({idx['symbol']})")