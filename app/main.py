import os, time, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from dotenv import load_dotenv

# === 路徑設定：從 app/ 回上一層就是專案根目錄 ===
APP_DIR  = os.path.dirname(__file__)
BASE_DIR = os.path.dirname(APP_DIR)

# 讀根目錄的 .env
load_dotenv(os.path.join(BASE_DIR, ".env"))

# 取環境變數
API_KEY = os.getenv("ALPHAVANTAGE_KEY")
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "TSLA,NVDA").split(",") if s.strip()]
if not API_KEY:
    raise SystemExit("缺少 ALPHAVANTAGE_KEY，請在專案根目錄建立 .env 並設定。")

# === 輸出資料夾：一律放在 app/data/ ===
OUT_DIR   = os.path.join(APP_DIR, "data")
PLOTS_DIR = os.path.join(OUT_DIR, "plots")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)

# === API 參數 ===
BASE_URL   = "https://www.alphavantage.co/query"
OUTPUTSIZE = "compact"   # 新手先抓近 100 筆；要完整歷史改 "full"
SLEEP_SEC  = 15          # 避免速率限制

def fetch_daily(symbol, adjusted=True):
    """先試調整後日線；若遇到 premium，自動 fallback 到未調整（日線）。"""
    fn = "TIME_SERIES_DAILY_ADJUSTED" if adjusted else "TIME_SERIES_DAILY"
    params = {"function": fn, "symbol": symbol, "outputsize": OUTPUTSIZE,
              "datatype": "json", "apikey": API_KEY}
    r = requests.get(BASE_URL, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()

    # 常見回覆處理
    if "Note" in j:
        raise RuntimeError(f"[{symbol}] 觸發額度/速率限制：{j['Note']}")
    if "Information" in j:
        if adjusted:  # ADJUSTED 被視為 premium → 改抓 DAILY
            return fetch_daily(symbol, adjusted=False)
        else:
            raise RuntimeError(f"[{symbol}] Premium 端點：{j['Information']}")

    ts = j.get("Time Series (Daily)")
    if not ts:
        raise RuntimeError(f"[{symbol}] 無資料回傳：{j}")

    # 轉成 DataFrame
    df = pd.DataFrame(ts).T.rename(columns={
        "1. open":"open","2. high":"high","3. low":"low",
        "4. close":"close","5. adjusted close":"adj_close",
        "6. volume":"volume","7. dividend amount":"dividend",
        "8. split coefficient":"split",
    }).astype(float, errors="ignore")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df, ("ADJUSTED" if adjusted else "DAILY")

def plot_ma(sym, g: pd.DataFrame):
    """畫收盤價 + MA20/MA50 到 app/data/plots/"""
    g = g.copy()
    g["ma20"] = g["close"].rolling(20).mean()
    g["ma50"] = g["close"].rolling(50).mean()
    fig = plt.figure(figsize=(9,4.5))
    plt.plot(g.index, g["close"], label=f"{sym} close")
    plt.plot(g.index, g["ma20"],  label="MA20")
    plt.plot(g.index, g["ma50"],  label="MA50")
    plt.title(f"{sym} — Close + MA20/MA50")
    plt.xlabel("date"); plt.ylabel("price"); plt.legend()
    out_png = os.path.join(PLOTS_DIR, f"{sym}_ma.png")
    plt.tight_layout(); plt.savefig(out_png, dpi=150); plt.close(fig)
    return out_png

def main():
    all_rows = []
    for i, sym in enumerate(SYMBOLS, 1):
        try:
            print(f"({i}/{len(SYMBOLS)}) 抓取 {sym} …")
            df, kind = fetch_daily(sym, adjusted=True)
            # 個別存檔：app/data/TSLA_daily_daily.csv（或 _adjusted.csv）
            csv_path = os.path.join(OUT_DIR, f"{sym}_daily_{kind.lower()}.csv")
            df.to_csv(csv_path, index_label="date", encoding="utf-8")
            print(f"→ 存檔：{csv_path}（{len(df)} 列）")

            # 畫圖
            png = plot_ma(sym, df)
            print(f"🖼 圖：{png}")

            # 合併用
            tmp = df.reset_index().rename(columns={"index":"date"})
            tmp["symbol"] = sym
            tmp["source"] = kind
            all_rows.append(tmp)

        except Exception as e:
            print(f"× 失敗 {sym}：{e}")
        time.sleep(SLEEP_SEC)

    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True).sort_values(["date","symbol"])
        out_comb = os.path.join(OUT_DIR, "all_stocks_daily_combined.csv")
        combined.to_csv(out_comb, index=False, encoding="utf-8")
        print(f"✅ 合併檔已輸出：{out_comb}")

if __name__ == "__main__":
    main()

