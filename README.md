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

需要 Python 3.11 或更高版本，无第三方运行时依赖。

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS / Linux
source .venv/bin/activate

PYTHONPATH=src python -m unittest discover -s tests -v
```

## 命令行\n\n安装后可使用 `stock-auto`，支持 `validate-data`、`scan`、`monitor`、`backtest` 和 `paper-replay`。示例数据生成和命令参数见 [deploy/README.md](deploy/README.md)。\n\n## 最小调用示例

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
- `src/stock_auto/context.py`：竞价、分时、资金流、板块数据协议。
- `docs/data-providers.md`：供应商接入与数据质量要求。
- `src/stock_auto/backtest.py`：无未来函数的日频回测引擎。
- `docs/data-backtest.md`：历史数据格式与回测假设。
- `tests/`：单元测试。
- `docs/strategy.md`：策略细节、数据契约与边界说明。

## 项目阶段\n\n完整阶段交付与生产化边界见 [docs/roadmap.md](docs/roadmap.md)。\n\n## 重要边界

当前版本不绑定行情供应商，不含新闻爬虫、券商交易接口或自动下单。数据接入和回测假设详见 `docs/data-backtest.md`。当前回测是研究级日频框架，交易日历、个股特殊涨跌幅规则、复权处理和费用参数仍需按数据源与实际交易规则校准。
