# 交易监控运行服务

本模块把既有的 `MarketMonitor` 纯决策逻辑包装为一个可长期运行的调度服务，负责交易时段门控、轮询节奏、失败退避、事件去重、JSONL 告警落盘和健康状态文件。

## 能力边界

- 时区固定为 `Asia/Shanghai`，监控窗口为 09:20–09:25、09:30–11:30、13:00–15:00。
- `TradingCalendar` 必须从交易所/合规数据供应商提供的交易日 CSV 加载。未列出的日期一律按非交易日处理；不会用“周一到周五”推断交易日。
- `MonitorService` 通过注入的 `monitor_callback(trade_date, checked_at)` 调用数据采集和 `MarketMonitor.evaluate`。数据采集适配器必须提供带交易日期/时间戳的 point-in-time 快照。
- 相同事件在当前进程生命周期内去重；告警默认写入 JSONL 文件。生产短信、邮件、企业微信或钉钉通知需由部署方实现 `AlertSink`，并管理对应凭证。
- 服务写入原子更新的健康文件，异常时记录错误并指数退避；不会因单轮行情或网络错误直接退出。
- 该服务不包含行情供应商实时 API、真实券商接口或自动下单。没有接入实际供应商之前，不能视为实时交易服务。

## 日历格式

```csv
trade_date
2026-11-11
2026-11-12
2026-11-13
```

日历必须覆盖部署运行周期，并由外部任务定期更新。日历缺失或为空会拒绝启动，避免节假日误运行。

## 接入方式

```python
from stock_auto.service import MonitorService, TradingCalendar, JsonlAlertSink

calendar = TradingCalendar.from_csv("data/trading-calendar.csv")

def monitor_callback(trade_date: str, checked_at: str):
    # 1. 从已授权的数据供应商获取当日竞价/分时数据及市场宽度
    # 2. 校验每条数据的 trade_date、时间戳、缺失字段和延迟
    # 3. 用历史数据构建候选信号，调用 MarketMonitor.evaluate
    # 4. 返回 MonitorReport
    raise NotImplementedError("connect an authorized point-in-time market data provider")

service = MonitorService(
    calendar=calendar,
    monitor_callback=monitor_callback,
    alert_sink=JsonlAlertSink("runtime/alerts.jsonl"),
    health_path="runtime/health.json",
    interval_seconds=5,
)
service.run_forever()
```

生产接入时，callback 必须具备连接超时、请求限频、断线重连、数据新鲜度校验、供应商熔断和日志脱敏。不要在代码中硬编码 Token 或 webhook URL。

## 部署检查

1. 使用可信交易日历并确认覆盖未来交易日。
2. 设置系统时区或显式使用服务内置的上海时区。
3. 配置运行目录持久化、日志轮转、进程守护和健康文件探针。
4. 监控行情延迟、轮询失败率、告警发送失败率和服务心跳。
5. 先以只读行情和本地模拟盘运行；真实交易需要独立授权的券商适配层、人工审批、限额和紧急停止开关。
