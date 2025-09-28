# app/dashboard.py
# -*- coding: utf-8 -*-
import os
import pandas as pd
import streamlit as st

APP_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(APP_DIR, "data")
COMBINED = os.path.join(DATA_DIR, "all_stocks_daily_combined.csv")

st.set_page_config(page_title="Stocks Dashboard", layout="wide")
st.title("📈 美股日線儀表板")

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """欄名一律小寫；補上常見欄位（不存在就用 NA/預設）"""
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    need_cols = ["date","open","high","low","close","volume","symbol","source"]
    for c in need_cols:
        if c not in df.columns:
            df[c] = pd.NA
    # 日期轉型
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def load_data():
    # 先讀合併檔
    if os.path.exists(COMBINED):
        df = pd.read_csv(COMBINED)
        df = normalize_columns(df)
        df = df.sort_values(["symbol","date"])
        return df

    # 否則從個別 CSV 合併
    parts = []
    if not os.path.isdir(DATA_DIR):
        return None
    for f in os.listdir(DATA_DIR):
        if f.endswith(".csv") and f != os.path.basename(COMBINED):
            p = os.path.join(DATA_DIR, f)
            tmp = pd.read_csv(p)
            tmp = normalize_columns(tmp)
            # 沒有 symbol 的話從檔名猜
            if tmp["symbol"].isna().all():
                tmp["symbol"] = f.split("_")[0]
            parts.append(tmp)
    if not parts:
        return None
    df = pd.concat(parts, ignore_index=True)
    df = df.sort_values(["symbol","date"])
    return df

df = load_data()
if df is None or df.empty:
    st.warning("找不到資料。請先執行：`python app\\main.py` 產生 CSV。")
    st.stop()

# 側邊欄：選股票/日期
with st.sidebar:
    st.header("⚙️ 設定")
    symbols = sorted(df["symbol"].dropna().unique().tolist())
    pick = st.multiselect("選擇標的", symbols, default=symbols)
    dmin = pd.to_datetime(df["date"]).min().date()
    dmax = pd.to_datetime(df["date"]).max().date()
    drange = st.date_input("日期範圍", (dmin, dmax), min_value=dmin, max_value=dmax)
    if isinstance(drange, tuple):
        start, end = pd.to_datetime(drange[0]), pd.to_datetime(drange[1])
    else:
        start, end = pd.to_datetime(drange), pd.to_datetime(drange)

# 篩選
df["date"] = pd.to_datetime(df["date"], errors="coerce")
view = df[(df["symbol"].isin(pick)) & (df["date"].between(start, end))].copy()

# 主要區塊：表格 + 圖
c1, c2 = st.columns([2, 3], gap="large")

with c1:
    st.subheader("最新收盤價")
    latest = view.sort_values("date").groupby("symbol").tail(1).copy()
    # 只取存在的欄位，避免 KeyError
    cols = [c for c in ["symbol","date","close","volume"] if c in latest.columns]
    st.dataframe(latest[cols].sort_values("symbol"), use_container_width=True)

with c2:
    st.subheader("收盤價走勢")
    pivot = (view.pivot_table(index="date", columns="symbol", values="close", aggfunc="last")
                  .sort_index())
    st.line_chart(pivot, height=380)

st.divider()
st.subheader("原始明細")
show_cols = [c for c in ["symbol","date","open","high","low","close","volume","source"] if c in view.columns]
st.dataframe(view[show_cols].sort_values(["symbol","date"], ascending=[True, False]),
             use_container_width=True, height=360)