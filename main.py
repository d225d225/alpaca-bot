"""
AlpacaBot 主程式入口
用法：
  python main.py run          # 執行所有帳戶策略
  python main.py report       # 只生成報告（不交易）
  python main.py email        # 只發送 Email
  python main.py status       # 顯示帳戶狀態
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import date

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("alpacabot")


def cmd_run(args) -> None:
    """完整流程：選股 → 停損停利 → 再平衡 → 報告 → Email"""
    from src.core.account_manager import AccountManager
    from src.strategy.strategy_loader import StrategyLoader
    from src.strategy.strategy_executor import run_strategy
    from src.report.report_model import build_report
    from src.report.report_storage import save_report, load_prev_nav, load_nav_history
    from src.report.report_view import render_daily_email, render_text_summary
    from src.notification.email_sender import send_daily_report, send_trade_alert

    manager  = AccountManager()
    loader   = StrategyLoader()
    today    = date.today().isoformat()

    for acc, client in manager.iter_active():
        logger.info("▶ 處理帳戶：%s", acc.account_id)

        if acc.strategy_id not in loader:
            logger.error("帳戶 %s 的策略 %s 不存在，跳過", acc.account_id, acc.strategy_id)
            continue

        strategy = loader.get(acc.strategy_id)
        trades_collected: list[dict] = []

        def notify(trade: dict):
            trade["account_id"] = acc.account_id
            trades_collected.append(trade)
            if strategy.notify_on_trade:
                send_trade_alert(acc.email_to, trade)

        summary = run_strategy(client, acc, strategy, notify_fn=notify)

        # 生成報告
        prev_nav    = load_prev_nav(acc.account_id)
        nav_history = load_nav_history(acc.account_id)

        report = build_report(
            client=client,
            account_id=acc.account_id,
            strategy_id=acc.strategy_id,
            target_symbols=summary.get("target_symbols", []),
            trades=trades_collected,
            watchlists=acc.watchlists,
            prev_nav=prev_nav,
            initial_capital=1_000_000.0,
            nav_history=nav_history,
        )
        save_report(report)

        # 寄送 Email
        html = render_daily_email(report)
        text = render_text_summary(report)
        send_daily_report(acc.email_to, html, text, today)
        logger.info("✅ 帳戶 %s 完成", acc.account_id)


def cmd_status(args) -> None:
    """顯示所有帳戶狀態"""
    from src.core.account_manager import AccountManager
    manager = AccountManager()
    for acc, client in manager.iter_active():
        try:
            cash = client.get_cash()
            pv   = client.get_portfolio_value()
            print(f"\n帳戶：{acc.account_id} ({acc.label})")
            print(f"  策略：{acc.strategy_id}")
            print(f"  現金：${cash:,.2f}")
            print(f"  NAV ：${pv:,.2f}")
            print(f"  市場開盤：{'是' if client.is_market_open() else '否'}")
        except Exception as e:
            print(f"  [錯誤] {e}")


def cmd_report(args) -> None:
    """只生成報告（不執行交易）"""
    from src.core.account_manager import AccountManager
    from src.market.market_data import get_top_n_nasdaq
    from src.report.report_model import build_report
    from src.report.report_storage import save_report, load_prev_nav, load_nav_history

    manager = AccountManager()
    for acc, client in manager.iter_active():
        top10       = get_top_n_nasdaq(10)
        prev_nav    = load_prev_nav(acc.account_id)
        nav_history = load_nav_history(acc.account_id)
        report = build_report(client, acc.account_id, acc.strategy_id,
                              top10, [], acc.watchlists, prev_nav, 1_000_000.0, nav_history)
        path = save_report(report)
        print(f"報告已儲存：{path}")


def cmd_email(args) -> None:
    """重新寄送最新報告 Email"""
    from src.core.account_manager import AccountManager
    from src.report.report_storage import load_report, list_report_dates
    from src.report.report_view import render_daily_email, render_text_summary
    from src.notification.email_sender import send_daily_report

    manager = AccountManager()
    for acc in manager.all_active():
        dates = list_report_dates(acc.account_id)
        if not dates:
            print(f"帳戶 {acc.account_id} 無報告可寄送")
            continue
        report = load_report(acc.account_id, dates[0])
        if report:
            html = render_daily_email(report)
            text = render_text_summary(report)
            send_daily_report(acc.email_to, html, text, dates[0])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AlpacaBot")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run")
    subparsers.add_parser("report")
    subparsers.add_parser("email")
    subparsers.add_parser("status")
    args = parser.parse_args()

    commands = {
        "run":    cmd_run,
        "report": cmd_report,
        "email":  cmd_email,
        "status": cmd_status,
    }
    fn = commands.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()
