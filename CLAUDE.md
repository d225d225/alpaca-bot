# CLAUDE.md — AlpacaBot 專案記憶

> 這個檔案是給 Claude 或任何接手開發者快速了解本專案的核心文件。

---

## 專案概覽

**AlpacaBot** 是一套全自動美股投資輔助系統，核心功能：
- 透過 Alpaca Paper/Live API 自動下單
- 每天 GitHub Actions 自動執行策略 & 生成報告
- Streamlit Dashboard 視覺化展示
- 每天 06:00（台灣時間）Email 通知日報
- 多帳戶管理、JSON 策略引擎

---

## GitHub Repo

| 項目 | 值 |
|------|-----|
| Repo | d225d225/alpaca-bot |
| Paper API | https://paper-api.alpaca.markets/v2 |
| Account | PA34JCP2N81D |

---

## 目錄結構

```
alpaca-bot/
├── .github/workflows/daily_trading.yml  # 每日自動執行
├── accounts/                            # 帳戶設定 JSON
├── strategies/                          # 策略 JSON + schema
├── reports/                             # 歷史報告（自動 commit）
├── src/
│   ├── core/         # config, alpaca_client, account_manager
│   ├── strategy/     # strategy_loader, strategy_executor
│   ├── market/       # market_data, pe_calculator, stock_screener
│   ├── trading/      # order_manager, position_manager, rebalancer
│   ├── report/       # report_model (JSON), report_view (HTML), report_storage
│   ├── notification/ # email_sender + HTML 模板
│   └── dashboard/    # Streamlit app.py
├── tests/            # pytest 測試（102+ cases）
├── main.py           # 命令列入口
└── requirements.txt
```

---

## 核心設計原則

| 原則 | 說明 |
|------|------|
| 策略 JSON 化 | 新策略只需新增 strategies/*.json，不動 Python |
| 多帳戶 | accounts/ 每個 JSON 一個帳戶，自動載入 |
| 每帳戶一策略 | 帳戶 JSON 內 strategy_id 欄位，可隨時更換 |
| 報告 Model/View 分離 | report_model.py 輸出純 JSON，report_view.py 渲染 HTML |
| 歷史報告 | 每日報告存 reports/{account_id}/{date}/report.json |
| 再平衡觸發點 | 新資金 OR 每月初（on_new_funds / monthly） |
| 投資配置 | 每檔 10%（alloc_pct），只買整數股 |
| 先賣後買 | 再平衡時先執行賣出，確保有現金再買入 |

---

## 技術架構

| 層 | 套件 |
|----|------|
| 交易 API | alpaca-py |
| 市場資料 | yfinance（快速）/ Polygon.io（進階） |
| Dashboard | Streamlit + Plotly |
| Email | SendGrid（優先）/ SMTP 備用 |
| 模板 | Jinja2 |
| 排程 | GitHub Actions（每天 21:00 UTC = 台灣次日 05:00） |
| 測試 | pytest + unittest.mock |

---

## 策略 JSON 格式

```json
{
  "strategy_id": "momentum_top10",
  "name": "動能前十策略",
  "universe": "NASDAQ_TOP_MC",
  "top_n": 10,
  "alloc_pct": 10,
  "whole_shares": true,
  "stop_loss_pct": -8,
  "take_profit_pct": 25,
  "notify_on_trade": true,
  "rebalance": { "on_new_funds": true, "monthly": true },
  "filters": { "min_price": 5, "max_pe": 200, "min_volume": 1000000 }
}
```

**新增策略只需新增此格式 JSON，不需修改任何 Python 程式碼。**

---

## 環境變數（GitHub Secrets）

| 變數 | 用途 |
|------|------|
| ALPACA_API_KEY | Alpaca API Key |
| ALPACA_API_SECRET | Alpaca API Secret |
| ALPACA_BASE_URL | API 端點（paper/live） |
| SENDGRID_API_KEY | Email 發送 |
| EMAIL_FROM / EMAIL_TO | 寄件 / 收件地址 |
| SMTP_HOST/PORT/USER/PASS | SMTP 備用 |

---

## 開發指令

```bash
# 安裝套件
pip install -r requirements.txt

# 執行全套流程
python main.py run

# 只看帳戶狀態
python main.py status

# 只生成報告（不交易）
python main.py report

# 只寄送 Email
python main.py email

# 啟動 Dashboard
streamlit run src/dashboard/app.py

# 執行測試
pytest
```

---

## 測試總覽（102 cases）

| 測試檔 | 模組 | Cases |
|--------|------|-------|
| test_p1_core.py | config, alpaca_client, account_manager | 15 |
| test_p2_strategy.py | strategy_loader | 12 |
| test_p3_market.py | market_data, pe_calculator | 14 |
| test_p4_trading.py | order_manager, position_manager, rebalancer | 16 |
| test_p5_report.py | report_model, report_storage, report_view | 13 |
| test_p6_email.py | email_sender | 10 |
| test_p7_rebalance.py | strategy_executor, rebalancer 進階 | 12 |
| test_p8_integration.py | 跨模組整合 + 多帳戶 | 12 |

---

## 投資風險提醒

> ⚠️ 本系統僅供資訊整理與研究參考，不構成投資建議。
> 所有排名、績效數據僅基於公開資料計算。
> 投資人應自行評估風險，過去績效不代表未來表現。
