# 三驱自动选股

`CandidateScanner` 接收某一交易日及之前的标准日线数据，计算 MA5/10/20、近 5 日均量、涨幅、振幅、近期涨停和前 20 个交易日高点，再调用三驱评分引擎。

```python
from stock_auto.data import CsvMarketDataProvider
from stock_auto.scanner import CandidateScanner

provider = CsvMarketDataProvider("data/daily.csv")
bars = provider.get_bars(["sh600000", "sz000001"], "2024-01-01", "2024-12-31")
result = CandidateScanner().scan(bars, "2024-12-31")
for item in result.candidates:
    print(item.snapshot.symbol, item.signal.score, item.signal.reasons)
```

## 排序与缺失数据

候选按综合评分、趋势分、资金分、情绪分降序排列。缺少资金流或板块情绪时，相关字段保持 None，三驱评分会拒绝不完整候选；这意味着只接入日线的 CSV/Tushare 日线源不能单独产生合格候选。必须提供可信的资金流和板块上下文适配器。

## Point-in-time 约束

- 仅使用 trade_date 当天及之前的日线。
- 均线和均量只使用截至当日已完成的数据。
- prior_high 不包含当日最高价，避免把当日突破的结果作为先验条件。
- 竞价、分时、资金流和板块情绪必须来自带交易日期的上下文 Provider，并保证该字段在信号生成时已可见。
