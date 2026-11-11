# 历史数据与回测模块

## 数据接入

核心层定义 `MarketDataProvider` 协议和 `DailyBar` 标准日线模型。当前提供 `CsvMarketDataProvider`，不绑定任何行情供应商；后续可按授权、成本和稳定性增加 TuShare、AKShare 或券商数据适配器。

CSV 必需列：`symbol,trade_date,open,high,low,close,volume`。可选列：`amount,prev_close,is_suspended,limit_pct`。日期使用 `YYYY-MM-DD`，价格为人民币元，成交量单位由数据源统一约定并在数据字典中记录。建议使用未复权 OHLC 进行成交模拟，指标计算可另行使用前复权序列；不得混用复权价格与真实成交价格。

## 回测时序与约束

- 信号在交易日收盘后产生，只能读取当日及以前的数据。
- 委托在下一交易日开盘价执行，并应用滑点；不允许用当日收盘价生成信号又按当日收盘价成交。
- T+1：当日买入的持仓不能在同一交易日卖出。
- 默认涨停价不买、跌停价不卖；停牌股票不成交。
- 默认佣金 3bp、卖出印花税 5bp、滑点 10bp、最低佣金 5 元。以上仅为可配置的研究假设，实际费用按账户与交易所最新规则校准。
- 默认每笔不超过初始资金 20%，最多同时持有 5 只，按 100 股整数手取整。
- 未平仓持仓在回测结束日按收盘价估值，不强制平仓。

涨跌停价由 `prev_close * (1 ± limit_pct)` 估算。真实 A 股规则因板块、股票风险警示状态、上市阶段和交易日期而异，数据应显式提供 `limit_pct`；本版本不是交易所规则引擎。

## 使用示例

```python
from stock_auto.data import CsvMarketDataProvider
from stock_auto.backtest import BacktestEngine

provider = CsvMarketDataProvider("data/daily.csv")
bars = provider.get_bars(["sh600000"], "2024-01-01", "2024-12-31")
result = BacktestEngine().run(
    bars,
    entry_selector=lambda date, history: [],  # 在此接入三驱策略信号
    exit_selector=lambda date, position, history: False,
)
print(result.total_return_pct, result.max_drawdown_pct, result.win_rate_pct)
```

## 指标

结果包含总收益率、最大回撤、胜率、盈亏比、逐笔交易、权益曲线和未成交订单原因。盈亏比在没有亏损交易时返回正无穷（若无盈利交易则为 0）。

## 风险边界

回测结果依赖数据质量、复权方式、交易日历、涨跌停规则和费用假设。当前版本不自动下载数据、不预测收益、不接券商、不自动下单。任何策略上线前都应做样本外验证、滚动验证、模拟盘和人工复核。
