"""
AlpacaBot Streamlit Dashboard
啟動：streamlit run src/dashboard/app.py
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from src.core.config import config
from src.core.account_manager import AccountManager
from src.report.report_storage import (
    load_report, list_report_dates, load_nav_history, load_prev_nav
)
from src.market.market_data import (
    get_returns_bulk, get_nasdaq_history, get_sp500_history, get_prices_bulk
)
from src.market.pe_calculator import get_pe_bulk
from dotenv import load_dotenv
load_dotenv()

# ── Page Config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="AlpacaBot Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="metric-container"] { background:#f8fafc; border-radius:10px; padding:12px; border-left:4px solid #0D9488; }
  .disclaimer { background:#fffbeb; border:1px solid #fcd34d; border-radius:8px; padding:10px 14px; font-size:.8rem; color:#92400e; }
  .section-title { font-size:1.1rem; font-weight:700; color:#0F2044; margin-bottom:.5rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_manager() -> AccountManager:
    return AccountManager()


@st.cache_data(ttl=300)
def fetch_top10_data(symbols: tuple) -> tuple:
    symbols = list(symbols)
    returns = get_returns_bulk(symbols)
    pe_data = get_pe_bulk(symbols)
    prices  = get_prices_bulk(symbols)
    return returns, pe_data, prices


@st.cache_data(ttl=600)
def fetch_benchmark(days: int) -> tuple:
    nasdaq = get_nasdaq_history(days)
    sp500  = get_sp500_history(days)
    return nasdaq, sp500


# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 設定")
    manager = get_manager()
    accs = manager.all_active()
    if not accs:
        st.error("找不到任何帳戶設定檔")
        st.stop()

    account_ids = [a.account_id for a in accs]
    selected_id = st.selectbox("選擇帳戶", account_ids)
    acc_cfg = manager.get_account(selected_id)

    st.divider()
    days = st.slider("NAV 歷史天數", 30, 365, 180)
    show_nasdaq = st.checkbox("顯示 NASDAQ", value=True)
    show_sp500  = st.checkbox("顯示 S&P 500", value=True)

    st.divider()
    st.markdown(f"**策略：** `{acc_cfg.strategy_id}`")
    st.markdown(f"**帳戶：** `{acc_cfg.account_id}`")
    if acc_cfg.paper:
        st.info("🧪 Paper Trading 模式")

    st.divider()
    refresh = st.button("🔄 重新整理資料")
    if refresh:
        st.cache_data.clear()


# ── Header ───────────────────────────────────────────────────────
st.title("📈 AlpacaBot Dashboard")
st.caption(f"帳戶：{selected_id}  ·  策略：{acc_cfg.strategy_id}  ·  *資料每 5 分鐘更新*")

# ── 即時帳戶資料 ──────────────────────────────────────────────────
try:
    client = manager.get_client(selected_id)
    acct   = client.get_account()
    cash   = float(acct.cash)
    equity = float(acct.equity)
    pv     = float(acct.portfolio_value)
    long_mv = float(acct.long_market_value)

    prev_nav = load_prev_nav(selected_id)
    nav_chg  = ((pv - prev_nav) / prev_nav * 100) if prev_nav else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💵 現金水位",    f"${cash:,.2f}")
    col2.metric("📊 NAV 淨值",   f"${pv:,.2f}",   delta=f"{nav_chg:+.2f}%")
    col3.metric("📦 持倉市值",   f"${long_mv:,.2f}")
    col4.metric("💼 淨資產",     f"${equity:,.2f}")

except Exception as e:
    st.warning(f"⚠️ 無法連線 Alpaca API：{e}  \n（顯示歷史報告資料）")
    cash = long_mv = pv = equity = 0.0

st.divider()

# ── NAV 走勢圖 ────────────────────────────────────────────────────
st.markdown('<div class="section-title">📉 NAV 淨值走勢</div>', unsafe_allow_html=True)

nav_history = load_nav_history(selected_id, last_n=days)
dates_available = list_report_dates(selected_id)[:days]
dates_available_rev = list(reversed(dates_available))

fig = go.Figure()
if nav_history and dates_available_rev:
    fig.add_trace(go.Scatter(
        x=dates_available_rev, y=nav_history,
        mode="lines", name="我的帳戶",
        line=dict(color="#0D9488", width=2.5),
        fill="tozeroy", fillcolor="rgba(13,148,136,0.08)",
    ))

if show_nasdaq or show_sp500:
    nasdaq_hist, sp500_hist = fetch_benchmark(days)
    if show_nasdaq and len(nasdaq_hist) > 0:
        # 標準化：以第一天為基準
        nasdaq_norm = nasdaq_hist / nasdaq_hist.iloc[0] * (nav_history[0] if nav_history else 100)
        fig.add_trace(go.Scatter(
            x=nasdaq_norm.index.astype(str), y=nasdaq_norm.values,
            mode="lines", name="NASDAQ",
            line=dict(color="#6366F1", width=1.5, dash="dot"),
        ))
    if show_sp500 and len(sp500_hist) > 0:
        sp500_norm = sp500_hist / sp500_hist.iloc[0] * (nav_history[0] if nav_history else 100)
        fig.add_trace(go.Scatter(
            x=sp500_norm.index.astype(str), y=sp500_norm.values,
            mode="lines", name="S&P 500",
            line=dict(color="#F59E0B", width=1.5, dash="dash"),
        ))

fig.update_layout(
    height=320, margin=dict(l=0, r=0, t=10, b=0),
    yaxis_title="NAV ($)", xaxis_title="",
    legend=dict(orientation="h", y=1.08),
    plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
    yaxis=dict(gridcolor="#f1f5f9"), xaxis=dict(gridcolor="#f1f5f9"),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── 持倉清單 ──────────────────────────────────────────────────────
col_l, col_r = st.columns([3, 2])

with col_l:
    st.markdown('<div class="section-title">📋 目前持倉</div>', unsafe_allow_html=True)
    try:
        positions = client.get_positions()
        if positions:
            rows = []
            for p in positions:
                upl     = float(p.unrealized_pl or 0)
                upl_pct = float(p.unrealized_plpc or 0) * 100
                rows.append({
                    "股票": p.symbol,
                    "股數": int(float(p.qty)),
                    "成本": f"${float(p.avg_entry_price or 0):,.2f}",
                    "現價": f"${float(p.current_price or 0):,.2f}",
                    "市值": f"${float(p.market_value or 0):,.2f}",
                    "未實現損益": f"${upl:+,.2f} ({upl_pct:+.1f}%)",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("目前無持倉")
    except Exception as e:
        st.warning(f"無法取得持倉：{e}")

with col_r:
    st.markdown('<div class="section-title">📈 各股收益率</div>', unsafe_allow_html=True)
    try:
        if positions:
            syms = [p.symbol for p in positions]
            returns = get_returns_bulk(syms)
            rows = [{"股票": s, "1日%": f"{returns[s].get('1d',0):+.2f}%",
                     "1週%": f"{returns[s].get('1w',0):+.2f}%",
                     "1月%": f"{returns[s].get('1m',0):+.2f}%"} for s in syms]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"無法取得收益率：{e}")

st.divider()

# ── Top 10 NASDAQ ─────────────────────────────────────────────────
st.markdown('<div class="section-title">🏆 NASDAQ Top 10 績效 & 本益比</div>', unsafe_allow_html=True)

from src.market.market_data import get_top_n_nasdaq
top10 = get_top_n_nasdaq(10)
returns_data, pe_data, prices_data = fetch_top10_data(tuple(top10))

rows = []
for i, sym in enumerate(top10, 1):
    rets  = returns_data.get(sym, {})
    pe    = pe_data.get(sym)
    price = prices_data.get(sym, 0)
    rows.append({
        "#": i, "股票": sym,
        "股價": f"${price:,.2f}",
        "1日%":  f"{rets.get('1d',0):+.2f}%",
        "1週%":  f"{rets.get('1w',0):+.2f}%",
        "1月%":  f"{rets.get('1m',0):+.2f}%",
        "本益比": f"{pe:.1f}" if pe else "N/A",
        "PE 說明": "合理" if pe and pe < 30 else ("偏高" if pe and pe < 60 else "極高" if pe else "N/A"),
    })

df10 = pd.DataFrame(rows)
st.dataframe(df10, use_container_width=True, hide_index=True)

# ── 柱狀圖：Top 10 報酬率 ─────────────────────────────────────────
period_opt = st.radio("顯示期間", ["1日", "1週", "1月"], horizontal=True)
period_key = {"1日": "1d", "1週": "1w", "1月": "1m"}[period_opt]

bar_vals  = [returns_data.get(s, {}).get(period_key, 0) for s in top10]
bar_colors = ["#059669" if v >= 0 else "#dc2626" for v in bar_vals]
fig2 = go.Figure(go.Bar(
    x=top10, y=bar_vals,
    marker_color=bar_colors,
    text=[f"{v:+.2f}%" for v in bar_vals],
    textposition="outside",
))
fig2.update_layout(
    height=280, margin=dict(l=0, r=0, t=20, b=0),
    yaxis_title=f"{period_opt} 報酬率 (%)",
    plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
    yaxis=dict(gridcolor="#f1f5f9"),
)
st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── 自選股三大類別 ────────────────────────────────────────────────
if acc_cfg.watchlists:
    st.markdown('<div class="section-title">👁 自選股追蹤</div>', unsafe_allow_html=True)
    for category, symbols in acc_cfg.watchlists.items():
        prices_wl = get_prices_bulk(symbols)
        rets_wl   = get_returns_bulk(symbols)
        cols = st.columns(len(symbols))
        st.caption(f"**{category.upper()}**")
        for col, sym in zip(cols, symbols):
            price = prices_wl.get(sym, 0)
            ret1d = rets_wl.get(sym, {}).get("1d", 0)
            col.metric(sym, f"${price:,.2f}", delta=f"{ret1d:+.2f}%")

st.divider()

# ── 歷史報告回查 ──────────────────────────────────────────────────
st.markdown('<div class="section-title">📂 歷史報告回查</div>', unsafe_allow_html=True)
all_dates = list_report_dates(selected_id)
if all_dates:
    chosen_date = st.selectbox("選擇日期", all_dates)
    hist_report = load_report(selected_id, chosen_date)
    if hist_report:
        st.json(hist_report.to_json())
else:
    st.info("尚無歷史報告")

# ── 免責聲明 ──────────────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
⚠️ 本 Dashboard 顯示內容僅供資訊整理與研究參考，不構成投資建議。
所有排名、績效數據僅基於公開資料計算，投資人應自行評估投資風險。
</div>
""", unsafe_allow_html=True)
