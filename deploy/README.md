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


## systemd 守护进程

仓库提供 `deploy/stock-auto.service.example`。部署前创建 stockauto 用户/组，准备数据目录、`/var/lib/stock-auto` 和 `/var/log/stock-auto`，并修改 unit 中的安装路径、开始日期和数据文件路径。服务支持 SIGTERM 优雅退出、自动重启和日志轮转（10 MB × 5 个文件）。使用前先以 stockauto 用户执行 `stock-auto --help` 与一次 `serve-akshare` 配置检查；不要在没有有效交易日历和行情缓存时启动。


可选 Webhook 告警：设置环境变量 `STOCK_AUTO_ALERT_WEBHOOK` 为接收 JSON POST 的 HTTPS 地址。服务会先将事件写入 SQLite outbox，再发送；失败会记录错误并在后续轮询重试，成功事件不会因进程重启重复发送。不要把含密钥的 webhook URL 提交到仓库或日志。此接口是通用 JSON webhook，不内置企业微信/钉钉的签名算法或消息模板，使用前需确认目标端接受本项目 JSON 结构。


## 东方财富优先的实时监控

安装核心包后直接运行（实时接口使用 Python 标准库，无需 AKShare SDK）：

```bash
stock-auto serve-live \
  --daily-csv data/daily.csv \
  --universe-csv data/universe.csv \
  --start-date 2024-01-01 \
  --calendar-csv data/trading-calendar.csv \
  --positions-csv data/positions.csv \
  --poll-interval 30 \
  --max-data-age 120 \
  --auction-db runtime/auction-history.sqlite3 \
  --market-data-jsonl runtime/market-data.jsonl
```

`serve-akshare` 仍作为兼容别名。实时源优先级是东方财富 → 腾讯 → 新浪；腾讯/新浪只兜底普通报价。竞价和五档盘口只认东方财富源，源时间戳超时或缺失时禁止新入场。09:25 最终集合竞价在东财分时数据的 09:26 源时间标签中落地，服务窗口延长至 09:27 用于接收该记录。

竞昨量比按今日最终竞价匹配成交量除以最近一个已归档交易日竞价匹配成交量计算。第一次部署没有历史基准时该字段为空；必须连续运行至少两个交易日。运行过程中生成：
- `runtime/auction-history.sqlite3`：每只股票每天最终竞价成交量；
- `runtime/market-data.jsonl`：行情快照、五档盘口、竞价数据、数据源和时间戳；
- `runtime/health.json`：监控健康状态；
- `runtime/alerts.sqlite3`：告警 outbox。

免费公开接口无 SLA，建议先用小规模股票池连续跑至少 5 个交易日，统计源切换次数、数据缺失率、请求耗时和时间戳延迟。该服务保持只读，不会下单。
