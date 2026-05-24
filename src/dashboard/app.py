"""
AlpacaBot Streamlit Dashboard（Cloud-First 版）

部署方式：
  Streamlit Cloud → 連接 d225d225/alpaca-bot，入口 streamlit_app.py
  本機           → streamlit run streamlit_app.py

資料優先序：
  1. Alpaca 即時 API（需 secrets）
  2. GitHub 已 commit 的 JSON 報告（只需網路，無需 API Key）
  3. 本地 reports/ 目錄（本機 fallback）
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.dashboard.data_provider import (
    DataProvider, make_provider_from_secrets,
    list_accounts_from_github,
)

# ── 頁面設定 ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="AlpacaBot Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  [data-testid="metric-container"] {
    background:#f8fafc; border-radius:10px; padding:12px; border-left:4px solid #0D9488;
  }
  .source-badge-live   { background:#d1fae5; color:#065f46; padding:2px 10px; border-radius:12px; font-size:.8rem; }
  .source-badge-report { background:#eff6ff; color:#1d4ed8; padding:2px 10px; border-radius:12px; font-size:.8rem; }
  .source-badge-none   { background:#fef2f2; color:#991b1b; padding:2px 10px; border-radius:12px; font-size:.8rem; }
  .disclaimer { background:#fffbeb; border:1px solid #fcd34d; border-radius:8px; padding:10px 14px; font-size:.8rem; color:#92400e; }
</style>
""", unsafe_allow_html=True)


# ── 工具函式 ─────────────────────────────────────────────────────
def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        import os
        return os.getenv(key, default)


def _source_badge(source: str) -> str:
    labels = {"live": "🟢 即時資料", "report": "📄 報告資料", "none": "⚠️ 無資料"}
    css_cls = {"live": "live", "report": "report", "none": "none"}.get(source, "none")
    return f'<span class="source-badge-{css_cls}">{labels.get(source, source)}</span>'


# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 設定")

    github_repo  = _get_secret("GITHUB_REPO",  "d225d225/alpaca-bot")
    github_token = _get_secret("GITHUB_TOKEN",  "")

    # 帳戶清單：從 GitHub 取（不需本地 accounts/ 目錄）
    @st.cache_data(ttl=300)
    def _cached_accounts(repo, token):
        accs = list_accounts_from_github(repo, token or None)
        return accs if accs else ["PA34JCP2N81D"]  # fallback 顯示預設帳號

    accounts = _cached_accounts(github_repo, github_token)
    selected_id = st.selectbox("選擇帳戶", accounts)

    st.divider()
    days         = st.slider("NAV 歷史天數", 30, 365, 180)
    show_nasdaq  = st.checkbox("顯示 NASDAQ", True)
    show_sp500   = st.checkbox("顯示 S&P 500", True)

    st.divider()
    if st.button("🔄 重新整理"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.caption("**Repo**")
    st.code(github_repo, language=None)


# ── DataProvider（含三層降級）──────────────────────────────────────
@st.cache_resource
def _get_provider(account_id: str) -> DataProvider:
    return make_provider_from_secrets(account_id)

provider = _get_provider(selected_id)


# ── Header ────────────────────────────────────────────────────────
st.title("📈 AlpacaBot Dashboard")
snap = provider.get_snapshot()
source_html = _source_badge(snap.source)
latest_report = provider.get_latest_report()
strategy_id   = latest_report.strategy_id if latest_report else "—"
report_date   = latest_report.report_date if latest_report else "—"

st.markdown(
    f"帳戶：`{selected_id}`  ·  策略：`{strategy_id}`  ·  "
    f"最後報告：`{report_date}`  ·  {source_html}",
    unsafe_allow_html=True,
)
if not provider.is_live:
    st.info("ℹ️ 未設定 Alpaca API Key，以歷史報告模式顯示。如需即時資料請在 Streamlit Secrets 填入 API 金鑰。")

# ── 帳戶快照（4 格指標）──────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("💵 現金水位",  f"${snap.cash:,.2f}")
c2.metric("📊 NAV 淨值",  f"${snap.portfolio_value:,.2f}", delta=f"{snap.nav_change_pct:+.2f}%")
c3.metric("📦 持倉市值",  f"${snap.long_market_value:,.2f}")
c4.metric("💼 淨資產",    f"${snap.equity:,.2f}")

# 回撤 & 累積損益（從報告讀）
if latest_report:
    c5, c6, c7, c8 = st.columns(4)
    bm = provider.get_benchmark_returns()
    c5.metric("📉 最大回撤",   f"{latest_report.max_drawdown_pct:.2f}%")
    c6.metric("💹 累積損益",   f"{latest_report.total_pl_pct:+.2f}%")
    c7.metric("🏷 NASDAQ 今日", f"{bm['nasdaq']:+.2f}%")
    c8.metric("🏷 S&P500 今日", f"{bm['sp500']:+.2f}%")

st.divider()

# ── NAV 走勢圖 ────────────────────────────────────────────────────
st.markdown("#### 📉 NAV 淨值走勢")

@st.cache_data(ttl=300)
def _nav_history(account_id, max_days):
    return provider.get_nav_history(days=max_days)

nav_points = _nav_history(selected_id, days)

fig = go.Figure()
if nav_points:
    xs = [p.date for p in nav_points]
    ys = [p.nav  for p in nav_points]
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines", name="我的帳戶",
        line=dict(color="#0D9488", width=2.5),
        fill="tozeroy", fillcolor="rgba(13,148,136,0.08)",
    ))

    # 從已存報告取指數資料（不再即時呼叫 yfinance）
    if show_nasdaq or show_sp500:
        @st.cache_data(ttl=600)
        def _benchmark(repo):
            try:
                from src.market.market_data import get_nasdaq_history, get_sp500_history
                return get_nasdaq_history(days), get_sp500_history(days)
            except Exception:
                return None, None

        nasdaq_hist, sp500_hist = _benchmark(github_repo)
        base_nav = ys[0] if ys else 1

        if show_nasdaq and nasdaq_hist is not None and len(nasdaq_hist) > 0:
            norm = nasdaq_hist / nasdaq_hist.iloc[0] * base_nav
            fig.add_trace(go.Scatter(
                x=norm.index.astype(str), y=norm.values, mode="lines",
                name="NASDAQ", line=dict(color="#6366F1", width=1.5, dash="dot"),
            ))
        if show_sp500 and sp500_hist is not None and len(sp500_hist) > 0:
            norm = sp500_hist / sp500_hist.iloc[0] * base_nav
            fig.add_trace(go.Scatter(
                x=norm.index.astype(str), y=norm.values, mode="lines",
                name="S&P 500", line=dict(color="#F59E0B", width=1.5, dash="dash"),
            ))
else:
    st.info("尚無 NAV 歷史報告，GitHub Actions 每日執行後資料將自動顯示。")

fig.update_layout(
    height=300, margin=dict(l=0, r=0, t=8, b=0),
    yaxis_title="NAV ($)", legend=dict(orientation="h", y=1.08),
    plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
    yaxis=dict(gridcolor="#f1f5f9"), xaxis=dict(gridcolor="#f1f5f9"),
)
st.plotly_chart(fig, use_container_width=True)
st.divider()

# ── 持倉清單 & 收益 ──────────────────────────────────────────────
col_l, col_r = st.columns([3, 2])

with col_l:
    st.markdown("#### 📋 目前持倉")
    positions = provider.get_positions()
    if positions:
        df = pd.DataFrame(positions)
        display_cols = {
            "symbol": "股票", "qty": "股數",
            "avg_cost": "成本", "current_price": "現價",
            "market_value": "市值", "unrealized_pl": "未實現損益",
            "unrealized_pl_pct": "損益%",
        }
        df = df.rename(columns={k: v for k, v in display_cols.items() if k in df.columns})
        for col in ["成本", "現價", "市值"]:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"${x:,.2f}")
        if "未實現損益" in df.columns:
            df["未實現損益"] = df["未實現損益"].apply(lambda x: f"${x:+,.2f}")
        if "損益%" in df.columns:
            df["損益%"] = df["損益%"].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("目前無持倉")

with col_r:
    st.markdown("#### 📈 各股收益率")
    if latest_report and latest_report.top10_returns:
        rows = []
        for sym in (latest_report.top10_symbols or []):
            rets = latest_report.top10_returns.get(sym, {})
            rows.append({
                "股票": sym,
                "1日%": f"{rets.get('1d', 0):+.2f}%",
                "1週%": f"{rets.get('1w', 0):+.2f}%",
                "1月%": f"{rets.get('1m', 0):+.2f}%",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("報告中尚無報酬率資料")

st.divider()

# ── Top 10 NASDAQ（從報告讀，不即時呼叫 API）────────────────────
st.markdown("#### 🏆 NASDAQ Top 10 績效 & 本益比")
top10_data = provider.get_top10_from_report()

if top10_data:
    symbols = top10_data["symbols"]
    returns = top10_data["returns"]
    pe_data = top10_data["pe"]
    prices  = top10_data["prices"]

    rows = []
    for i, sym in enumerate(symbols, 1):
        rets  = returns.get(sym, {})
        pe    = pe_data.get(sym)
        price = prices.get(sym, 0)
        rows.append({
            "#": i, "股票": sym,
            "股價": f"${price:,.2f}",
            "1日%": f"{rets.get('1d',0):+.2f}%",
            "1週%": f"{rets.get('1w',0):+.2f}%",
            "1月%": f"{rets.get('1m',0):+.2f}%",
            "本益比": f"{pe:.1f}" if pe else "N/A",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # 柱狀圖
    period_opt = st.radio("顯示期間", ["1日", "1週", "1月"], horizontal=True)
    pk = {"1日": "1d", "1週": "1w", "1月": "1m"}[period_opt]
    vals   = [returns.get(s, {}).get(pk, 0) for s in symbols]
    colors = ["#059669" if v >= 0 else "#dc2626" for v in vals]
    fig2 = go.Figure(go.Bar(
        x=symbols, y=vals, marker_color=colors,
        text=[f"{v:+.2f}%" for v in vals], textposition="outside",
    ))
    fig2.update_layout(
        height=260, margin=dict(l=0, r=0, t=16, b=0),
        yaxis_title=f"{period_opt} 報酬率 (%)",
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        yaxis=dict(gridcolor="#f1f5f9"),
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("等待首次 GitHub Actions 執行後，Top 10 資料將自動填入。")

st.divider()

# ── 自選股三大類別 ────────────────────────────────────────────────
wl = provider.get_watchlist_from_report()
if wl:
    st.markdown("#### 👁 自選股追蹤")
    for category, prices_dict in wl.items():
        st.caption(f"**{category.upper()}**")
        cols = st.columns(min(len(prices_dict), 5))
        for col, (sym, price) in zip(cols, prices_dict.items()):
            col.metric(sym, f"${float(price):,.2f}")
    st.divider()

# ── 歷史報告回查 ──────────────────────────────────────────────────
st.markdown("#### 📂 歷史報告回查")
all_dates = provider.list_report_dates()
if all_dates:
    chosen = st.selectbox("選擇日期", all_dates)
    if st.button("載入報告"):
        hist = provider.get_report(chosen)
        if hist:
            st.json(hist.to_json())
else:
    st.info("尚無歷史報告。GitHub Actions 每個交易日執行後報告將自動出現。")

# ── 免責聲明 ──────────────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
⚠️ 本 Dashboard 顯示內容僅供資訊整理與研究參考，不構成投資建議。
所有排名、績效數據僅基於公開資料計算，投資人應自行評估投資風險。
</div>
""", unsafe_allow_html=True)
