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
- `stock-auto monitor --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2024-12-31 --signal-date 2024-12-30 --trade-date 2024-12-31 --checked-at 09:23:00 --auction-csv data/auction.csv --intraday-csv data/intraday.csv --flow-csv data/flow.csv --sector-csv data/sector.csv --market-stats-json data/market-stats.json`\n- `stock-auto backtest --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2024-12-31 --flow-csv data/flow.csv --sector-csv data/sector.csv`
- `stock-auto paper-replay --daily-csv data/daily.csv --orders-csv data/paper-orders.csv`

Monitor 命令使用上一交易日 `--signal-date` 生成候选信号，使用当日 `--trade-date` 读取竞价/分时数据；市场宽度 JSON 需包含 `market_limit_up_count`、`market_limit_down_count`、`market_max_streak`。持仓 CSV 可选，字段为 `symbol,entry_price,quantity,entry_date,highest_price,cost_basis`。\n\nUniverse CSV 至少需要 `symbol` 列。日线 CSV 格式见 `docs/data-backtest.md`；上下文 CSV 字段见 `docs/data-providers.md`。模拟盘订单 CSV 字段：`order_id,symbol,side,quantity,submitted_date,trade_date`。

## Docker

```bash
docker build -t stock-of-a-auto .
docker run --rm -v "$PWD/data:/app/data" -v "$PWD/reports:/app/reports" stock-of-a-auto validate-data --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2024-12-31
```

## 定时任务

把扫描任务调度在交易日 15:10（收盘后），竞价监控服务应在 09:20–09:25 由独立实时数据进程调用 `MarketMonitor`。系统时区需显式设为 Asia/Shanghai，并使用交易日历过滤节假日。不要用普通 cron 的工作日表达式替代交易日历。

本仓库不提供行情 Token、实时数据服务、云主机或真实券商连接。生产部署前需配置数据授权、密钥管理、日志轮转、告警和人工审批。


## AKShare 免费数据源

安装：`pip install -e ".[akshare]"`。

日线缓存：`stock-auto sync-akshare --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2026-12-31 --output data/daily.csv`。

Spot 快照：`stock-auto spot-akshare --universe-csv data/universe.csv --output runtime/spot.csv`。

持续只读监控：`stock-auto serve-akshare --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --calendar-csv data/trading-calendar.csv --positions-csv data/positions.csv --poll-interval 30`。

交易日历必须来自可信交易所/供应商数据并覆盖运行日期。服务使用 Asia/Shanghai 时区，按 09:20–09:25、09:30–11:30、13:00–15:00 轮询。告警通过 SQLite 持久化去重，health.json 记录运行状态。

重要限制：AKShare spot 不是逐笔、盘口深度或专用集合竞价接口。服务不会推断竞价量比、VWAP 或市场宽度；缺少这些数据时强制谨慎模式并阻止新增买入。只读服务不会调用券商或提交订单。

Docker 可选安装 AKShare：`docker build --build-arg INSTALL_AKSHARE=1 -t stock-of-a-auto:akshare .`
