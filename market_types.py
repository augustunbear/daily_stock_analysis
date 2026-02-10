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
from datetime import datetime

logger = logging.getLogger(__name__)


_COMMON_STOCK_ALIASES: Dict[str, str] = {
    # US stocks (common company names)
    "microsoft": "MSFT",
    "ms": "MSFT",
    "apple": "AAPL",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "nvidia": "NVDA",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "berkshirehathaway": "BRK.B",
    "berkshire": "BRK.B",
    "brkb": "BRK.B",
    # Chinese company names (common A-share examples)
    "贵州茅台": "600519",
    "平安银行": "000001",
    "宁德时代": "300750",
    "比亚迪": "002594",
    "招商银行": "600036",
    "中国平安": "601318",
    "五粮液": "000858",
    "恒瑞医药": "600276",
    "隆基绿能": "601012",
    "立讯精密": "002475",
    "东方财富": "300059",
    "海康威视": "002415",
    "长江电力": "600900",
    "兴业银行": "601166",
    "中国石化": "600028",
    # Chinese aliases for US stocks
    "微软": "MSFT",
    "微软公司": "MSFT",
    "苹果": "AAPL",
    "苹果公司": "AAPL",
    "谷歌": "GOOGL",
    "亚马逊": "AMZN",
    "特斯拉": "TSLA",
    "英伟达": "NVDA",
    "脸书": "META",
    "奈飞": "NFLX",
    "伯克希尔": "BRK.B",
}

_IDENTIFIER_RESOLVE_CACHE: Dict[str, Optional[str]] = {}


def _alias_key(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"[\s\-_.(),&'\"`]+", "", cleaned)
    return cleaned


def _looks_like_stock_code(value: str) -> bool:
    code = value.strip()
    if not code:
        return False
    if re.match(r"^HK\d{4,5}$", code.upper()):
        return True
    if re.match(r"^\d{4,6}(\.[A-Za-z]{1,5})?$", code):
        return True
    if re.match(r"^[A-Za-z]{1,5}(\.[A-Za-z]{1,5})?$", code):
        return True
    return False


def is_isin_code(value: str) -> bool:
    """判断是否为 ISIN（12位，末位校验位）"""
    if not value:
        return False
    code = value.strip().upper()
    return bool(re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", code))


def is_wkn_code(value: str) -> bool:
    """判断是否为 WKN（6位字母数字，可全数字）。"""
    if not value:
        return False
    code = value.strip().upper()
    return bool(re.match(r"^[A-Z0-9]{6}$", code))


def _is_mainland_a_share_code(code: str) -> bool:
    """判断是否是常见 A 股 6 位代码。"""
    if not re.match(r"^\d{6}$", code):
        return False
    return code.startswith((
        "600", "601", "603", "605", "688", "689",  # 沪市/科创板
        "000", "001", "002", "003", "300", "301",  # 深市/创业板
    ))


def _lookup_symbol_by_identifier(identifier: str) -> Optional[str]:
    """通过 Yahoo Finance 搜索接口将 ISIN/WKN 解析为股票代码。"""
    cache_key = identifier.upper().strip()
    if cache_key in _IDENTIFIER_RESOLVE_CACHE:
        return _IDENTIFIER_RESOLVE_CACHE[cache_key]

    resolved_symbol: Optional[str] = None

    try:
        import requests

        response = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={
                "q": cache_key,
                "quotesCount": 10,
                "newsCount": 0,
            },
            timeout=6,
            headers={
                "User-Agent": "Mozilla/5.0",
            },
        )
        if response.status_code == 200:
            payload = response.json()
            quotes = payload.get("quotes") or []

            candidates: List[str] = []
            for quote in quotes:
                symbol = str(quote.get("symbol") or "").strip().upper()
                quote_type = str(quote.get("quoteType") or "").upper()
                if not symbol:
                    continue
                if quote_type and quote_type not in {"EQUITY", "ETF", "MUTUALFUND"}:
                    continue
                candidates.append(symbol)

            def _score_symbol(symbol: str) -> int:
                score = 0
                ident = cache_key

                # 通用偏好：更像主板股票代码
                if re.match(r"^[A-Z]{1,6}$", symbol):
                    score += 30
                if re.match(r"^[A-Z0-9]{1,8}\.[A-Z]{1,5}$", symbol):
                    score += 10

                # 按 ISIN 国家前缀做市场偏好
                if is_isin_code(ident):
                    country = ident[:2]
                    if country == "US":
                        # 美股优先：AAPL / BRK.B / XXX.NYSE
                        if re.match(r"^[A-Z]{1,5}(\.[A-Z])?$", symbol):
                            score += 60
                        if symbol.endswith((".NYSE", ".NASDAQ", ".AMEX")):
                            score += 50
                        if symbol.endswith((".DE", ".F", ".L", ".PA", ".SW", ".AS")):
                            score -= 30
                    elif country == "DE":
                        if symbol.endswith((".DE", ".F")):
                            score += 60
                    elif country == "GB":
                        if symbol.endswith(".L"):
                            score += 60
                    elif country == "FR":
                        if symbol.endswith(".PA"):
                            score += 60
                    elif country == "CH":
                        if symbol.endswith(".SW"):
                            score += 60
                    elif country == "NL":
                        if symbol.endswith(".AS"):
                            score += 60

                # WKN 常见于德国市场
                elif is_wkn_code(ident):
                    if symbol.endswith((".DE", ".F")):
                        score += 40

                return score

            if candidates:
                resolved_symbol = max(candidates, key=_score_symbol)

    except Exception as exc:
        logger.warning(f"通过标识符 {cache_key} 解析股票代码失败: {exc}")

    if resolved_symbol:
        logger.info(f"标识符解析成功: {cache_key} -> {resolved_symbol}")
    else:
        logger.warning(f"标识符解析失败: {cache_key}")

    _IDENTIFIER_RESOLVE_CACHE[cache_key] = resolved_symbol
    return resolved_symbol


def _calculate_isin_check_digit(isin_without_check: str) -> str:
    """计算 ISIN 校验位（Luhn 算法）。"""
    expanded = ""
    for ch in isin_without_check.upper():
        if ch.isdigit():
            expanded += ch
        elif "A" <= ch <= "Z":
            expanded += str(ord(ch) - ord("A") + 10)
        else:
            raise ValueError(f"ISIN 包含非法字符: {ch}")

    # 末位先补 0 参与校验，计算真实 check digit
    digits = expanded + "0"
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
        total += (n // 10) + (n % 10)
    return str((10 - (total % 10)) % 10)


def _wkn_to_german_isin(wkn: str) -> Optional[str]:
    """将 WKN 转换为德国 ISIN（DE000 + WKN + 校验位）。"""
    normalized = wkn.strip().upper()
    if not is_wkn_code(normalized):
        return None
    body = f"DE000{normalized}"
    try:
        check_digit = _calculate_isin_check_digit(body)
    except Exception:
        return None
    return f"{body}{check_digit}"


def _resolve_wkn_symbol(wkn: str) -> Optional[str]:
    """解析 WKN 到股票代码（优先直查，其次转换为 ISIN 再查）。"""
    resolved = _lookup_symbol_by_identifier(wkn)
    if resolved:
        return resolved

    # 针对美股等非德股场景，增加关键词检索兜底
    for query in (f"WKN {wkn}", f"{wkn} stock", f"{wkn} aktie"):
        resolved = _lookup_symbol_by_identifier(query)
        if resolved:
            return resolved

    german_isin = _wkn_to_german_isin(wkn)
    if german_isin:
        return _lookup_symbol_by_identifier(german_isin)
    return None


def resolve_stock_alias(stock_input: str) -> Optional[str]:
    """
    根据公司名称或常见别名解析为股票代码（若无匹配则返回 None）
    """
    if not stock_input:
        return None
    raw = stock_input.strip()
    if _looks_like_stock_code(raw):
        # 兼容德股 WKN 全数字场景：若不是常见 A 股前缀，尝试按 WKN 解析
        if re.match(r"^\d{6}$", raw) and not _is_mainland_a_share_code(raw):
            resolved_from_wkn = _resolve_wkn_symbol(raw)
            if resolved_from_wkn:
                return resolved_from_wkn
        return None
    key = _alias_key(raw)
    alias = _COMMON_STOCK_ALIASES.get(key) or _COMMON_STOCK_ALIASES.get(raw.strip())
    if alias:
        logger.info(f"股票名称别名解析: {stock_input} -> {alias}")
        return alias

    # 扩展支持：ISIN / WKN -> 股票代码（常用于德股）
    if is_isin_code(raw):
        return _lookup_symbol_by_identifier(raw)

    if is_wkn_code(raw):
        return _resolve_wkn_symbol(raw)

    return None


def normalize_stock_input(stock_input: str) -> str:
    """将输入标准化为可分析的股票代码（无法解析则返回原值）。"""
    raw = (stock_input or "").strip()
    if not raw:
        return ""
    resolved = resolve_stock_alias(raw)
    return resolved or raw


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
    try:
        import pytz
        if pytz:
            # 将时间转换为目标市场时区
            market_tz = pytz.timezone(market.get_timezone())
            local_time = current_time.astimezone(market_tz)
        else:
            local_time = current_time
    except ImportError:
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
