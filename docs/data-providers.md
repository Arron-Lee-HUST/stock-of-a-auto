# 行情数据供应商接入

## 统一契约

- `MarketDataProvider.get_bars(symbols, start_date, end_date)` 返回标准 `DailyBar`，日期升序，价格为人民币元。
- `PointInTimeContextProvider` 为竞价、分时、资金流和板块情绪提供可选补充数据。
- 缺失字段必须为 `None`，不可用 0 伪造。
- 每个补充数据必须带交易日期，且不得包含决策时点之后的信息。

## CSV

CSV 适合离线研究、回测和供应商数据落盘。格式见 `docs/data-backtest.md`。

## Tushare Pro

安装：`pip install 'stock-of-a-auto[tushare]'`。设置环境变量 `TUSHARE_TOKEN`，不要把 Token 写入代码、配置文件或提交记录。

```python
from stock_auto.providers import TushareMarketDataProvider

provider = TushareMarketDataProvider()
bars = provider.get_bars(["sh600000", "sz000001"], "2024-01-01", "2024-12-31")
```

Tushare 的日线成交量单位为手、成交额单位为千元；适配器统一转换为股和人民币元。证券代码转换为 `sh600000` / `sz000001`。当前 `limit_pct` 是普通主板默认值，不足以准确覆盖创业板、科创板、北交所、ST 和上市初期；生产数据需从交易日维度维护真实涨跌幅规则。

## 竞价、分时、资金流和板块数据

本项目只定义标准数据结构和协议，不假设某个供应商能稳定、合法、完整提供这些字段。后续供应商实现应遵守授权条款、限频规则和历史数据可用性要求。

## 数据质量要求

- 校验证券代码、日期、重复记录、OHLC 逻辑、停牌和异常成交量。
- 复权序列仅用于指标计算；成交模拟使用真实未复权价格。
- 历史资金流、板块排名、事件催化必须保存当时可见版本，禁止使用事后修订数据回填历史。
- 生产运行需记录供应商、抓取时间、数据版本和缺失率。
