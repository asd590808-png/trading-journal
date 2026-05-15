"""
Prop Firm Trading Journal — Cloud Edition v2
Fixed: sidebar outside tabs, header not clipped
"""

import streamlit as st
import pandas as pd
import json
import os
import base64
import gspread
from google.oauth2.service_account import Credentials
from datetime import date
import plotly.graph_objects as go

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="交易日誌",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Symbol Database ──────────────────────────────────────────────────────────
SYMBOL_DB = {
    "MNQ": {"name":"Micro Nasdaq (MNQ)",  "point_value":2.0,   "tick_size":0.25,"tick_value":0.50,  "desc":"納斯達克微型合約｜1 點 = $2",   "ex":"19500.25"},
    "MES": {"name":"Micro S&P 500 (MES)", "point_value":5.0,   "tick_size":0.25,"tick_value":1.25,  "desc":"標普 500 微型合約｜1 點 = $5",  "ex":"5300.50"},
    "MGC": {"name":"Micro Gold (MGC)",    "point_value":10.0,  "tick_size":0.10,"tick_value":1.00,  "desc":"微型黃金合約｜1 點 = $10",      "ex":"2380.10"},
    "GC":  {"name":"Gold (GC)",           "point_value":100.0, "tick_size":0.10,"tick_value":10.00, "desc":"標準黃金合約｜1 點 = $100",     "ex":"2380.10"},
    "NQ":  {"name":"Nasdaq (NQ)",         "point_value":20.0,  "tick_size":0.25,"tick_value":5.00,  "desc":"納斯達克標準合約｜1 點 = $20",  "ex":"19500.25"},
    "ES":  {"name":"S&P 500 (ES)",        "point_value":50.0,  "tick_size":0.25,"tick_value":12.50, "desc":"標普 500 標準合約｜1 點 = $50", "ex":"5300.50"},
    "自訂": {"name":"自訂標的",           "point_value":1.0,   "tick_size":1.0, "tick_value":1.0,   "desc":"其他合約，請手動填入每點美金價值","ex":"—"},
}
SYMBOL_LIST = ["MNQ","MES","MGC","GC","NQ","ES","自訂"]
PSY_LIST    = ["冷靜執行","FOMO 追價","復仇交易","過度自信","過早平倉","計劃外進場","其他"]

TRADE_COLS = [
    "date","symbol","direction","entry","exit",
    "stop_usd","contracts","point_value",
    "pnl","r_multiple","psychology","notes","screenshot_b64"
]

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@300;400;500&family=Noto+Sans+TC:wght@300;400;500&family=IM+Fell+English:ital@1&display=swap');

:root {
    --bg:#1A1C1E; --bg2:#22252A; --sidebar:#1E2126; --text:#C8C3BC; --muted:#60646C;
    --border:#2E3240; --red:#C05050; --red-dim:rgba(192,80,80,0.14);
    --slate:#7A8FA0; --green:#528060; --grn-dim:rgba(82,128,96,0.14);
    --card:#24272E; --input:#2A2E37; --accent:#8FAABF;
    --amber:#B89060; --amb-dim:rgba(184,144,96,0.14);
}

html, body, [class*="css"] {
    font-family: 'Noto Sans TC', sans-serif !important;
    color: var(--text) !important;
    background-color: var(--bg) !important;
}
.stApp, .main { background-color: var(--bg) !important; }
.block-container {
    padding-top: 1.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 100% !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background-color: var(--sidebar) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * { color: var(--text) !important; }
section[data-testid="stSidebar"] label {
    font-size: 0.76rem !important; color: var(--muted) !important;
    font-weight: 300 !important; letter-spacing: 0.04em !important;
}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] .stSelectbox > div > div {
    background-color: var(--input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 3px !important; color: var(--text) !important;
}

/* ── Inputs ── */
.stTextInput input, .stNumberInput input,
.stSelectbox > div > div, .stDateInput input,
[data-baseweb="input"] input {
    background-color: var(--input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 3px !important; color: var(--text) !important;
    font-family: 'Noto Sans TC', sans-serif !important;
}
input::placeholder { color: var(--muted) !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    background-color: var(--card) !important;
    border: 1px dashed var(--border) !important;
    border-radius: 4px !important;
}
[data-testid="stFileUploader"] * { color: var(--text) !important; }

/* Dropdown */
[data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {
    background-color: var(--bg2) !important;
    border: 1px solid var(--border) !important;
}
[role="option"] { background-color: var(--bg2) !important; color: var(--text) !important; }
[role="option"]:hover { background-color: var(--card) !important; }

/* Buttons */
.stButton > button {
    background-color: var(--slate) !important; color: #1A1C1E !important;
    border: none !important; border-radius: 3px !important;
    font-family: 'Noto Sans TC', sans-serif !important;
    font-weight: 400 !important; letter-spacing: 0.08em !important;
    padding: 0.5rem 1.5rem !important; transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background-color: var(--accent) !important;
    box-shadow: 0 2px 12px rgba(122,143,160,0.25) !important;
    transform: translateY(-1px) !important;
}
.stDownloadButton > button {
    background-color: transparent !important; color: var(--slate) !important;
    border: 1px solid var(--border) !important; border-radius: 3px !important;
}
.stDownloadButton > button:hover {
    background-color: var(--card) !important; border-color: var(--slate) !important;
}

hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 1.2rem 0 !important; }

/* Metric */
[data-testid="stMetric"] {
    background-color: var(--card) !important; border: 1px solid var(--border) !important;
    border-radius: 4px !important; padding: 1rem 1.2rem !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.66rem !important; letter-spacing: 0.16em !important;
    text-transform: uppercase !important; color: var(--muted) !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Noto Serif TC', serif !important;
    font-size: 1.4rem !important; color: var(--text) !important;
}

/* Progress */
.stProgress > div > div { background-color: var(--border) !important; }
.stProgress > div > div > div > div { background-color: var(--green) !important; }

/* DataFrame */
.stDataFrame { border: 1px solid var(--border) !important; border-radius: 4px !important; }

/* Section header */
.sec {
    font-size: 0.62rem; letter-spacing: 0.32em; text-transform: uppercase;
    color: var(--muted); border-bottom: 1px solid var(--border);
    padding-bottom: 0.35rem; margin: 1.6rem 0 1rem;
}

/* Field label */
.flabel { font-size: 0.72rem; color: var(--muted); margin-bottom: 0.15rem; letter-spacing: 0.04em; line-height: 1.5; }
.fex { font-size: 0.66rem; color: #404558; font-style: italic; }

/* Risk boxes */
.rw { background: var(--red-dim); border-left: 3px solid var(--red); border-radius: 0 3px 3px 0;
      padding: 0.75rem 1rem; margin: 0.3rem 0; font-size: 0.8rem; color: #D07070; line-height: 1.65; }
.rs { background: var(--grn-dim); border-left: 3px solid var(--green); border-radius: 0 3px 3px 0;
      padding: 0.75rem 1rem; margin: 0.3rem 0; font-size: 0.8rem; color: #80B090; line-height: 1.65; }

/* Info box */
.ibox {
    background: var(--card); border: 1px solid var(--border); border-radius: 4px;
    padding: 0.9rem 1.1rem; margin: 0.5rem 0; line-height: 1.8; font-size: 0.85rem;
}
.edit-banner {
    background: var(--amb-dim); border: 1px solid var(--amber);
    border-radius: 4px; padding: 0.8rem 1.1rem; margin-bottom: 1rem;
    font-size: 0.82rem; color: #D0A870; line-height: 1.7;
}

/* Symbol card */
.sym-card {
    background: var(--card); border: 1px solid var(--border);
    border-left: 3px solid var(--accent); border-radius: 0 4px 4px 0;
    padding: 0.65rem 1rem; margin: 0.4rem 0 0.9rem;
    font-size: 0.78rem; color: var(--text); line-height: 1.65;
}

/* Stop hint */
.stop-hint {
    background: var(--amb-dim); border-left: 2px solid var(--amber);
    border-radius: 0 3px 3px 0; padding: 0.45rem 0.8rem;
    font-size: 0.72rem; color: #C0A070; margin-top: 0.2rem; line-height: 1.5;
}

/* Screenshot */
.shot-card {
    background: var(--card); border: 1px solid var(--border);
    border-left: 3px solid var(--accent); border-radius: 0 4px 4px 0;
    padding: 0.6rem 1rem; margin: 0.3rem 0; font-size: 0.78rem;
    color: var(--muted); line-height: 1.6;
}
.lb-wrap {
    background: rgba(0,0,0,0.85); border-radius: 6px;
    padding: 0.5rem; margin: 0.5rem 0; text-align: center;
}
.lb-wrap img { max-width: 100%; border-radius: 4px; }

/* Trade card */
.trade-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 4px; padding: 0.9rem 1.1rem; margin: 0.5rem 0; line-height: 1.9;
}
.trade-card-win  { border-left: 3px solid var(--green); }
.trade-card-loss { border-left: 3px solid var(--red); }

/* Title */
.mtitle {
    font-family: 'Noto Serif TC', serif; font-weight: 300;
    font-size: 1.55rem; letter-spacing: 0.18em; color: var(--text);
}
.msub {
    font-family: 'IM Fell English', serif; font-style: italic;
    font-size: 0.8rem; color: var(--muted); letter-spacing: 0.06em;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important; gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; color: var(--muted) !important;
    font-size: 0.7rem !important; letter-spacing: 0.14em !important;
    text-transform: uppercase !important; border-radius: 0 !important;
    padding: 0.5rem 1.4rem !important;
}
.stTabs [aria-selected="true"] {
    color: var(--text) !important;
    border-bottom: 2px solid var(--accent) !important;
    background: transparent !important;
}

/* Expander */
.streamlit-expanderHeader {
    background-color: var(--card) !important; border-radius: 4px !important;
    color: var(--text) !important; font-size: 0.8rem !important;
}
.streamlit-expanderContent {
    background-color: var(--card) !important;
    border: 1px solid var(--border) !important;
}

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
</style>
""", unsafe_allow_html=True)


# ─── Google Sheets ────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource(show_spinner=False)
def get_gc():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def open_wb():
    return get_gc().open_by_key(st.secrets["sheet_id"])

def ensure_sheets(wb):
    titles = [ws.title for ws in wb.worksheets()]
    if "settings" not in titles:
        ws = wb.add_worksheet("settings", rows=10, cols=2)
        ws.update("A1:B6", [
            ["key","value"],
            ["account_name","Topstep 50K"],
            ["initial_balance","50000"],
            ["daily_loss_limit","1000"],
            ["max_drawdown","2000"],
            ["profit_target","3000"],
        ])
    if "trades" not in titles:
        ws = wb.add_worksheet("trades", rows=2, cols=len(TRADE_COLS))
        ws.update("A1", [TRADE_COLS])

def load_settings(wb):
    rows = wb.worksheet("settings").get_all_values()[1:]
    out  = {}
    for r in rows:
        if len(r) >= 2: out[r[0]] = r[1]
    defaults = {"account_name":"Topstep 50K","initial_balance":"50000",
                "daily_loss_limit":"1000","max_drawdown":"2000","profit_target":"3000"}
    for k,v in defaults.items():
        if k not in out: out[k] = v
    for k in ["initial_balance","daily_loss_limit","max_drawdown","profit_target"]:
        try: out[k] = float(out[k])
        except: out[k] = float(defaults[k])
    return out

def save_settings(wb, s):
    ws = wb.worksheet("settings")
    ws.clear()
    ws.update("A1", [["key","value"]] + [[k,str(v)] for k,v in s.items()])

def load_trades(wb):
    rows = wb.worksheet("trades").get_all_values()
    if len(rows) < 2: return []
    headers = rows[0]
    out = []
    for row in rows[1:]:
        row = row + [""] * (len(headers) - len(row))
        t = dict(zip(headers, row))
        for f in ["entry","exit","stop_usd","contracts","point_value","pnl","r_multiple"]:
            try:    t[f] = float(t[f]) if t.get(f,"") != "" else 0.0
            except: t[f] = 0.0
        try:    t["contracts"] = int(t["contracts"])
        except: t["contracts"] = 1
        out.append(t)
    return out

def save_trades(wb, trades):
    ws = wb.worksheet("trades")
    ws.clear()
    rows = [TRADE_COLS]
    for t in trades:
        rows.append([str(t.get(c,"")) for c in TRADE_COLS])
    ws.update("A1", rows)

@st.cache_data(ttl=30, show_spinner="載入資料中…")
def fetch_all():
    wb = open_wb()
    ensure_sheets(wb)
    return load_settings(wb), load_trades(wb)

def persist():
    wb = open_wb()
    save_settings(wb, st.session_state.settings)
    save_trades(wb, st.session_state.trades)
    fetch_all.clear()


# ─── Image helpers ────────────────────────────────────────────────────────────
def img_to_b64(f) -> str:
    return base64.b64encode(f.getbuffer()).decode()

def b64_to_bytes(s) -> bytes:
    return base64.b64decode(s)

def b64_mime(s) -> str:
    try:
        h = base64.b64decode(s[:16])
        if h[:4] == b'\x89PNG': return "png"
        if h[:2] == b'\xff\xd8': return "jpeg"
    except: pass
    return "png"


# ─── Helpers ─────────────────────────────────────────────────────────────────
def field(label, example=""):
    ex = f'<span class="fex">（例：{example}）</span>' if example else ""
    st.markdown(f'<div class="flabel">{label} {ex}</div>', unsafe_allow_html=True)

def calc_pnl(symbol, direction, entry, exit_p, contracts, custom_pv=1.0):
    pv  = SYMBOL_DB[symbol]["point_value"] if symbol != "自訂" else custom_pv
    pts = (exit_p - entry) if direction == "Long" else (entry - exit_p)
    return pts * pv * contracts


# ─── Session State init ───────────────────────────────────────────────────────
if "initialized" not in st.session_state:
    try:
        s, t = fetch_all()
        st.session_state.settings    = s
        st.session_state.trades      = t
        st.session_state.initialized = True
        st.session_state.wb_error    = False
    except Exception as e:
        st.session_state.wb_error   = True
        st.session_state.wb_err_msg = str(e)

if st.session_state.get("wb_error"):
    st.error(f"⚠️ 無法連線 Google Sheets：{st.session_state.wb_err_msg}")
    st.info("請確認 Streamlit Secrets 中的 gcp_service_account 與 sheet_id 正確。")
    st.stop()

if "edit_idx" not in st.session_state: st.session_state.edit_idx = None
if "cpv"      not in st.session_state: st.session_state.cpv      = 1.0

settings = st.session_state.settings
trades   = st.session_state.trades


# ════════════════════════════════════════════════════════
# SIDEBAR — lives outside all tabs (fixes layout bug)
# ════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="mtitle" style="font-size:1.05rem;">交易日誌</div>', unsafe_allow_html=True)
    st.markdown('<div class="msub">Prop Firm Journal</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<div class="sec">帳戶設置</div>', unsafe_allow_html=True)

    settings["account_name"]     = st.text_input("公司 / 帳號名稱",   value=settings.get("account_name","Topstep 50K"))
    settings["initial_balance"]  = st.number_input("初始資金 ($)",     value=float(settings.get("initial_balance",50000)),  min_value=0.0, step=1000.0, format="%.2f")
    settings["daily_loss_limit"] = st.number_input("每日虧損上限 ($)", value=float(settings.get("daily_loss_limit",1000)),  min_value=0.0, step=100.0,  format="%.2f")
    settings["max_drawdown"]     = st.number_input("總回撤上限 ($)",   value=float(settings.get("max_drawdown",2000)),      min_value=0.0, step=100.0,  format="%.2f")
    settings["profit_target"]    = st.number_input("利潤目標 ($)",     value=float(settings.get("profit_target",3000)),     min_value=0.0, step=500.0,  format="%.2f")

    st.markdown("---")
    st.markdown("""
<div style="font-size:0.72rem;color:#404558;line-height:1.9;">
<b style="color:#60646C;">各標的每點金額：</b><br>
MNQ = $2 ／ MES = $5<br>
NQ &nbsp;= $20 ／ ES &nbsp;= $50<br>
MGC = $10 ／ GC &nbsp;= $100<br><br>
選好標的後系統<b style="color:#7A8FA0;">自動換算</b>，不用自己填。
</div>
""", unsafe_allow_html=True)
    st.markdown("---")

    if st.button("儲存設置", use_container_width=True):
        st.session_state.settings = settings
        persist()
        st.success("設置已儲存 ✓")

    st.markdown(
        f'<div style="font-size:0.68rem;color:#404558;margin-top:0.4rem;">'
        f'{settings["account_name"]}　|　{len(trades)} 筆紀錄</div>',
        unsafe_allow_html=True
    )


# ─── Computed ────────────────────────────────────────────────────────────────
df = pd.DataFrame(trades) if trades else pd.DataFrame(
    columns=["date","symbol","direction","entry","exit","stop_usd","contracts",
             "point_value","pnl","r_multiple","psychology","notes","screenshot_b64"]
)
for col in ["pnl","r_multiple","entry","exit","stop_usd","contracts","point_value"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

total_pnl       = df["pnl"].sum() if not df.empty and "pnl" in df.columns else 0.0
current_balance = settings["initial_balance"] + total_pnl
profit_progress = min(max(total_pnl / settings["profit_target"], 0), 1) if settings["profit_target"] > 0 else 0
today_str       = date.today().isoformat()
today_pnl       = df[df["date"] == today_str]["pnl"].sum() if not df.empty and "date" in df.columns else 0.0
daily_buf       = settings["daily_loss_limit"] + today_pnl
max_dd_buf      = settings["max_drawdown"] - (settings["initial_balance"] - current_balance)


# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown('<div class="mtitle">交易紀錄</div>', unsafe_allow_html=True)
st.markdown('<div class="msub">Calm mind, disciplined execution.</div>', unsafe_allow_html=True)
st.markdown("---")


# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["  儀表板  ","  新增 / 編輯  ","  歷史清單  ","  數據分析  "])


# ══════════════════════════════════════════════════════
# TAB 1 — Dashboard
# ══════════════════════════════════════════════════════
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("帳戶淨值",  f"${current_balance:,.0f}", delta=f"{total_pnl:+,.2f}" if total_pnl else None)
    with c2: st.metric("累計損益",  f"${total_pnl:+,.0f}")
    with c3: st.metric("今日損益",  f"${today_pnl:+,.0f}")
    with c4:
        tc = len(df)
        wc = len(df[df["pnl"] > 0]) if not df.empty and "pnl" in df.columns else 0
        st.metric("勝率", f"{wc/tc*100:.0f}%" if tc else "—", delta=f"{wc}W / {tc-wc}L" if tc else None)

    st.markdown('<div class="sec">利潤目標進度</div>', unsafe_allow_html=True)
    cp, cpct = st.columns([5, 1])
    with cp: st.progress(profit_progress)
    with cpct:
        st.markdown(f'<div style="text-align:right;font-size:0.85rem;color:var(--accent);padding-top:0.3rem;">{profit_progress*100:.1f}%</div>', unsafe_allow_html=True)
    rem = max(settings["profit_target"] - total_pnl, 0)
    st.markdown(f'<div style="font-size:0.75rem;color:#404558;">目標 ${settings["profit_target"]:,.0f}　已達成 ${max(total_pnl,0):,.0f}　還差 <b style="color:var(--slate);">${rem:,.0f}</b></div>', unsafe_allow_html=True)

    st.markdown('<div class="sec">風險監控</div>', unsafe_allow_html=True)
    r1, r2 = st.columns(2)
    with r1:
        dp = daily_buf / settings["daily_loss_limit"] * 100 if settings["daily_loss_limit"] else 100
        if   daily_buf <= 0:                                st.markdown(f'<div class="rw">🚨 今日虧損超標！<br>已超出 ${abs(daily_buf):,.0f}，限額 ${settings["daily_loss_limit"]:,.0f}<br><small>請立即停止交易</small></div>', unsafe_allow_html=True)
        elif daily_buf < settings["daily_loss_limit"]*0.3: st.markdown(f'<div class="rw">⚠ 每日緩衝偏低<br>剩餘 ${daily_buf:,.0f}（剩 {dp:.0f}%）</div>', unsafe_allow_html=True)
        else:                                               st.markdown(f'<div class="rs">✓ 每日回撤安全<br>剩餘緩衝 ${daily_buf:,.0f}（剩 {dp:.0f}%）</div>', unsafe_allow_html=True)
    with r2:
        ddp = max_dd_buf / settings["max_drawdown"] * 100 if settings["max_drawdown"] else 100
        if   max_dd_buf <= 0:                              st.markdown(f'<div class="rw">🚨 總回撤超標！帳戶已爆<br>超出 ${abs(max_dd_buf):,.0f}</div>', unsafe_allow_html=True)
        elif max_dd_buf < settings["max_drawdown"]*0.3:   st.markdown(f'<div class="rw">⚠ 總回撤緩衝危險<br>剩餘 ${max_dd_buf:,.0f}（剩 {ddp:.0f}%）</div>', unsafe_allow_html=True)
        else:                                              st.markdown(f'<div class="rs">✓ 總回撤安全<br>剩餘緩衝 ${max_dd_buf:,.0f}（剩 {ddp:.0f}%）</div>', unsafe_allow_html=True)

    if not df.empty and "pnl" in df.columns and len(df) > 1:
        st.markdown('<div class="sec">近期權益走勢</div>', unsafe_allow_html=True)
        eq = df.sort_values("date").copy()
        eq["cum"] = settings["initial_balance"] + eq["pnl"].cumsum()
        fig_m = go.Figure()
        fig_m.add_trace(go.Scatter(
            x=list(range(len(eq))), y=eq["cum"].tolist(),
            mode="lines", line=dict(color="#7A8FA0", width=1.5),
            fill="tozeroy", fillcolor="rgba(122,143,160,0.07)"
        ))
        fig_m.add_hline(y=settings["initial_balance"], line_dash="dot", line_color="#2E3240", line_width=1)
        fig_m.update_layout(
            height=150, margin=dict(l=0,r=0,t=0,b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, tickfont=dict(size=8,color="#404558"), tickformat="$,.0f", zeroline=False),
            showlegend=False
        )
        st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})


# ══════════════════════════════════════════════════════
# TAB 2 — Add / Edit
# ══════════════════════════════════════════════════════
with tab2:
    edit_idx = st.session_state.edit_idx
    is_edit  = edit_idx is not None and 0 <= edit_idx < len(trades)

    if is_edit:
        ed = trades[edit_idx]
        def_date=date.fromisoformat(ed.get("date", today_str))
        def_sym=ed.get("symbol","MNQ"); def_dir=ed.get("direction","Long")
        def_entry=float(ed.get("entry",0)); def_exit=float(ed.get("exit",0))
        def_stop_usd=float(ed.get("stop_usd",0)); def_contracts=int(ed.get("contracts",1))
        def_psy=ed.get("psychology","冷靜執行"); def_notes=ed.get("notes","")
        def_cpv=float(ed.get("point_value",1)); existing_b64=ed.get("screenshot_b64","")
    else:
        def_date=date.today(); def_sym="MNQ"; def_dir="Long"
        def_entry=0.0; def_exit=0.0; def_stop_usd=0.0; def_contracts=1
        def_psy="冷靜執行"; def_notes=""; def_cpv=st.session_state.cpv; existing_b64=""

    if is_edit:
        st.markdown(
            f'<div class="edit-banner">✏️ 編輯模式　<b>第 {edit_idx+1} 筆</b>　'
            f'{ed.get("date","")}｜{ed.get("symbol","")} {ed.get("direction","")}<br>'
            f'修改後按「儲存修改」，或按取消返回。</div>',
            unsafe_allow_html=True
        )
        if st.button("✕  取消編輯"):
            st.session_state.edit_idx = None
            st.rerun()
    else:
        st.markdown('<div class="sec">新增交易紀錄</div>', unsafe_allow_html=True)

    col_s, col_d = st.columns([2, 1])
    with col_s:
        field("交易標的", "MNQ、MES、NQ、ES、MGC、GC")
        sel_sym = st.selectbox(
            "標的", SYMBOL_LIST,
            index=SYMBOL_LIST.index(def_sym) if def_sym in SYMBOL_LIST else 0,
            label_visibility="collapsed", key=f"sym_{is_edit}"
        )
    with col_d:
        field("交易方向", "Long 做多 / Short 做空")
        sel_dir = st.selectbox(
            "方向", ["Long","Short"],
            index=["Long","Short"].index(def_dir) if def_dir in ["Long","Short"] else 0,
            label_visibility="collapsed", key=f"dir_{is_edit}"
        )

    si = SYMBOL_DB[sel_sym]
    if sel_sym != "自訂":
        st.markdown(
            f'<div class="sym-card"><b style="color:var(--accent);">{si["name"]}</b><br>'
            f'最小跳動：{si["tick_size"]} 點 = ${si["tick_value"]}　｜　<b>每整點 = ${si["point_value"]}</b><br>'
            f'<span style="color:#404558;">{si["desc"]}</span></div>',
            unsafe_allow_html=True
        )
        cur_pv = si["point_value"]
    else:
        st.markdown(
            '<div class="sym-card" style="border-left-color:var(--red);">⚙ 自訂標的：請填入每點美金價值<br>'
            '<span style="color:#404558;">查合約規格表，1 整點移動等於多少美金</span></div>',
            unsafe_allow_html=True
        )
        field("每點美金價值", "NQ=20, ES=50, MNQ=2, MES=5")
        cur_pv = st.number_input(
            "自訂點值", value=def_cpv, min_value=0.01, step=0.5,
            format="%.2f", label_visibility="collapsed", key="cpv_in"
        )
        st.session_state.cpv = cur_pv

    st.markdown("")

    with st.form(f"form_{'edit' if is_edit else 'add'}", clear_on_submit=not is_edit):
        col_dt, _, __ = st.columns(3)
        with col_dt:
            field("交易日期")
            t_date = st.date_input("日期", value=def_date, label_visibility="collapsed")

        st.markdown("")
        col_en, col_ex = st.columns(2)
        with col_en:
            field("進場價格（Entry Price）", si.get("ex",""))
            t_entry = st.number_input("進場價", value=def_entry, format="%.2f", label_visibility="collapsed")
        with col_ex:
            field("出場價格（Exit Price）", si.get("ex",""))
            t_exit = st.number_input("出場價", value=def_exit, format="%.2f", label_visibility="collapsed")

        st.markdown("")
        col_su, col_co = st.columns(2)
        with col_su:
            field("停損金額（美金，單口）", "50 → 代表這筆你每口最多接受虧 $50")
            t_stop_usd = st.number_input(
                "停損金額", value=def_stop_usd, min_value=0.0,
                step=10.0, format="%.2f", label_visibility="collapsed"
            )
            if t_stop_usd > 0 and cur_pv > 0:
                st.markdown(
                    f'<div class="stop-hint">≈ {t_stop_usd/cur_pv:.2f} 點（每口）　|　每點 ${cur_pv}　|　自動換算 R</div>',
                    unsafe_allow_html=True
                )
        with col_co:
            field("口數", "1 口、2 口")
            t_contracts = st.number_input("口數", value=def_contracts, min_value=1, step=1, label_visibility="collapsed")

        st.markdown("")
        col_p, col_n = st.columns([1, 2])
        with col_p:
            field("心理狀態", "冷靜執行 = 最好")
            t_psy = st.selectbox(
                "心理", PSY_LIST,
                index=PSY_LIST.index(def_psy) if def_psy in PSY_LIST else 0,
                label_visibility="collapsed"
            )
        with col_n:
            field("備註", "突破前高進場，止盈阻力區")
            t_notes = st.text_input(
                "備註", value=def_notes,
                placeholder="簡短記錄你的想法…", label_visibility="collapsed"
            )

        st.markdown("")
        field("交易截圖（選填）", "PNG / JPG / WEBP")
        if existing_b64:
            st.markdown('<div class="shot-card">📷 此筆已有截圖　（上傳新圖會覆蓋）</div>', unsafe_allow_html=True)
        t_upload = st.file_uploader(
            "截圖", type=["png","jpg","jpeg","webp"],
            label_visibility="collapsed", key=f"up_{edit_idx}_{is_edit}"
        )

        if t_entry > 0 and t_exit > 0:
            prev_pnl   = calc_pnl(sel_sym, sel_dir, t_entry, t_exit, t_contracts, cur_pv)
            raw_pts    = (t_exit-t_entry) if sel_dir=="Long" else (t_entry-t_exit)
            tr_risk    = t_stop_usd * t_contracts
            r_prev     = prev_pnl / tr_risk if tr_risk > 0 else 0
            pc         = "#528060" if prev_pnl >= 0 else "#C05050"
            r_str      = f'　｜　預估 R：<b>{r_prev:+.2f}R</b>' if tr_risk > 0 else ""
            st.markdown(
                f'<div class="ibox" style="border-left:3px solid {pc};">'
                f'📊 預估損益：<b style="color:{pc};">${prev_pnl:+,.2f}</b>　｜　'
                f'移動：{raw_pts:+.2f} 點　｜　口數 {t_contracts}{r_str}</div>',
                unsafe_allow_html=True
            )

        submitted = st.form_submit_button(
            "💾  儲存修改" if is_edit else "✓  記錄此筆交易",
            use_container_width=True
        )

    if submitted:
        pnl     = calc_pnl(sel_sym, sel_dir, t_entry, t_exit, t_contracts, cur_pv)
        tr_risk = t_stop_usd * t_contracts
        r_m     = pnl / tr_risk if tr_risk > 0 else 0.0
        new_b64 = img_to_b64(t_upload) if t_upload else existing_b64

        record = {
            "date":           t_date.isoformat(),
            "symbol":         sel_sym,
            "direction":      sel_dir,
            "entry":          t_entry,
            "exit":           t_exit,
            "stop_usd":       round(t_stop_usd, 2),
            "contracts":      t_contracts,
            "point_value":    cur_pv,
            "pnl":            round(pnl, 2),
            "r_multiple":     round(r_m, 2),
            "psychology":     t_psy,
            "notes":          t_notes,
            "screenshot_b64": new_b64,
        }

        if is_edit:
            trades[edit_idx] = record
            st.session_state.edit_idx = None
        else:
            trades.append(record)

        st.session_state.trades = trades
        persist()

        pc2  = "#528060" if pnl >= 0 else "#C05050"
        verb = "已修改" if is_edit else "已記錄"
        shot = "　｜　📷 截圖已儲存" if new_b64 else ""
        st.markdown(
            f'<div class="ibox" style="border-left:3px solid {pc2};">'
            f'✓ {verb}　<b>{sel_sym}</b> {sel_dir} × {t_contracts} 口　'
            f'損益：<b style="color:{pc2};">${pnl:+,.2f}</b>　R：<b>{r_m:+.2f}R</b>{shot}</div>',
            unsafe_allow_html=True
        )
        st.rerun()


# ══════════════════════════════════════════════════════
# TAB 3 — History
# ══════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="sec">交易明細</div>', unsafe_allow_html=True)

    if df.empty:
        st.markdown('<div class="ibox" style="text-align:center;color:#404558;padding:2.5rem;">尚無交易紀錄</div>', unsafe_allow_html=True)
    else:
        display_cols = [
            ("date","日期"),("symbol","標的"),("direction","方向"),
            ("entry","進場價"),("exit","出場價"),("stop_usd","停損金額 ($)"),
            ("contracts","口數"),("pnl","損益 ($)"),("r_multiple","R 乘數"),
            ("psychology","心理狀態"),("notes","備註"),
        ]
        show = df.copy().sort_values("date", ascending=False).reset_index(drop=True)
        if "pnl"        in show.columns: show["pnl"]        = show["pnl"].apply(lambda x: f"+${x:,.2f}" if x>=0 else f"-${abs(x):,.2f}")
        if "r_multiple" in show.columns: show["r_multiple"] = show["r_multiple"].apply(lambda x: f"{x:+.2f}R")
        if "stop_usd"   in show.columns: show["stop_usd"]   = show["stop_usd"].apply(lambda x: f"${float(x):,.2f}" if float(x)>0 else "—")
        avail = [c for c,_ in display_cols if c in show.columns]
        st.dataframe(show[avail].rename(columns=dict(display_cols)), use_container_width=True, hide_index=True)

        st.markdown('<div class="sec">逐筆查看 ／ 截圖</div>', unsafe_allow_html=True)
        sorted_trades = sorted(enumerate(trades), key=lambda x: x[1].get("date",""), reverse=True)
        label_list, orig_indices = [], []
        for orig_i, t in sorted_trades:
            pv   = float(t.get("pnl",0))
            ps   = f"+${pv:,.0f}" if pv >= 0 else f"-${abs(pv):,.0f}"
            icon = "📷" if t.get("screenshot_b64","") else "  "
            label_list.append(f"{icon} #{orig_i+1}　{t.get('date','')}　{t.get('symbol','')} {t.get('direction','')}　{ps}")
            orig_indices.append(orig_i)

        sel_label = st.selectbox("選擇紀錄", label_list, label_visibility="collapsed")
        sel_orig  = orig_indices[label_list.index(sel_label)]
        sel_trade = trades[sel_orig]

        pnl_v   = float(sel_trade.get("pnl",0))
        pnl_col = "#528060" if pnl_v >= 0 else "#C05050"
        r_v     = float(sel_trade.get("r_multiple",0))
        su_v    = float(sel_trade.get("stop_usd",0))
        pv_v    = float(sel_trade.get("point_value",1))
        stop_pts_disp = f"{su_v/pv_v:.2f} 點" if su_v > 0 and pv_v > 0 else "—"
        cls     = "trade-card-win" if pnl_v >= 0 else "trade-card-loss"

        st.markdown(
            f'<div class="trade-card {cls}">'
            f'<b style="color:var(--accent);">{sel_trade.get("symbol","")} {sel_trade.get("direction","")}</b>　'
            f'{sel_trade.get("date","")}　× {sel_trade.get("contracts",1)} 口<br>'
            f'進場：{sel_trade.get("entry","")}　→　出場：{sel_trade.get("exit","")}<br>'
            f'停損：<b>${su_v:,.2f}</b>（≈ {stop_pts_disp}）　｜　'
            f'損益：<b style="color:{pnl_col};">${pnl_v:+,.2f}</b>　｜　R：<b>{r_v:+.2f}R</b><br>'
            f'心理：{sel_trade.get("psychology","")}　｜　備註：{sel_trade.get("notes","—")}'
            f'</div>',
            unsafe_allow_html=True
        )

        b64_str = sel_trade.get("screenshot_b64","")
        if b64_str:
            with st.expander("📷  查看交易截圖", expanded=False):
                try:
                    mime = b64_mime(b64_str)
                    st.markdown(
                        f'<div class="lb-wrap"><img src="data:image/{mime};base64,{b64_str}" alt="screenshot"/></div>',
                        unsafe_allow_html=True
                    )
                    st.download_button(
                        "⬇  下載截圖", data=b64_to_bytes(b64_str),
                        file_name=f"trade_{sel_orig+1}.{mime}", mime=f"image/{mime}"
                    )
                except Exception as e:
                    st.warning(f"無法載入截圖：{e}")
        else:
            st.markdown('<div class="shot-card" style="border-left-color:var(--muted);">此筆尚未上傳截圖。進入「編輯」後可上傳。</div>', unsafe_allow_html=True)

        st.markdown("")
        ec, dc, _ = st.columns([1, 1, 3])
        with ec:
            if st.button("✏️  編輯此筆", use_container_width=True):
                st.session_state.edit_idx = sel_orig
                st.rerun()
        with dc:
            if st.button("🗑  刪除此筆", use_container_width=True):
                trades.pop(sel_orig)
                st.session_state.trades   = trades
                st.session_state.edit_idx = None
                persist()
                st.rerun()

        st.markdown('<div class="sec">統計摘要</div>', unsafe_allow_html=True)
        raw_df = pd.DataFrame(trades)
        for col in ["pnl","r_multiple"]:
            raw_df[col] = pd.to_numeric(raw_df[col], errors="coerce").fillna(0)
        wins   = raw_df[raw_df["pnl"] > 0]; losses = raw_df[raw_df["pnl"] <= 0]
        aw = wins["pnl"].mean()   if len(wins)   else 0
        al = losses["pnl"].mean() if len(losses) else 0
        ar = raw_df["r_multiple"].mean() if len(raw_df) else 0
        pf = abs(wins["pnl"].sum()/losses["pnl"].sum()) if len(losses) and losses["pnl"].sum()!=0 else 9.99
        c1,c2,c3,c4,c5 = st.columns(5)
        with c1: st.metric("平均盈利", f"${aw:,.0f}")
        with c2: st.metric("平均虧損", f"${al:,.0f}")
        with c3: st.metric("平均 R",   f"{ar:+.2f}")
        with c4: st.metric("獲利因子", f"{min(pf,9.99):.2f}")
        with c5: st.metric("最佳單筆", f"${raw_df['pnl'].max():,.0f}")

        st.markdown('<div class="sec">匯出給 Claude 覆盤</div>', unsafe_allow_html=True)
        exp = raw_df.copy()
        for dc_ in ["point_value","screenshot_b64"]:
            if dc_ in exp.columns: exp = exp.drop(columns=[dc_])
        for k,v in settings.items(): exp[f"[帳戶]{k}"] = v
        csv_b = exp.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "⬇  匯出 CSV（含帳戶設置）", data=csv_b,
            file_name=f"trading_journal_{date.today().isoformat()}.csv",
            mime="text/csv", use_container_width=True
        )
        st.markdown('<div style="font-size:0.72rem;color:#404558;margin-top:0.3rem;">下載後直接上傳給 Claude 做深度覆盤分析 📊</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# TAB 4 — Analytics
# ══════════════════════════════════════════════════════
with tab4:
    if df.empty or len(df) < 2:
        st.markdown('<div class="ibox" style="text-align:center;color:#404558;padding:2.5rem;">需要至少 2 筆紀錄才能顯示分析圖表</div>', unsafe_allow_html=True)
    else:
        raw = pd.DataFrame(trades).copy()
        for col in ["pnl","r_multiple"]:
            raw[col] = pd.to_numeric(raw[col], errors="coerce").fillna(0)
        raw = raw.sort_values("date").reset_index(drop=True)
        raw["cum"]       = settings["initial_balance"] + raw["pnl"].cumsum()
        raw["trade_num"] = range(1, len(raw)+1)
        peak = raw["cum"].cummax()

        st.markdown('<div class="sec">權益曲線 Equity Curve</div>', unsafe_allow_html=True)
        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(x=raw["trade_num"].tolist(), y=raw["cum"].tolist(), fill=None, mode="lines", line=dict(color="rgba(0,0,0,0)"), showlegend=False))
        fig_eq.add_trace(go.Scatter(x=raw["trade_num"].tolist(), y=peak.tolist(), fill="tonexty", fillcolor="rgba(192,80,80,0.12)", mode="none", name="回撤區間"))
        fig_eq.add_trace(go.Scatter(x=raw["trade_num"].tolist(), y=raw["cum"].tolist(), mode="lines+markers", line=dict(color="#7A8FA0",width=2), marker=dict(size=4,color="#8FAABF"), name="帳戶淨值"))
        fig_eq.add_hline(y=settings["initial_balance"], line_dash="dot", line_color="#404558", line_width=1, annotation_text="初始資金", annotation_position="right", annotation_font_color="#60646C")
        fig_eq.add_hline(y=settings["initial_balance"]+settings["profit_target"], line_dash="dash", line_color="#528060", line_width=1, annotation_text="利潤目標", annotation_position="right", annotation_font_color="#528060")
        fig_eq.add_hline(y=settings["initial_balance"]-settings["max_drawdown"], line_dash="dash", line_color="#C05050", line_width=1, annotation_text="最大回撤", annotation_position="right", annotation_font_color="#C05050")
        fig_eq.update_layout(height=360, margin=dict(l=10,r=80,t=10,b=30), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#22252A",
                              font=dict(family="Noto Sans TC",size=9,color="#60646C"),
                              xaxis=dict(title="交易筆數",gridcolor="#2A2E37",zeroline=False),
                              yaxis=dict(title="帳戶淨值 ($)",gridcolor="#2A2E37",zeroline=False,tickformat="$,.0f"),
                              legend=dict(orientation="h",y=-0.2,x=0,font=dict(size=9)), hovermode="x unified")
        st.plotly_chart(fig_eq, use_container_width=True, config={"displayModeBar":False})

        cl, cr = st.columns(2)
        with cl:
            st.markdown('<div class="sec">心理狀態分佈</div>', unsafe_allow_html=True)
            pc = raw["psychology"].value_counts().reset_index(); pc.columns = ["label","count"]
            palette = ["#7A8FA0","#8FAABF","#6A7F90","#528060","#A0B5C5","#C05050","#B07070"]
            fig_ps = go.Figure(go.Bar(x=pc["count"].tolist(), y=pc["label"].tolist(), orientation="h", marker_color=palette[:len(pc)], text=pc["count"].tolist(), textposition="inside", textfont=dict(color="#1A1C1E",size=10)))
            fig_ps.update_layout(height=280, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Noto Sans TC",size=10,color="#60646C"), xaxis=dict(showgrid=False,showticklabels=False,zeroline=False), yaxis=dict(showgrid=False,zeroline=False), showlegend=False)
            st.plotly_chart(fig_ps, use_container_width=True, config={"displayModeBar":False})
        with cr:
            st.markdown('<div class="sec">R 乘數分佈</div>', unsafe_allow_html=True)
            rv = raw["r_multiple"].tolist(); rc = ["#528060" if r>=0 else "#C05050" for r in rv]
            fig_r = go.Figure(go.Bar(x=list(range(1,len(rv)+1)), y=rv, marker_color=rc, opacity=0.85))
            fig_r.add_hline(y=0, line_color="#404558", line_width=1)
            fig_r.update_layout(height=280, margin=dict(l=10,r=10,t=10,b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Noto Sans TC",size=10,color="#60646C"), xaxis=dict(title="交易筆數",showgrid=False,zeroline=False), yaxis=dict(title="R 乘數",showgrid=True,gridcolor="#2A2E37",zeroline=False), showlegend=False)
            st.plotly_chart(fig_r, use_container_width=True, config={"displayModeBar":False})

        st.markdown('<div class="sec">各心理狀態的平均損益</div>', unsafe_allow_html=True)
        ppnl = raw.groupby("psychology").agg(avg=("pnl","mean")).reset_index().sort_values("avg")
        bc   = ["#528060" if v>=0 else "#C05050" for v in ppnl["avg"]]
        fig_pp = go.Figure(go.Bar(x=ppnl["psychology"].tolist(), y=ppnl["avg"].tolist(), marker_color=bc, opacity=0.85, text=[f"${v:,.0f}" for v in ppnl["avg"]], textposition="outside", textfont=dict(size=9,color="#60646C")))
        fig_pp.add_hline(y=0, line_color="#404558", line_width=1)
        fig_pp.update_layout(height=250, margin=dict(l=10,r=10,t=20,b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Noto Sans TC",size=10,color="#60646C"), xaxis=dict(showgrid=False,zeroline=False), yaxis=dict(showgrid=True,gridcolor="#2A2E37",zeroline=False,tickformat="$,.0f"), showlegend=False)
        st.plotly_chart(fig_pp, use_container_width=True, config={"displayModeBar":False})

# ─── Footer ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;font-size:0.62rem;color:#2E3240;'
    'letter-spacing:0.18em;padding-bottom:0.8rem;">'
    'PROP FIRM TRADING JOURNAL　｜　冷靜執行，紀律為本</div>',
    unsafe_allow_html=True
)
