"""Phase 6-7 測試：Email 通知機制（10 cases）"""
import pytest
from unittest.mock import patch, MagicMock


# ── TC-31: SMTP Email 發送 ───────────────────────────────────────
class TestEmailSender:
    @patch("src.notification.email_sender.smtplib.SMTP")
    @patch("src.notification.email_sender.config")
    def test_smtp_sends_successfully(self, mock_cfg, mock_smtp):
        mock_cfg.SENDGRID_API_KEY = ""
        mock_cfg.EMAIL_FROM = "from@test.com"
        mock_cfg.SMTP_HOST = "smtp.gmail.com"
        mock_cfg.SMTP_PORT = 587
        mock_cfg.SMTP_USER = "user"
        mock_cfg.SMTP_PASS = "pass"
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = lambda s: mock_server
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        from src.notification.email_sender import _send_smtp
        result = _send_smtp("to@test.com", "Subject", "<h1>Test</h1>")
        assert result is True

    @patch("src.notification.email_sender.smtplib.SMTP")
    @patch("src.notification.email_sender.config")
    def test_smtp_failure_returns_false(self, mock_cfg, mock_smtp):
        mock_cfg.SENDGRID_API_KEY = ""
        mock_cfg.EMAIL_FROM = "from@test.com"
        mock_cfg.SMTP_HOST = "smtp.gmail.com"
        mock_cfg.SMTP_PORT = 587
        mock_cfg.SMTP_USER = "user"
        mock_cfg.SMTP_PASS = "pass"
        mock_smtp.side_effect = ConnectionRefusedError("Cannot connect")
        from src.notification.email_sender import _send_smtp
        result = _send_smtp("to@test.com", "Subject", "<h1>Test</h1>")
        assert result is False

    @patch("src.notification.email_sender.send_email")
    def test_daily_report_calls_send_email(self, mock_send):
        mock_send.return_value = True
        from src.notification.email_sender import send_daily_report
        result = send_daily_report("to@test.com", "<h1>Report</h1>", "Text", "2026-05-24")
        assert mock_send.called

    @patch("src.notification.email_sender.send_email")
    def test_trade_alert_includes_symbol(self, mock_send):
        mock_send.return_value = True
        from src.notification.email_sender import send_trade_alert
        trade = {"action": "BUY", "symbol": "NVDA", "qty": 5,
                 "order_id": "abc", "status": "accepted",
                 "timestamp": "2026-05-24T10:00:00", "reason": "再平衡"}
        send_trade_alert("to@test.com", trade)
        html_arg = mock_send.call_args[0][2]
        assert "NVDA" in html_arg

    @patch("src.notification.email_sender.config")
    @patch("src.notification.email_sender._send_sendgrid")
    @patch("src.notification.email_sender._send_smtp")
    def test_uses_sendgrid_when_key_set(self, mock_smtp, mock_sg, mock_cfg):
        mock_cfg.SENDGRID_API_KEY = "SG.test_key"
        mock_sg.return_value = True
        from src.notification.email_sender import send_email
        send_email("to@test.com", "Sub", "<h1>Hi</h1>")
        assert mock_sg.called
        assert not mock_smtp.called

    @patch("src.notification.email_sender.config")
    @patch("src.notification.email_sender._send_sendgrid")
    @patch("src.notification.email_sender._send_smtp")
    def test_uses_smtp_when_no_sendgrid_key(self, mock_smtp, mock_sg, mock_cfg):
        mock_cfg.SENDGRID_API_KEY = ""
        mock_smtp.return_value = True
        from src.notification.email_sender import send_email
        send_email("to@test.com", "Sub", "<h1>Hi</h1>")
        assert mock_smtp.called
        assert not mock_sg.called

    def test_trade_alert_html_structure(self):
        from src.notification.email_sender import send_trade_alert
        from unittest.mock import patch
        with patch("src.notification.email_sender.send_email") as mock_send:
            mock_send.return_value = True
            trade = {"action": "SELL", "symbol": "AAPL", "qty": 3,
                     "order_id": "xyz", "status": "filled",
                     "account_id": "TEST123",
                     "timestamp": "2026-05-24T15:00:00", "reason": "停損"}
            send_trade_alert("to@test.com", trade)
            html = mock_send.call_args[0][2]
            assert "AAPL" in html
            assert "停損" in html

    def test_buy_sell_subject_format(self):
        from src.notification.email_sender import send_trade_alert
        with patch("src.notification.email_sender.send_email") as mock_send:
            mock_send.return_value = True
            trade = {"action": "BUY", "symbol": "MSFT", "qty": 10,
                     "order_id": "o1", "status": "accepted",
                     "timestamp": "2026-05-24T12:00:00", "reason": "再平衡"}
            send_trade_alert("to@test.com", trade)
            subject = mock_send.call_args[0][1]
            assert "MSFT" in subject
            assert "10" in subject

    def test_daily_report_subject_contains_date(self):
        with patch("src.notification.email_sender.send_email") as mock_send:
            mock_send.return_value = True
            from src.notification.email_sender import send_daily_report
            send_daily_report("to@test.com", "<h1/>" , "text", "2026-05-24")
            subject = mock_send.call_args[0][1]
            assert "2026-05-24" in subject

    def test_send_email_returns_bool(self):
        with patch("src.notification.email_sender._send_smtp") as mock_smtp:
            with patch("src.notification.email_sender.config") as mock_cfg:
                mock_cfg.SENDGRID_API_KEY = ""
                mock_smtp.return_value = True
                from src.notification.email_sender import send_email
                result = send_email("to@test.com", "Sub", "<p>Hi</p>")
                assert isinstance(result, bool)
