# -*- coding: utf-8 -*-
"""
简化版主程序 - 专注于数据获取和展示
在缺少依赖时提供完整功能
"""

import logging
import sys
import os
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def setup_data_source():
    """设置数据源"""
    try:
        from data_provider.simple_manager import DataFetcherManager
        manager = DataFetcherManager()
        logger.info(f"✅ 使用模拟数据源: {manager.available_fetchers}")
        return manager, "Mock"
    except Exception as e:
        logger.error(f"❌ 数据源设置失败: {e}")
        return None, "Failed"

def format_stock_info(stock_code, df, source):
    """格式化股票信息"""
    if df is None or df.empty:
        return f"❌ {stock_code}: 数据获取失败"
    
    # 基本信息
    latest = df.iloc[-1]
    info = []
    
    # 头部信息
    info.append(f"📈 {stock_code} 数据报告")
    info.append(f"📊 数据源: {source}")
    info.append(f"📅 数据条数: {len(df)} 条")
    info.append("")
    
    # 价格信息
    info.append("💰 价格信息:")
    info.append(f"   最新价格: {latest['close']:.2f}")
    info.append(f"   涨跌幅: {latest['pct_chg']:+.2f}%")
    info.append(f"   开盘: {latest['open']:.2f}")
    info.append(f"   最高: {latest['high']:.2f}")
    info.append(f"   最低: {latest['low']:.2f}")
    info.append("")
    
    # 成交量信息
    info.append("📊 成交信息:")
    info.append(f"   成交量: {latest['volume']:,}")
    info.append(f"   成交额: {latest['amount']:,.0f}")
    info.append(f"   量比: {latest.get('volume_ratio', 1.0):.2f}")
    info.append("")
    
    # 技术指标
    info.append("📈 技术指标:")
    info.append(f"   MA5: {latest['ma5']:.2f}")
    info.append(f"   MA10: {latest['ma10']:.2f}")
    info.append(f"   MA20: {latest['ma20']:.2f}")
    info.append("")
    
    # 趋势分析
    ma5 = latest['ma5']
    ma10 = latest['ma10']
    ma20 = latest['ma20']
    close = latest['close']
    
    trend_info = []
    if close > ma5 > ma10 > ma20:
        trend_info.append("✅ 多头排列")
        trend = "上涨"
    elif close < ma5 < ma10 < ma20:
        trend_info.append("❌ 空头排列")
        trend = "下跌"
    else:
        trend_info.append("➡️ 震荡排列")
        trend = "震荡"
    
    info.append("📊 趋势分析:")
    info.extend(f"   {item}" for item in trend_info)
    info.append(f"   当前趋势: {trend}")
    info.append("")
    
    # 时间范围
    date_range = f"{df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}"
    info.append(f"📅 时间范围: {date_range}")
    info.append("")
    
    # 价格合理性检查
    price = latest['close']
    stock_names = {
        '600519': '贵州茅台',
        '000001': '平安银行',
        '300750': '宁德时代',
        'AAPL': 'Apple Inc.',
        'TSLA': 'Tesla Inc.',
        'MSFT': 'Microsoft Corporation',
        'VOD.L': 'Vodafone Group',
        'SAP.DE': 'SAP SE',
    }
    
    stock_name = stock_names.get(stock_code, f"股票 {stock_code}")
    
    if stock_code.startswith(('600', '000', '300', '688')):  # A股
        if 10 <= price <= 500:
            price_check = "✅ 价格正常"
        else:
            price_check = f"⚠️ 价格异常: {price:.2f} (正常范围: 10-500)"
    elif stock_code.isalpha():  # 美股
        if 10 <= price <= 2000:
            price_check = "✅ 价格正常"
        else:
            price_check = f"⚠️ 价格异常: ${price:.2f} (正常范围: $10-2000)"
    else:
        price_check = "🔍 价格范围未知"
    
    info.append("🔍 数据质量检查:")
    info.append(f"   {price_check}")
    info.append(f"   公司名称: {stock_name}")
    
    return "\\n".join(info)

def analyze_single_stock(manager, stock_code):
    """分析单只股票"""
    logger.info(f"🔍 开始分析 {stock_code}")
    
    try:
        # 获取数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        df, source = manager.get_daily_data(stock_code, start_date=start_date, end_date=end_date, days=30)
        
        # 格式化并输出信息
        report = format_stock_info(stock_code, df, source)
        print(report)
        
        # 尝试获取实时行情
        if hasattr(manager, 'get_realtime_quote'):
            quote = manager.get_realtime_quote(stock_code)
            if quote:
                print(f"📊 实时行情: {quote['name']} ({quote['code']})")
                print(f"   当前价格: {quote['price']:.2f}")
                print(f"   涨跌幅: {quote['change_pct']:+.2f}%")
                print(f"   数据源: {quote.get('source', 'Unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 分析 {stock_code} 失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 股票数据获取和分析工具")
    print("=" * 50)
    
    # 设置数据源
    manager, source_type = setup_data_source()
    if manager is None:
        print("❌ 无法设置数据源，程序退出")
        return
    
    # 测试股票列表
    test_stocks = [
        "600519",  # 贵州茅台 - A股
        "000001",  # 平安银行 - A股
        "300750",  # 宁德时代 - A股
        "AAPL",    # 苹果 - 美股
        "TSLA",    # 特斯拉 - 美股
        "VOD.L",   # 沃达丰 - 英股
        "SAP.DE",  # SAP - 德股
    ]
    
    print(f"\\n🎯 开始分析 {len(test_stocks)} 只股票")
    print("=" * 50)
    
    success_count = 0
    total_count = len(test_stocks)
    
    for i, stock in enumerate(test_stocks, 1):
        print(f"\\n[{i}/{total_count}] 正在分析: {stock}")
        print("-" * 40)
        
        if analyze_single_stock(manager, stock):
            success_count += 1
    
    # 总结报告
    print("\\n" + "=" * 50)
    print("分析总结")
    print("=" * 50)
    print(f"成功分析: {success_count}/{total_count} 只股票")
    print(f"数据源类型: {source_type}")
    
    if success_count == total_count:
        print("所有股票分析完成！")
    else:
        print(f"警告: {total_count - success_count} 只股票分析失败")
    
    print("\\n💡 提示:")
    print("- 当前使用模拟数据进行演示")
    print("- 要获取真实数据，请安装相应的依赖包")
    print("- 有关真实数据源配置，请查看文档")

if __name__ == "__main__":
    main()