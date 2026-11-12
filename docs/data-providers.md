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

## CSV 上下文字段

`CsvPointInTimeContextProvider` 可分别读取以下文件，所有文件均以 `symbol,trade_date` 为键：

- 竞价：`auction_pct,auction_volume_ratio`
- 分时：`price,vwap,volume_ratio`
- 资金流：`main_net_inflow`
- 板块：`sector_rank,sector_limit_up_count,sector_leader_limit_up,catalyst`

日期格式必须是 `YYYY-MM-DD`，布尔值支持 `true/false`、`1/0`、`yes/no`。数据源必须明确金额单位、成交量单位和时间戳语义。

生成合成演示数据（仅用于功能验证）：

```bash
python examples/generate_demo_data.py
```

演示数据并非真实行情，不可用于策略有效性评估。


## AKShare 免费适配器

安装：`pip install -e ".[akshare]"`。适配器使用 `stock_zh_a_hist(..., period="daily", adjust="")` 下载未复权日线，使用 `stock_zh_a_spot_em` 读取普通全市场 spot 快照。历史成交量按手转换为股，成交额按人民币元保留。

`AkshareMarketDataProvider.get_spot_quotes()` 返回采集时间、来源、价格、涨跌幅、成交量和成交额。Spot 快照不是逐笔行情、盘口深度或集合竞价专用接口，不提供可直接用于交易的竞价量比和 VWAP。上游接口可用性、字段和访问频率可能变化，免费接口没有 SLA。

当前 CLI：`sync-akshare` 下载标准日线 CSV；`spot-akshare` 导出 spot 快照；`serve-akshare` 启动只读轮询服务。该服务在缺少竞价/VWAP/市场宽度时 fail closed，不产生新增买入动作。

## Tushare 免费权限边界

Tushare Pro 日线接口权限与账号积分有关；分钟、实时行情、集合竞价等接口可能要求独立授权。Token 应通过环境变量配置。不能假设免费账号可以使用所有接口。


## 东方财富优先的实时行情、竞价与盘口

新增 `EastmoneyTencentRealtimeProvider`，运行时优先级：

1. 东方财富：批量实时行情（`push2.eastmoney.com/api/qt/ulist.np/get`）；单股五档盘口（`api/qt/stock/get`）；分时/竞价数据（`api/qt/stock/trends2/get`）。
2. 腾讯财经：东方财富行情缺失、上游时间戳缺失或超出新鲜度阈值时，按股票逐只回退到 `qt.gtimg.cn`。
3. 新浪财经：腾讯不可用或数据不新鲜时，最后回退到 `hq.sinajs.cn`。

腾讯和新浪当前只作为普通报价兜底，不会伪装成东方财富竞价或五档盘口数据。盘口与竞价数据缺失时仍然 fail closed。

### 集合竞价口径

东方财富分时接口在 09:15–09:25 提供虚拟撮合/参考价格行；最终 09:25 撮合量额在源时间标签为 09:26 的记录中读取。当前实现读取该行的 f53 匹配价、f56 竞价成交量（手，转换为股）和 f57 竞价成交额（元），并将逻辑竞价时间记为 09:25、源时间戳保留为 09:26。09:15 等虚拟行成交量为零，不作为实际竞价成交量。

`auction_volume_ratio` 定义为“今日最终竞价匹配成交量 / 最近一个已归档交易日的最终竞价匹配成交量”（竞昨量比），不是日内量比，也不是今日竞价量除以昨日全天成交量。SQLite 文件 `runtime/auction-history.sqlite3` 按股票、交易日持久化最终竞价成交量。首次部署没有上一交易日竞价样本时，量比为 None；连续采集至少两个交易日后才可计算。不能用全天成交量或虚拟撮合量填补缺失基准。

### 五档盘口口径

东方财富 `stock/get` 五档字段映射：
- 买一至买五：f19/f20、f17/f18、f15/f16、f13/f14、f11/f12（价格/委托量）。
- 卖一至卖五：f39/f40、f37/f38、f35/f36、f33/f34、f31/f32（价格/委托量）。
- 当前实现保留五档逐档委托量、买卖总深度、买卖深度失衡率、最优买价/卖价以及源时间戳。未获得授权的十档/L2 字段不作假设。

### 新鲜度与交易安全

- 默认上游时间戳最大允许年龄为 120 秒；超过阈值先尝试腾讯，再尝试新浪。无法取得可验证的上游时间戳时不把本地采集时间冒充源时间。
- 实时快照与五档盘口按采集周期归档到 `runtime/market-data.jsonl`，保留 source、source timestamp 和逻辑交易时间。
- 新入场判断要求竞价涨幅、竞昨量比、分时 VWAP、五档深度/失衡率，以及报价和盘口的有效上游时间戳。任一缺失均返回 wait。
- 竞价数据与盘口仍由东方财富提供；腾讯/新浪 fallback 只补普通报价，因此它们不能单独让竞价入场条件通过。

### 使用方式

```bash
stock-auto serve-live --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --calendar-csv data/trading-calendar.csv --positions-csv data/positions.csv --poll-interval 30 --max-data-age 120 --auction-db runtime/auction-history.sqlite3 --market-data-jsonl runtime/market-data.jsonl
```

旧命令 `serve-akshare` 保留为兼容别名。AKShare 仍负责免费日线历史下载；实时监控不再使用 AKShare spot 作为竞价或盘口来源。


### 市场情绪统计

监控服务额外读取东方财富 `push2ex` 的 `getTopicZTPool` 与 `getTopicDTPool`，以涨停池/跌停池条目数形成市场涨跌停家数，并从涨停池 `lbc` 取最大连板数。接口返回 `data=null` 或请求失败时，市场情绪字段保持 None，风控层继续进入 cautious，不用 0 冒充正常市场状态。


### 市场广度与行业热度

`getTopicZDFenBu` 返回的涨跌幅分布用于归纳上涨家数、下跌家数、平盘家数和上涨/下跌比。行业热度来自东方财富行业板块 `clist/get` 排名，个股行业名由实时行情字段 f100 关联；涨停池的 `hybk` 用于统计行业涨停家数，板块领涨股代码与涨停池交叉判断龙头是否涨停。若行业名或领涨股代码无法匹配，相关字段保持 None，不猜测关联。

实时监控默认只对按评分排序的前 50 个候选股及全部持仓请求逐股竞价/五档盘口，避免对免费上游接口发起数千次并发/连续请求。可通过 `--max-candidates` 调整，逐股请求仍受 `--source-min-interval` 限频。

盘口请求使用东方财富网页端完整字段集合，而不是只请求 f11–f40 的窄字段列表；部分公开接口部署会在窄字段请求下返回空盘口字段。五档字段按东财实时集群的 f19/f20 等映射，仍需在真实交易时段抽样校验源返回值、档位完整度和委托量单位。
