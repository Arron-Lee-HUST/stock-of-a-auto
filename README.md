# A股短线自动化交易系统

围绕「三驱一动」模型构建可配置、可回测、可解释的 A 股短线选股与交易决策系统。

> 本项目用于研究、策略验证与风险分析，不构成投资建议。任何策略均不保证收益；实盘前必须进行数据校验、回测、模拟盘验证，并遵守交易所规则。

## 当前能力

- **趋势动能**：MA5/MA10/MA20 站位、涨幅区间、近期活跃度、前高/平台突破。
- **资金博弈**：近 5 日均量放大、量价关系、主力资金净流向。
- **市场情绪**：板块热度、涨停梯队、龙头状态、消息催化。
- **动态决策**：竞价涨幅/量比过滤、分时 VWAP 确认、止盈止损与移动止盈。
- **风险管理**：市场退潮识别、空仓/谨慎模式、单票仓位上限和分仓数量计算。
- **历史数据与回测**：标准日线数据协议、CSV/Tushare 适配器、下一交易日开盘成交、T+1、涨跌停/停牌约束及费用/滑点模型。
- **多源数据契约**：竞价、分时、资金流和板块情绪的统一 point-in-time 数据结构。
- **全市场候选扫描**：从日线构建技术特征，接入 point-in-time 上下文后按三驱评分排序。
- **策略联动回测**：将候选扫描、持仓退出规则和日频成交模拟串联。
- **交易监控**：竞价窗口 watch 信号、盘中入场与持仓退出监控。
- **组合风控**：日内亏损、账户回撤、连续亏损、总敞口和板块集中度熔断。

策略参数集中在 `StrategyConfig`，行情输入统一使用 `MarketSnapshot`。所有百分比字段均使用百分数数值（例如 3.2 表示 3.2%）；未知字段使用 `None`，不允许用 0 冒充缺失值。

## 从零启动项目（推荐流程）

本节以 **Windows PowerShell** 为例，同时提供 macOS/Linux 命令。首次启动建议先跑通历史数据下载、数据校验和单次扫描，确认数据正常后再启动实时只读监控。

### 1. 获取代码并创建 Python 环境

要求：Python 3.11+、可访问互联网。项目核心依赖较少；本流程安装 AKShare，用于免费获取日线数据和交易日历。

```bash
git clone https://github.com/Arron-Lee-HUST/stock-of-a-auto.git
cd stock-of-a-auto
python -m venv .venv
```

激活虚拟环境：

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

安装项目和 AKShare 可选依赖：

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[akshare]"
```

验证命令行入口和测试：

```bash
stock-auto --help
python -m unittest discover -s tests -v
```

如果当前终端提示找不到 `stock-auto`，先确认虚拟环境已激活；也可以重新执行 `python -m pip install -e ".[akshare]"`。

### 2. 准备股票池

项目不会默认替你选择股票。创建 `data/universe.csv`，至少包含 `symbol` 列，代码使用带市场前缀的格式：

```csv
symbol
sh600000
sz000001
sz300750
sh688981
```

示例仅用于说明格式，请按自己的研究范围替换。股票池越大，首次日线下载耗时越长；实时监控也会对候选股和持仓逐只请求数据源，建议先用少量股票验证。

### 3. 下载历史日线数据

首次运行需要建立本地日线缓存。以下示例下载 2024-01-01 至指定日期的数据；将结束日期改为最近一个已完成的交易日：

```bash
stock-auto sync-akshare --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2026-11-11 --output data/daily.csv
```

后续每天收盘后增量更新：

```bash
stock-auto refresh-akshare --universe-csv data/universe.csv --daily-csv data/daily.csv --lookback-days 10
```

数据文件保存在本地 `data/` 目录（该目录已加入 .gitignore，不会提交到 Git）。

### 4. 同步并核对交易日历

```bash
stock-auto sync-calendar-akshare --output data/trading-calendar.csv
```

生成后检查 `data/trading-calendar.csv` 是否包含你准备启动监控的**当天交易日**。可用 PowerShell 检查：

```powershell
Import-Csv data/trading-calendar.csv | Select-Object -Last 10
```

macOS/Linux 可执行：

```bash
tail data/trading-calendar.csv
```

注意：免费日历接口可能只返回已公布的历史交易日，未必提前包含未来交易日。若文件不包含运行当天，实时服务会按安全策略停止；不要为了启动而把周末或节假日随意添加为交易日，应先核对权威交易所日历。

### 5. 先做数据校验和候选扫描

数据校验：

```bash
stock-auto validate-data --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2026-11-11 --output reports/data-quality.json
```

收盘后扫描示例（`--trade-date` 必须是日线缓存中存在的交易日）：

```bash
stock-auto scan --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2026-11-11 --trade-date 2026-11-11 --output-dir reports
```

扫描和回测的输出默认写入 `reports/`。如果你只想先验证项目能运行，到这一步即可，不需要启动持续监控。

### 6. 启动实时只读监控

确认以下文件均已准备好后再启动：

- `data/universe.csv`：股票池。
- `data/daily.csv`：截至最近一个已完成交易日的历史日线。
- `data/trading-calendar.csv`：包含监控当天的有效交易日历。
- 可选：`data/positions.csv`：当前持仓；没有持仓文件时，启动命令中不要传 `--positions-csv`。

启动命令：

```bash
stock-auto serve-live --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --calendar-csv data/trading-calendar.csv --poll-interval 30 --max-data-age 120 --max-candidates 25 --auction-db runtime/auction-history.sqlite3 --market-data-jsonl runtime/market-data.jsonl --health runtime/health.json --log-file runtime/service.log
```

如果有持仓文件，在命令末尾增加：

```bash
--positions-csv data/positions.csv
```

服务会在适用的交易时段持续轮询，默认每 30 秒采集一次；实时普通报价优先使用东方财富，按规则回退腾讯/新浪。竞价匹配数据仍以东方财富为准。按 `Ctrl+C` 可停止进程。服务不会连接券商，也不会自动下单。

运行时主要文件：

| 文件 | 用途 |
|---|---|
| `runtime/market-data.jsonl` | 行情快照、数据源、源时间戳和质量诊断 |
| `runtime/auction-history.sqlite3` | 竞价样本和最终匹配量历史 |
| `runtime/health.json` | 服务健康状态 |
| `runtime/alerts.sqlite3` | 告警去重与持久化记录 |
| `runtime/service.log` | 服务运行日志 |

首次启动时竞昨量比没有前一交易日基准是正常情况。系统需要连续观察同一只股票至少两个交易日才能计算；缺少竞价量比、完整盘口或有效源时间戳时会阻止新增买入信号。实时监控建议先使用小股票池连续运行至少 5 个交易日，检查日志和数据质量后再扩大范围。

### 7. 常见问题

- **`stock-auto` 命令不存在**：确认已激活 `.venv`，然后重新执行 `python -m pip install -e ".[akshare]"`。
- **提示缺少 AKShare**：执行 `python -m pip install -e ".[akshare]"`。
- **提示没有历史日线**：检查 `data/universe.csv` 股票代码格式、网络连接和 `sync-akshare` 命令输出。
- **提示交易日历不包含当天**：重新同步并核对交易所日历；不能用非交易日或未经确认的日期绕过检查。
- **没有买入信号**：这可能是安全过滤的预期结果。竞价历史基准尚未积累、数据过期、盘口不完整或上游时间戳缺失都会导致只观察、不入场。
- **免费行情接口不稳定**：公开接口没有 SLA，可能限流或调整字段。先降低股票池规模、保持默认轮询间隔，并检查 `runtime/service.log` 和 `runtime/market-data.jsonl`。

## 快速开始

需要 Python 3.11 或更高版本。核心研究模块无强制第三方运行时依赖；免费 AKShare 数据源需额外安装 `pip install -e ".[akshare]"`。

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS / Linux
source .venv/bin/activate

PYTHONPATH=src python -m unittest discover -s tests -v
```

## 命令行

安装后可使用 `stock-auto`，支持 `validate-data`、`scan`、`monitor`、`backtest`、`paper-replay`、`sync-akshare`、`refresh-akshare`、`spot-akshare`、`serve-live`（兼容别名 `serve-akshare`）。示例数据生成和命令参数见 [deploy/README.md](deploy/README.md)。

## 免费行情源（AKShare）

```bash
pip install -e ".[akshare]"
stock-auto sync-akshare --universe-csv data/universe.csv --start-date 2024-01-01 --end-date 2024-12-31 --output data/daily.csv
stock-auto spot-akshare --universe-csv data/universe.csv --output runtime/spot.csv
```

持续只读监控需提供真实交易日历 CSV（`trade_date` 列）和本地历史日线缓存：

```bash
stock-auto serve-akshare --daily-csv data/daily.csv --universe-csv data/universe.csv --start-date 2024-01-01 --calendar-csv data/trading-calendar.csv --positions-csv data/positions.csv
```

AKShare spot 快照不包含可靠的逐笔、盘口、集合竞价量比和 VWAP；该监控服务会阻止新增买入信号，仅输出观察/风险提示及基于快照的持仓风险事件。不要把它当成自动交易系统。

## 最小调用示例

```python
from stock_auto import MarketSnapshot, StrategyConfig, evaluate_candidate

snapshot = MarketSnapshot(
    symbol="sh600000",
    close=10.80,
    prev_close=10.30,
    pct_change=4.85,
    ma5=10.50,
    ma10=10.20,
    ma20=9.90,
    volume=1800,
    avg_volume_5=1000,
    main_net_inflow=1200000,
    recent_limit_up=True,
    prior_high=10.60,
    sector_rank=3,
    sector_limit_up_count=4,
    sector_leader_limit_up=True,
    catalyst=True,
)

signal = evaluate_candidate(snapshot, StrategyConfig())
print(signal.eligible, signal.score, signal.reasons, signal.warnings)
```

## 目录结构

- `src/stock_auto/models.py`：行情、信号、持仓和决策数据结构。
- `src/stock_auto/config.py`：可配置策略参数。
- `src/stock_auto/scoring.py`：三驱评分及候选硬过滤。
- `src/stock_auto/decision.py`：竞价/盘中入场和退出判断。
- `src/stock_auto/risk.py`：市场风险等级和仓位计算。
- `src/stock_auto/pipeline.py`：单标的收盘后候选筛选入口。
- `src/stock_auto/scanner.py`：全市场候选扫描与特征构建。
- `src/stock_auto/strategy_backtest.py`：三驱选股与回测引擎的联动入口。
- `src/stock_auto/monitor.py`：竞价和盘中信号监控。
- `src/stock_auto/portfolio_risk.py`：组合级风控与熔断。
- `docs/monitoring.md`、`docs/risk-controls.md`：监控和风控说明。
- `src/stock_auto/data.py`：标准日线模型、行情数据协议和 CSV 适配器。
- `src/stock_auto/providers.py`：Tushare Pro 可选适配器和代码转换。
- `src/stock_auto/realtime_provider.py`：东方财富优先、腾讯和新浪兜底的实时行情、竞价与五档盘口采集。
- `src/stock_auto/auction_history.py`：竞价成交量历史归档与竞昨量比计算。
- `src/stock_auto/context.py`：竞价、分时、资金流、板块数据协议。
- `docs/data-providers.md`：供应商接入与数据质量要求。
- `src/stock_auto/backtest.py`：无未来函数的日频回测引擎。
- `docs/data-backtest.md`：历史数据格式与回测假设。
- `tests/`：单元测试。
- `docs/strategy.md`：策略细节、数据契约与边界说明。

## 项目阶段

完整阶段交付与生产化边界见 [docs/roadmap.md](docs/roadmap.md)。

## 重要边界

当前版本已接入东方财富实时行情、腾讯报价/盘口兜底和新浪报价备用，并保留 AKShare/Tushare 日线适配器；不含新闻爬虫、券商交易接口或自动下单。数据接入和回测假设详见 `docs/data-backtest.md`。当前回测是研究级日频框架，交易日历、个股特殊涨跌幅规则、复权处理和费用参数仍需按数据源与实际交易规则校准。


## 实时行情：东方财富优先，腾讯/新浪兜底

实时服务使用 `stock-auto serve-live`。东方财富负责实时快照、最终集合竞价成交和优先五档盘口；普通报价过期时按顺序回退腾讯财经和新浪财经，五档盘口缺失或不完整时尝试腾讯五档盘口。集合竞价成交仍只认东方财富，腾讯/新浪不会伪装成竞价数据。

09:15–09:25 会保存东方财富最新竞价参考价；最终成交价和量额在 09:26 源时间标签的记录中确认。竞价量比采用竞昨量比：今日 09:25 最终匹配成交量 / 最近一个已归档交易日的 09:25 最终匹配成交量。首次部署需要积累前一交易日样本；没有基准时不会伪造量比。新入场还必须通过分时 VWAP、五档深度及上游时间戳新鲜度检查。数据不完整时只观察，不产生买入动作。

未匹配委托量/未匹配金额和完整逐秒竞价委托变化尚未接入。完整字段映射、09:26 源时间标签处理、限频与故障降级规则见 [docs/data-providers.md](docs/data-providers.md)。


增量更新本地日线缓存（默认回看最近日期并留 10 个自然日修正窗口，按股票和交易日 upsert，不重复追加）：

```bash
stock-auto refresh-akshare --universe-csv data/universe.csv --daily-csv data/daily.csv --lookback-days 10
```

建议在每个交易日收盘后运行；它只更新本地历史日线，不会自动更新交易日历。


更新交易日历（免费 AKShare/Sina）：

```bash
stock-auto sync-calendar-akshare --output data/trading-calendar.csv
```

此接口提供已公布的历史交易日列表；上线前仍须确认文件包含当天，未包含时监控会安全停止。

实时监控默认最多逐只轮询评分前 25 个候选和全部持仓，采集东方财富五档盘口、最终竞价数据、分钟资金流估算；普通报价按东财→腾讯→新浪降级。可用 `--max-candidates` 与 `--source-min-interval` 控制请求规模和限频。
