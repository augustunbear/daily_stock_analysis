# 多市场股票分析支持

## 概述

本库已成功扩展支持全球主要股票市场，包括：

- 🇨🇳 **中国市场**：A股、港股
- 🇺🇸 **美国市场**：NYSE、NASDAQ、AMEX
- 🇪🇺 **欧洲市场**：伦敦、法兰克福、巴黎、苏黎世、阿姆斯特丹

## 核心功能

### 1. 智能市场识别
自动根据股票代码识别所属市场：

```python
from market_types import Market

# 自动识别市场
market = Market.from_stock_code("AAPL")        # → Market.US_NASDAQ
market = Market.from_stock_code("600519")       # → Market.CHINA_A  
market = Market.from_stock_code("VOD.L")        # → Market.UK_LSE
market = Market.from_stock_code("00700")        # → Market.HONG_KONG
```

### 2. 多市场数据源

#### 美股专用数据源 (USStockFetcher)
- **主数据源**：Yahoo Finance
- **备用数据源**：Alpha Vantage
- **特色功能**：
  - 盘前盘后交易数据
  - 财报日历提醒
  - 美股特有估值指标（EPS, P/E等）

#### 欧股专用数据源 (EUStockFetcher)
- **主数据源**：Yahoo Finance
- **备用数据源**：Alpha Vantage
- **支持交易所**：
  - 伦敦证券交易所 (LSE)
  - 德国法兰克福交易所 (XETRA)
  - 法国泛欧交易所 (EURONEXT)
  - 瑞士证券交易所 (SWX)
- **特色功能**：
  - 多币种支持（GBP, EUR, CHF）
  - 监管信息（FCA, BaFin等）
  - 自动货币转换

### 3. 智能路由系统

```python
from multi_market_manager import get_multi_market_manager

# 获取多市场数据源管理器
manager = get_multi_market_manager()

# 自动选择最合适的数据源
df, source = manager.get_daily_data("AAPL")    # 优先使用 USStockFetcher
df, source = manager.get_daily_data("VOD.L")   # 优先使用 EUStockFetcher
df, source = manager.get_daily_data("600519")  # 优先使用中国数据源
```

## 配置说明

### 环境变量配置

```bash
# Alpha Vantage API（美股、欧洲股市备用数据源）
ALPHA_VANTAGE_KEY=your_alpha_vantage_api_key

# 现有配置保持不变
STOCK_LIST=600519,AAPL,VOD.L,TSLA,SAP.DE
TUSHARE_TOKEN=your_tushare_token
GEMINI_API_KEY=your_gemini_api_key
```

### 自选股配置

现在支持混合市场的股票列表：

```bash
# 混合市场股票列表
STOCK_LIST=600519,000001,300750,      # A股
           00700,01810,               # 港股  
           AAPL,TSLA,MSFT,GOOGL,      # 美股
           VOD.L,SAP.DE,ASML.AS       # 欧股
```

## 数据源优先级

### 美股市场
1. **USStockFetcher** (Priority 10) - 美股专用，高优先级
2. **YfinanceFetcher** (Priority 11) - 通用数据源，美股备用

### 欧洲市场  
1. **EUStockFetcher** (Priority 11) - 欧股专用，高优先级
2. **YfinanceFetcher** (Priority 12) - 通用数据源，欧股备用

### 中国市场
1. **TushareFetcher** (Priority 0) - 配置Token时最高优先级
2. **EfinanceFetcher** (Priority 0) - 高优先级
3. **AkshareFetcher** (Priority 1) - 主要数据源
4. **YfinanceFetcher** (Priority 15) - 全球兜底数据源

## 使用示例

### 1. 获取美股数据

```python
from data_provider.us_stock_fetcher import USStockFetcher

fetcher = USStockFetcher()

# 获取历史数据
df = fetcher.get_daily_data("AAPL", days=30)

# 获取实时行情（含盘前盘后）
quote = fetcher.get_realtime_quote("AAPL")
print(f"价格: ${quote.price:.2f}")
print(f"盘前: ${quote.pre_market_price:.2f} ({quote.pre_market_change:+.2f}%)")

# 获取财报信息
earnings = fetcher.get_earnings_info("AAPL")
if earnings:
    print(f"下次财报: {earnings.earnings_date}")
```

### 2. 获取欧洲股票数据

```python
from data_provider.eu_stock_fetcher import EUStockFetcher

fetcher = EUStockFetcher()

# 获取历史数据
df = fetcher.get_daily_data("VOD.L", days=30)

# 获取实时行情（含货币信息）
quote = fetcher.get_realtime_quote("VOD.L")
print(f"价格: {quote.currency}{quote.price:.2f}")
print(f"交易所: {quote.exchange}")
print(f"监管: {quote.regulatory_info}")
```

### 3. 统一多市场接口

```python
from multi_market_manager import get_multi_market_manager

manager = get_multi_market_manager()

# 支持混合股票列表
stocks = ["600519", "AAPL", "VOD.L", "TSLA", "SAP.DE"]

for stock in stocks:
    try:
        df, source = manager.get_daily_data(stock, days=30)
        print(f"{stock}: 获取成功，数据源={source}, 数据条数={len(df)}")
    except Exception as e:
        print(f"{stock}: 获取失败 - {e}")
```

## 实时行情差异

### 美股实时行情
```python
USRealtimeQuote(
    code="AAPL",
    price=175.43,
    pre_market_price=175.20,     # 盘前价格
    pre_market_change=-0.13,     # 盘前变化
    pe_ratio=29.8,               # 市盈率
    eps=5.89,                    # 每股收益
    market_cap=2.8e12            # 市值
)
```

### 欧股实时行情
```python
EURealtimeQuote(
    code="VOD.L",
    price=85.67,
    currency="GBP",              # 货币
    exchange="London Stock Exchange",
    market_cap_usd=1.1e11,       # 美元市值
    regulatory_info="FCA regulated"  # 监管信息
)
```

## 时区和交易时间

系统自动处理不同市场的时区和交易时间：

```python
from market_types import is_market_trading_hours
from datetime import datetime

current_time = datetime.now()

is_cn_trading = is_market_trading_hours(Market.CHINA_A, current_time)
is_us_trading = is_market_trading_hours(Market.US_NASDAQ, current_time)
is_uk_trading = is_market_trading_hours(Market.UK_LSE, current_time)
```

## 注意事项

### API限制
- **Yahoo Finance**: 无官方API限制，但建议合理控制请求频率
- **Alpha Vantage**: 免费版每分钟5次请求，每日500次请求
- **Alpha Vantage配置**: `ALPHA_VANTAGE_KEY=your_key`

### 数据延迟
- **美股**: Yahoo Finance有15-20分钟延迟
- **欧股**: Yahoo Finance延迟可能更长
- **实时数据**: 建议订阅专业数据源以获取真正实时数据

### 货币处理
- 所有价格数据以本地货币显示
- 美股：美元(USD)
- 英股：英镑(GBP)  
- 德股/法股：欧元(EUR)
- 瑞士股：瑞士法郎(CHF)

## 测试脚本

运行完整的多市场测试：

```bash
python test_multi_market.py
```

测试包括：
- ✅ 市场识别功能
- ✅ 交易时间检查  
- ✅ 多市场数据获取
- ✅ 实时行情获取
- ✅ 增强数据（财报等）

## 故障排除

### 常见问题

1. **Alpha Vantage配额超限**
   ```
   解决方案：等待配额重置或升级到付费版
   ```

2. **Yahoo Finance延迟**
   ```python
   # 检查数据是否为空
   if df.empty:
       print("Yahoo Finance数据为空，尝试备用数据源")
   ```

3. **市场识别失败**
   ```python
   # 手动指定市场
   from market_types import normalize_stock_code, Market
   code = normalize_stock_code("AAPL", Market.US_NASDAQ)
   ```

## 贡献指南

欢迎贡献新的市场支持！

1. 在 `market_types.py` 中添加新市场枚举
2. 创建对应的数据源Fetcher类
3. 更新 `multi_market_manager.py` 的路由配置
4. 添加相应的测试用例

---

**扩展完成！** 🎉

现在您可以：
- 🌍 分析中美欧三大经济体股市
- 🔄 智能路由选择最优数据源  
- 💱 支持多币种多时区
- 📊 获取各市场特有的财务指标