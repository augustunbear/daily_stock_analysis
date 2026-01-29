# -*- coding: utf-8 -*-
"""
数据源调试脚本
检查数据获取是否正常
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

def test_data_sources():
    """测试各种数据源"""
    print("=== 数据源测试 ===")
    
    # 测试基础数据源管理器
    try:
        from data_provider import DataFetcherManager
        print("✅ DataFetcherManager 导入成功")
    except Exception as e:
        print(f"❌ DataFetcherManager 导入失败: {e}")
        return
    
    # 创建管理器
    try:
        manager = DataFetcherManager()
        print(f"✅ 数据源管理器创建成功")
        print(f"可用数据源: {manager.available_fetchers}")
    except Exception as e:
        print(f"❌ 数据源管理器创建失败: {e}")
        return
    
    # 测试几个常见股票代码
    test_stocks = [
        "600519",  # 茅台 - A股
        "000001",  # 平安银行 - A股
        "AAPL",    # 苹果 - 美股
        "TSLA",    # 特斯拉 - 美股
    ]
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    print(f"\n=== 数据获取测试 ({start_date} ~ {end_date}) ===")
    
    for stock in test_stocks:
        print(f"\n🔍 测试股票: {stock}")
        try:
            df, source = manager.get_daily_data(stock, start_date=start_date, end_date=end_date)
            
            if df is not None and not df.empty:
                print(f"✅ {stock}: 获取成功")
                print(f"   数据源: {source}")
                print(f"   数据条数: {len(df)}")
                print(f"   日期范围: {df['date'].min()} ~ {df['date'].max()}")
                print(f"   最新价格: {df['close'].iloc[-1]:.2f}")
                print(f"   最新成交量: {df['volume'].iloc[-1]}")
                
                # 检查价格合理性
                latest_price = df['close'].iloc[-1]
                if stock.startswith(('600', '000', '300', '688')):  # A股
                    if latest_price > 1000 or latest_price < 0.1:
                        print(f"⚠️  价格异常: {latest_price:.2f}")
                    else:
                        print(f"✅ 价格正常: {latest_price:.2f}")
                elif stock.isalpha():  # 美股
                    if latest_price > 10000 or latest_price < 0.1:
                        print(f"⚠️  价格异常: {latest_price:.2f}")
                    else:
                        print(f"✅ 价格正常: ${latest_price:.2f}")
            else:
                print(f"❌ {stock}: 获取失败 - 数据为空")
                
        except Exception as e:
            print(f"❌ {stock}: 获取异常 - {str(e)}")

def test_akshare_directly():
    """直接测试Akshare"""
    print("\n=== 直接测试 Akshare ===")
    
    try:
        import akshare as ak
        print("✅ Akshare 导入成功")
        
        # 测试获取单只股票数据
        df = ak.stock_zh_a_hist(symbol="600519", period="daily", 
                               start_date="20240101", end_date="20240131", adjust="qfq")
        
        if df is not None and not df.empty:
            print(f"✅ Akshare 直接获取成功")
            print(f"   数据条数: {len(df)}")
            print(f"   列名: {list(df.columns)}")
            print(f"   最新几行数据:")
            print(df.tail(3))
        else:
            print("❌ Akshare 直接获取失败")
            
    except Exception as e:
        print(f"❌ Akshare 直接测试失败: {e}")

def test_market_recognition():
    """测试市场识别"""
    print("\n=== 市场识别测试 ===")
    
    try:
        from market_types import Market
        print("✅ Market 枚举导入成功")
        
        test_codes = ["600519", "AAPL", "VOD.L", "00700"]
        
        for code in test_codes:
            market = Market.from_stock_code(code)
            print(f"{code} -> {market.get_display_name()} ({market.value})")
            
    except Exception as e:
        print(f"❌ 市场识别测试失败: {e}")

if __name__ == "__main__":
    print("🚀 开始数据源调试...")
    
    test_market_recognition()
    test_data_sources()
    test_akshare_directly()
    
    print("\n🏁 调试完成！")