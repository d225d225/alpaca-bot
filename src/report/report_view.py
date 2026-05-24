"""
報告 View 層（從 JSON Model 渲染 HTML Email）
Model 與 View 完全分離：View 只讀取 DailyReport，不呼叫任何 API
"""
from __future__ import annotations
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.report.report_model import DailyReport

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "notification" / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_daily_email(report: DailyReport) -> str:
    """將 DailyReport 渲染為 HTML 格式的 Email 內容"""
    tmpl = _jinja_env.get_template("daily_report.html")
    return tmpl.render(r=report)


def render_text_summary(report: DailyReport) -> str:
    """純文字摘要（用於 log / 簡訊）"""
    lines = [
        f"【AlpacaBot 日報 {report.report_date}】",
        f"帳戶：{report.account_id}  策略：{report.strategy_id}",
        f"NAV：${report.nav:,.2f}  今日損益：${report.daily_pl:+,.2f} ({report.nav_change_pct:+.2f}%)",
        f"累積損益：{report.total_pl_pct:+.2f}%  最大回撤：{report.max_drawdown_pct:.2f}%",
        f"現金：${report.cash:,.2f}  持倉市值：${report.long_market_value:,.2f}",
        "",
        "【Top 10 持倉】",
    ]
    for sym in report.top10_symbols:
        rets = report.top10_returns.get(sym, {})
        pe   = report.top10_pe.get(sym)
        price = report.top10_prices.get(sym, 0)
        pe_str = f"PE:{pe:.1f}" if pe else "PE:N/A"
        lines.append(
            f"  {sym:<6} ${price:>8.2f}  "
            f"1D:{rets.get('1d',0):+.2f}%  "
            f"1W:{rets.get('1w',0):+.2f}%  "
            f"1M:{rets.get('1m',0):+.2f}%  {pe_str}"
        )
    lines += [
        "",
        f"NASDAQ 今日：{report.nasdaq_1d_return:+.2f}%  S&P500：{report.sp500_1d_return:+.2f}%",
        "",
        report.disclaimer,
    ]
    return "\n".join(lines)
