# 模拟盘

`PaperBroker` 是本地确定性模拟账户，不连接券商，不使用真实资金。它支持：

- 本地订单登记和订单 ID 幂等；
- 下一交易日开盘模拟成交、滑点、佣金和卖出印花税；
- A 股 100 股整数手、停牌和涨跌停限制；
- T+1 卖出约束；
- 现金、持仓、成交记录和按最新价格估值。

示例：

```python
from stock_auto.paper import PaperBroker
from stock_auto.data import DailyBar

broker = PaperBroker(initial_cash=500_000)
broker.submit_order("order-001", "sh600000", "BUY", 100, "2024-01-02")
fills = broker.process_bar(DailyBar(
    "sh600000", "2024-01-03", 10, 10.5, 9.9, 10.2, 10000, prev_close=10
))
print(fills, broker.account.cash, broker.account.positions)
```

订单必须在目标成交日之前提交。模拟盘不等同于券商仿真环境，不能验证真实排队、盘口深度、部分成交和交易所拒单行为。
