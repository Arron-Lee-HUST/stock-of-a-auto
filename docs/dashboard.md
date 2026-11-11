# 报表与可视化

`reporting.py` 将候选扫描输出为 `candidates.csv`、`rejected.csv` 和 JSON 摘要；回测输出为 `trades.csv`、权益曲线和回测指标。可生成独立 HTML 仪表盘，无需额外前端构建工具或在线图表依赖。

HTML 输出对标题、指标和表格内容进行转义；报表仅展示传入的数据，不会发起交易。生成目录建议放在本地 `reports/`，不要提交包含个人账户信息或供应商 Token 的报表。
