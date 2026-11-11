from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from html import escape
from pathlib import Path
from typing import Any


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def write_json(path: str | Path, value: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_plain(value), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return target


def write_scan_reports(result, output_dir: str | Path) -> list[Path]:
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    paths = [write_json(folder / "scan-summary.json", result)]
    for name, items in (("candidates.csv", result.candidates), ("rejected.csv", result.rejected)):
        target = folder / name
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["symbol", "trade_date", "score", "trend_score", "capital_score",
                             "sentiment_score", "eligible", "reasons", "warnings", "missing_fields"])
            for item in items:
                s = item.signal
                writer.writerow([s.symbol, item.snapshot.trade_date, s.score, s.trend_score,
                                 s.capital_score, s.sentiment_score, s.eligible,
                                 " | ".join(s.reasons), " | ".join(s.warnings),
                                 " | ".join(s.missing_fields)])
        paths.append(target)
    return paths


def write_backtest_reports(result, output_dir: str | Path) -> list[Path]:
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    summary = {
        "initial_cash": result.initial_cash, "final_equity": result.final_equity,
        "total_return_pct": result.total_return_pct, "max_drawdown_pct": result.max_drawdown_pct,
        "win_rate_pct": result.win_rate_pct, "profit_factor": result.profit_factor,
        "trade_count": len(result.trades), "rejected_order_count": len(result.rejected_orders),
        "rejected_orders": result.rejected_orders,
    }
    paths = [write_json(folder / "backtest-summary.json", summary)]
    target = folder / "trades.csv"
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["symbol", "entry_date", "exit_date", "quantity", "entry_price",
                         "exit_price", "pnl", "return_pct"])
        for trade in result.trades:
            writer.writerow([trade.symbol, trade.entry_date, trade.exit_date, trade.quantity,
                             trade.entry_price, trade.exit_price, trade.pnl, trade.return_pct])
    paths.append(target)
    paths.append(write_json(folder / "equity-curve.json", result.equity_curve))
    return paths


def write_dashboard(path: str | Path, title: str, metrics: dict[str, Any],
                    rows: list[dict[str, Any]] | None = None,
                    equity_curve: list[tuple[str, float]] | None = None) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    cards = "".join(
        f'<article class="metric"><span>{escape(str(key))}</span><strong>{escape(str(value))}</strong></article>'
        for key, value in metrics.items()
    )
    headers = list(rows[0]) if rows else []
    table_head = "".join(f"<th>{escape(str(k))}</th>" for k in headers)
    table_rows = "".join("<tr>" + "".join(
        f"<td>{escape(str(row.get(k, '')))}</td>" for k in headers
    ) + "</tr>" for row in (rows or []))
    points = json.dumps(equity_curve or [], ensure_ascii=False).replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
:root{{--bg:#f4f6fa;--panel:#fff;--ink:#182230;--muted:#65748b;--line:#e3e8ef;--accent:#2563eb}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Microsoft YaHei",sans-serif}}
main{{max-width:1200px;margin:32px auto;padding:0 20px}}h1{{font-size:25px;margin:0 0 6px}}.muted{{color:var(--muted)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:22px 0}}
.metric,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}}
.metric span{{display:block;color:var(--muted);font-size:12px}}.metric strong{{display:block;font-size:22px;margin-top:6px;overflow-wrap:anywhere}}
.panel{{margin:16px 0;overflow:auto}}table{{border-collapse:collapse;width:100%;white-space:nowrap}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--muted);font-weight:600;background:#fafbfc}}
canvas{{width:100%;height:260px}}footer{{color:var(--muted);padding:18px 0}}@media(max-width:600px){{main{{margin:18px auto;padding:0 12px}}}}
</style></head><body><main><h1>{escape(title)}</h1><div class="muted">研究与模拟数据报表，不构成投资建议</div>
<section class="cards">{cards}</section><section class="panel"><h2>权益曲线</h2><canvas id="curve" width="1100" height="260"></canvas></section>
<section class="panel"><h2>明细</h2><table><thead><tr>{table_head}</tr></thead><tbody>{table_rows}</tbody></table></section>
<footer>请核对数据源、复权方式、交易规则、手续费和滑点假设。严禁将历史回测表现视为未来收益保证。</footer></main>
<script>
const points={points};const canvas=document.getElementById('curve'),ctx=canvas.getContext('2d');
if(points.length){{const vals=points.map(p=>Number(p[1])),lo=Math.min(...vals),hi=Math.max(...vals),span=hi-lo||1;
ctx.strokeStyle='#2563eb';ctx.lineWidth=2;ctx.beginPath();vals.forEach((v,i)=>{{const x=20+i*(canvas.width-40)/Math.max(1,vals.length-1),y=canvas.height-20-(v-lo)/span*(canvas.height-40);i?ctx.lineTo(x,y):ctx.moveTo(x,y)}});ctx.stroke();}}
else{{ctx.fillStyle='#65748b';ctx.fillText('暂无权益曲线数据',20,35)}}
</script></body></html>"""
    target.write_text(html, encoding="utf-8")
    return target
