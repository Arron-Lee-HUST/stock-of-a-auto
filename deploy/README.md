# 本地部署

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

可选 Tushare SDK：`pip install -e '.[tushare]'`，并通过环境变量设置 `TUSHARE_TOKEN`。

## 命令

- `stock-auto validate-data --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2024-12-31`
- `stock-auto scan --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2024-12-31 --trade-date 2024-12-31 --flow-csv data/flow.csv --sector-csv data/sector.csv`
- `stock-auto backtest --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2024-12-31 --flow-csv data/flow.csv --sector-csv data/sector.csv`
- `stock-auto paper-replay --daily-csv data/daily.csv --orders-csv data/paper-orders.csv`

Universe CSV 至少需要 `symbol` 列。日线 CSV 格式见 `docs/data-backtest.md`；上下文 CSV 字段见 `docs/data-providers.md`。模拟盘订单 CSV 字段：`order_id,symbol,side,quantity,submitted_date,trade_date`。

## Docker

```bash
docker build -t stock-of-a-auto .
docker run --rm -v "$PWD/data:/app/data" -v "$PWD/reports:/app/reports" stock-of-a-auto validate-data --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2024-12-31
```

## 定时任务

把扫描任务调度在交易日 15:10（收盘后），竞价监控服务应在 09:20–09:25 由独立实时数据进程调用 `MarketMonitor`。系统时区需显式设为 Asia/Shanghai，并使用交易日历过滤节假日。不要用普通 cron 的工作日表达式替代交易日历。

本仓库不提供行情 Token、实时数据服务、云主机或真实券商连接。生产部署前需配置数据授权、密钥管理、日志轮转、告警和人工审批。
