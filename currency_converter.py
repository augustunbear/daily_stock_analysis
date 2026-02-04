# -*- coding: utf-8 -*-
"""
===================================
汇率转换模块
===================================

职责：
1. 获取当前汇率（USD/CNY, EUR/CNY, EUR/USD等）
2. 实时汇率转换功能
3. 缓存汇率数据避免频繁API调用
"""

import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path
import requests

from config import get_config

logger = logging.getLogger(__name__)


class ExchangeRateProvider:
    """汇率数据提供者"""
    
    def __init__(self):
        self.cache_file = Path("./data/exchange_rates.json")
        self.cache_duration = timedelta(hours=1)  # 缓存1小时
        self.rates_cache: Dict[str, Dict] = {}
        
    def _load_cache(self) -> Dict[str, Dict]:
        """加载缓存汇率"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    # 检查缓存是否过期
                    for provider, data in cached_data.items():
                        cached_time = datetime.fromisoformat(data.get('timestamp', '2020-01-01'))
                        if datetime.now() - cached_time < self.cache_duration:
                            self.rates_cache[provider] = data
                            logger.debug(f"加载缓存汇率 {provider}: {data.get('rates', {})}")
            except Exception as e:
                logger.warning(f"加载汇率缓存失败: {e}")
        return self.rates_cache
    
    def _save_cache(self, provider: str, rates: Dict[str, float]):
        """保存汇率到缓存"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_data = self.rates_cache.copy()
            cache_data[provider] = {
                'rates': rates,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"保存汇率缓存 {provider}: {rates}")
        except Exception as e:
            logger.warning(f"保存汇率缓存失败: {e}")
    
    def get_rates(self) -> Dict[str, float]:
        """获取汇率（主要对EUR的汇率）"""
        if 'api_rates' in self.rates_cache:
            return self.rates_cache['api_rates']['rates']
        
        # 默认汇率（2026年估算值，实际应该从API获取）
        default_rates = {
            'EUR': 1.0,  # 基准货币
            'CNY': 7.8,   # 1 EUR = 7.8 CNY
            'USD': 1.08,  # 1 EUR = 1.08 USD
            'GBP': 0.85,  # 1 EUR = 0.85 GBP
            'CHF': 0.93,  # 1 EUR = 0.93 CHF
            'HKD': 8.4,   # 1 EUR = 8.4 HKD
        }
        
        # 尝试从API获取
        try:
            rates = self._fetch_from_api()
            if rates:
                self.rates_cache['api_rates'] = {
                    'rates': rates,
                    'timestamp': datetime.now().isoformat()
                }
                self._save_cache('api_rates', rates)
                return rates
        except Exception as e:
            logger.warning(f"获取汇率API失败: {e}，使用默认汇率")
        
        # 使用默认汇率
        self.rates_cache['default'] = {
            'rates': default_rates,
            'timestamp': datetime.now().isoformat()
        }
        return default_rates
    
    def _fetch_from_api(self) -> Optional[Dict[str, float]]:
        """从API获取汇率"""
        # 使用免费的汇率API（如exchangerate-api.com）
        try:
            # 这里可以替换为其他API
            url = "https://api.exchangerate-api.com/v4/latest/EUR"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('rates', {})
        except Exception as e:
            logger.warning(f"汇率API调用失败: {e}")
        
        return None


class CurrencyConverter:
    """货币转换器 - 人民币仅限A股，其余统一欧元显示"""
    
    def __init__(self):
        self.provider = ExchangeRateProvider()
        self.rates = self.provider.get_rates()
        self.target_currencies = {
            'CN_A': 'CNY',      # 中国A股用人民币
            'HK': 'EUR',         # 港股统一换算为欧元
            'US_NYSE': 'EUR',    # 美股用欧元
            'US_NASDAQ': 'EUR',  # 美股用欧元
            'US_AMEX': 'EUR',    # 美股用欧元
            'UK_LSE': 'EUR',     # 英股用欧元
            'GER_XETRA': 'EUR',  # 德股用欧元
            'FRA_EURONEXT': 'EUR', # 法股用欧元
            'SWX_SIX': 'EUR',   # 瑞士股用欧元
            'EURONEXT': 'EUR',  # 泛欧交易所用欧元
        }
    
    def get_target_currency(self, market: str) -> str:
        """根据市场获取目标显示货币"""
        return self.target_currencies.get(market, 'EUR')
    
    def convert_amount(
        self, 
        amount: float, 
        from_currency: str, 
        to_currency: str
    ) -> Tuple[float, float]:
        """
        转换金额
        
        Args:
            amount: 原始金额
            from_currency: 原始货币
            to_currency: 目标货币
            
        Returns:
            (转换后金额, 汇率)
        """
        if from_currency == to_currency:
            return amount, 1.0
        
        # 通过EUR作为中介货币进行转换
        from_to_eur = 1.0 / self.rates.get(from_currency, 1.0)
        eur_to_target = self.rates.get(to_currency, 1.0)
        exchange_rate = from_to_eur * eur_to_target
        
        converted_amount = amount * exchange_rate
        return converted_amount, exchange_rate
    
    def format_amount(
        self, 
        amount: float, 
        from_currency: str,
        to_currency: Optional[str] = None,
        show_exchange_rate: bool = False
    ) -> str:
        """
        格式化金额显示
        
        Args:
            amount: 原始金额
            from_currency: 原始货币
            to_currency: 目标货币（可选）
            show_exchange_rate: 是否显示汇率
            
        Returns:
            格式化后的金额字符串
        """
        if to_currency is None:
            to_currency = from_currency
        
        if from_currency == to_currency:
            # 不需要转换
            formatted = self._format_currency(amount, to_currency)
            if show_exchange_rate:
                formatted += " (1:1)"
            return formatted
        
        converted_amount, exchange_rate = self.convert_amount(amount, from_currency, to_currency)
        formatted = self._format_currency(converted_amount, to_currency)
        
        if show_exchange_rate:
            formatted += f" (1 {from_currency} = {exchange_rate:.4f} {to_currency})"
        
        return formatted
    
    def _format_currency(self, amount: float, currency: str) -> str:
        """格式化特定货币的显示"""
        currency_units = {
            "CNY": {"price": "元", "ten_thousand": "万元", "hundred_million": "亿元"},
            "HKD": {"price": "港元", "ten_thousand": "万港元", "hundred_million": "亿港元"},
            "USD": {"price": "美元", "ten_thousand": "万美元", "hundred_million": "亿美元"},
            "EUR": {"price": "欧元", "ten_thousand": "万欧元", "hundred_million": "亿欧元"},
            "GBP": {"price": "英镑", "ten_thousand": "万英镑", "hundred_million": "亿英镑"},
            "CHF": {"price": "瑞郎", "ten_thousand": "万瑞郎", "hundred_million": "亿瑞郎"},
        }
        
        units = currency_units.get(currency, {
            "price": currency,
            "ten_thousand": f"万{currency}",
            "hundred_million": f"亿{currency}",
        })
        
        if abs(amount) >= 1e8:
            return f"{amount / 1e8:.2f} {units['hundred_million']}"
        elif abs(amount) >= 1e4:
            return f"{amount / 1e4:.2f} {units['ten_thousand']}"
        else:
            return f"{amount:.2f} {units['price']}"
    
    def convert_stock_data(
        self, 
        data: Dict, 
        market: str, 
        original_currency: Optional[str] = None
    ) -> Dict:
        """
        转换股票数据中的货币字段
        
        Args:
            data: 股票数据字典
            market: 市场类型
            original_currency: 原始货币（可选，会尝试推断）
            
        Returns:
            转换后的数据字典
        """
        if original_currency is None:
            # 从市场推断原始货币
            market_currency_map = {
                'CN_A': 'CNY',
                'HK': 'HKD', 
                'US_NYSE': 'USD',
                'US_NASDAQ': 'USD',
                'US_AMEX': 'USD',
                'UK_LSE': 'GBP',
                'GER_XETRA': 'EUR',
                'FRA_EURONEXT': 'EUR',
                'SWX_SIX': 'CHF',
                'EURONEXT': 'EUR',
            }
            original_currency = market_currency_map.get(market, 'USD')
        
        target_currency = self.get_target_currency(market)
        
        # 如果目标货币和原始货币相同，不需要转换
        if original_currency == target_currency:
            return data.copy()
        
        converted_data = data.copy()
        
        # 需要转换的字段
        money_fields = [
            'open', 'high', 'low', 'close', 'pre_close',
            'amount', 'total_mv', 'circ_mv'
        ]
        
        for field in money_fields:
            if field in converted_data and converted_data[field] is not None:
                try:
                    amount = float(converted_data[field])
                    converted_amount, _ = self.convert_amount(
                        amount, original_currency, target_currency
                    )
                    converted_data[field] = converted_amount
                except (ValueError, TypeError):
                    logger.warning(f"无法转换字段 {field}: {converted_data[field]}")
        
        # 添加转换信息
        converted_data['_currency_info'] = {
            'original_currency': original_currency,
            'display_currency': target_currency,
            'exchange_rate': self.rates.get(target_currency, 1.0)
        }
        
        return converted_data
    
    def refresh_rates(self):
        """刷新汇率"""
        logger.info("刷新汇率数据...")
        self.rates = self.provider.get_rates()
        logger.info(f"当前汇率: {self.rates}")


# 全局实例
_converter_instance: Optional[CurrencyConverter] = None


def get_currency_converter() -> CurrencyConverter:
    """获取全局货币转换器实例"""
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = CurrencyConverter()
    return _converter_instance


def convert_for_display(
    amount: float, 
    from_currency: str, 
    market: str, 
    show_rate: bool = False
) -> str:
    """
    便捷函数：根据市场转换并格式化金额显示
    
    Args:
        amount: 金额
        from_currency: 原始货币
        market: 市场类型
        show_rate: 是否显示汇率
        
    Returns:
        格式化后的金额字符串
    """
    converter = get_currency_converter()
    target_currency = converter.get_target_currency(market)
    
    return converter.format_amount(
        amount, from_currency, target_currency, show_rate
    )


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    converter = get_currency_converter()
    
    print("=== 货币转换测试 ===")
    print(f"当前汇率: {converter.rates}")
    
    # 测试转换
    test_cases = [
        (1000, 'USD', 'US_NASDAQ'),    # 美股：USD转EUR
        (1000, 'CNY', 'CN_A'),         # 中国股票：CNY保持
        (1000, 'HKD', 'HK'),           # 港股：HKD转CNY
        (1000, 'GBP', 'UK_LSE'),       # 英股：GBP转EUR
        (1000, 'EUR', 'GER_XETRA'),     # 德股：EUR保持
    ]
    
    for amount, from_curr, market in test_cases:
        target_curr = converter.get_target_currency(market)
        result = converter.format_amount(amount, from_curr, target_curr, True)
        print(f"{market} {amount} {from_curr} -> {result}")
