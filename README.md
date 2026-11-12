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

## 命令行\n\n安装后可使用 `stock-auto`，支持 `validate-data`、`scan`、`monitor`、`backtest`、`paper-replay`、`sync-akshare`、`refresh-akshare`、`spot-akshare`、`serve-live`（兼容别名 `serve-akshare`）。示例数据生成和命令参数见 [deploy/README.md](deploy/README.md)。\n\n## 免费行情源（AKShare）

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
- `src/stock_auto/providers.py`：Tushare Pro 可选适配器和代码转换。\n- `src/stock_auto/realtime_provider.py`：东方财富优先、腾讯和新浪兜底的实时行情、竞价与五档盘口采集。\n- `src/stock_auto/auction_history.py`：竞价成交量历史归档与竞昨量比计算。
- `src/stock_auto/context.py`：竞价、分时、资金流、板块数据协议。
- `docs/data-providers.md`：供应商接入与数据质量要求。
- `src/stock_auto/backtest.py`：无未来函数的日频回测引擎。
- `docs/data-backtest.md`：历史数据格式与回测假设。
- `tests/`：单元测试。
- `docs/strategy.md`：策略细节、数据契约与边界说明。

## 项目阶段\n\n完整阶段交付与生产化边界见 [docs/roadmap.md](docs/roadmap.md)。\n\n## 重要边界

当前版本不绑定行情供应商，不含新闻爬虫、券商交易接口或自动下单。数据接入和回测假设详见 `docs/data-backtest.md`。当前回测是研究级日频框架，交易日历、个股特殊涨跌幅规则、复权处理和费用参数仍需按数据源与实际交易规则校准。


## 实时行情：东方财富优先，腾讯/新浪兜底

实时服务使用 `stock-auto serve-live`。东方财富负责实时快照、最终集合竞价成交和优先五档盘口；普通报价过期时按顺序回退腾讯财经和新浪财经，五档盘口缺失或不完整时尝试腾讯五档盘口。集合竞价成交仍只认东方财富，腾讯/新浪不会伪装成竞价数据。

竞价量比采用竞昨量比：今日 09:25 最终匹配成交量 / 最近一个已归档交易日的 09:25 最终匹配成交量。首次部署需要积累前一交易日样本；没有基准时不会伪造量比。新入场还必须通过分时 VWAP、五档深度及上游时间戳新鲜度检查。数据不完整时只观察，不产生买入动作。

完整字段映射、09:26 源时间标签处理、限频与故障降级规则见 [docs/data-providers.md](docs/data-providers.md)。


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

实时监控默认最多逐只轮询评分前 30 个候选和全部持仓，采集东方财富五档盘口、最终竞价数据、分钟资金流估算；普通报价按东财→腾讯→新浪降级。可用 `--max-candidates` 与 `--source-min-interval` 控制请求规模和限频。
