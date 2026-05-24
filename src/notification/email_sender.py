"""Email 通知：每日日報（06:00）& 交易即時通知"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.core.config import config

logger = logging.getLogger(__name__)


def _send_smtp(to: str, subject: str, html: str, text: str = "") -> bool:
    """透過 SMTP 發送 Email（Gmail App Password）"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = config.EMAIL_FROM
    msg["To"]      = to
    if text:
        msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Gmail App Password 去除空格（Google 顯示格式含空格，實際不需要）
    smtp_pass = (config.SMTP_PASS or "").replace(" ", "")

    # 方法一：STARTTLS（port 587）
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()          # STARTTLS 後需再 ehlo
            server.login(config.SMTP_USER, smtp_pass)
            server.sendmail(config.EMAIL_FROM, to, msg.as_string())
        logger.info("✉️  Email 寄送成功（STARTTLS）→ %s", to)
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.warning("STARTTLS 認證失敗，嘗試 SSL（port 465）：%s", e)
    except Exception as e:
        logger.warning("STARTTLS 失敗，嘗試 SSL（port 465）：%s", e)

    # 方法二：SSL（port 465）fallback
    try:
        with smtplib.SMTP_SSL(config.SMTP_HOST, 465, timeout=15) as server:
            server.ehlo()
            server.login(config.SMTP_USER, smtp_pass)
            server.sendmail(config.EMAIL_FROM, to, msg.as_string())
        logger.info("✉️  Email 寄送成功（SSL）→ %s", to)
        return True
    except Exception as e:
        logger.error("Email 寄送失敗：%s", e)
        return False


def _send_sendgrid(to: str, subject: str, html: str, text: str = "") -> bool:
    """透過 SendGrid API 發送"""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        sg  = sendgrid.SendGridAPIClient(api_key=config.SENDGRID_API_KEY)
        msg = Mail(
            from_email=config.EMAIL_FROM,
            to_emails=to,
            subject=subject,
            html_content=html,
            plain_text_content=text or "",
        )
        resp = sg.send(msg)
        if resp.status_code < 300:
            logger.info("✉️  SendGrid 寄送成功 [%d] → %s", resp.status_code, to)
            return True
        logger.error("SendGrid 回傳 %d", resp.status_code)
        return False
    except Exception as e:
        logger.error("SendGrid 失敗：%s", e)
        return False


def send_email(to: str, subject: str, html: str, text: str = "") -> bool:
    """
    自動選擇發送方式：
    - 若 SENDGRID_API_KEY 已設定 → 使用 SendGrid
    - 否則使用 SMTP
    """
    if config.SENDGRID_API_KEY:
        return _send_sendgrid(to, subject, html, text)
    return _send_smtp(to, subject, html, text)


def send_daily_report(to: str, report_html: str, report_text: str, report_date: str) -> bool:
    """每日日報通知"""
    subject = f"📊 AlpacaBot 日報 {report_date}"
    return send_email(to, subject, report_html, report_text)


def send_trade_alert(to: str, trade: dict) -> bool:
    """交易即時通知"""
    action = trade.get("action", "TRADE")
    symbol = trade.get("symbol", "")
    qty    = trade.get("qty", 0)
    subject = f"{'🟢 買入' if action=='BUY' else '🔴 賣出'} {symbol} x{qty}"
    html = f"""
    <div style="font-family:Arial;padding:20px;">
      <h2>{subject}</h2>
      <table>
        <tr><td><b>帳戶</b></td><td>{trade.get('account_id','')}</td></tr>
        <tr><td><b>動作</b></td><td>{action}</td></tr>
        <tr><td><b>股票</b></td><td>{symbol}</td></tr>
        <tr><td><b>股數</b></td><td>{qty}</td></tr>
        <tr><td><b>訂單狀態</b></td><td>{trade.get('status','')}</td></tr>
        <tr><td><b>時間</b></td><td>{trade.get('timestamp','')}</td></tr>
        <tr><td><b>原因</b></td><td>{trade.get('reason','再平衡')}</td></tr>
      </table>
      <p style="color:#888;font-size:12px;">此為自動通知，不構成投資建議。</p>
    </div>
    """
    return send_email(to, subject, html)
