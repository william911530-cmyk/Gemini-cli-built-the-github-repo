# -*- coding: utf-8 -*-
import sys, os, requests, json, time, math
import pandas as pd
import yfinance as yf
import urllib3
import warnings

warnings.filterwarnings('ignore')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if sys.platform.startswith('win'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# ==========================================
# 🌟 0. 你的前端「必抓保護名單」 (確保熱門妖股絕對不漏接)
# ==========================================
HOT_STOCKS = [
    "2330.TW", "2317.TW", "2454.TW", "2382.TW", "3231.TW", 
    "AAPL", "NVDA", "TSLA", "MSFT", "AMD", "GOOGL", "AMZN", "META", 
    "ARM", "PLTR", "BE", "CRWD", "DDOG", "SNOW", "MDB", "NET", "ZS", 
    "NOW", "SMCI", "VRT", "CELH", "APP", "PATH", "SYM", "AI", "SOFI", 
    "HOOD", "COIN", "MSTR", "UBER"
]

# ==========================================
# 📋 1. 動態獲取全市場股票代號清單
# ==========================================
def get_tw_stock_list():
    print("📋 [1/2] 正在動態獲取全台股清單...")
    tw_tickers = []
    try:
        res = requests.get("https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", verify=False)
        df = pd.read_html(res.text)[0]
        for val in df[0].dropna():
            if ' ' in str(val):
                code = val.split(' ')[0]
                if code.isdigit() and len(code) == 4: tw_tickers.append(f"{code}.TW")
        
        res = requests.get("https://isin.twse.com.tw/isin/C_public.jsp?strMode=4", verify=False)
        df = pd.read_html(res.text)[0]
        for val in df[0].dropna():
            if ' ' in str(val):
                code = val.split(' ')[0]
                if code.isdigit() and len(code) == 4: tw_tickers.append(f"{code}.TWO")
    except Exception as e:
        print(f"⚠️ 台股清單獲取失敗: {e}")
    return tw_tickers

def get_us_stock_list():
    print("📋 [2/2] 正在動態獲取美股 S&P 500 清單...")
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        df = pd.read_html(url)[0]
        us_tickers = df['Symbol'].tolist()
        return [ticker.replace('.', '-') for ticker in us_tickers]
    except Exception as e:
        print(f"⚠️ 美股清單獲取失敗: {e}")
        return []

# ==========================================
# 📊 2. 100% 保留你原版的技術指標與清洗器
# ==========================================
def calculate_technical_indicators(df):
    if df.empty or len(df) < 30: return df
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp1 - exp2
    df['MACD_Signal'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['DIF'] - df['MACD_Signal']
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    df['RSV'] = 100 * (df['Close'] - low_min) / (high_max - low_min)
    df['K'], df['D'] = 50.0, 50.0
    for i in range(1, len(df)):
        if pd.isna(df['RSV'].iloc[i]): continue
        df.loc[df.index[i], 'K'] = df['K'].iloc[i-1] * (2/3) + df['RSV'].iloc[i] * (1/3)
        df.loc[df.index[i], 'D'] = df['D'].iloc[i-1] * (2/3) + df['K'].iloc[i] * (1/3)
    return df

def clean_val(val, is_pct=False, multiplier=1):
    if val is None or (isinstance(val, float) and math.isnan(val)) or val == 'N/A': return 'N/A'
    if is_pct and isinstance(val, (int, float)): return f"{val * multiplier:.2f}%"
    if isinstance(val, float): return round(val, 2)
    return val

def safe_pct(val, normal_max=1.0):
    if val is None or (isinstance(val, float) and math.isnan(val)) or val == 'N/A': return 'N/A'
    if isinstance(val, (int, float)):
        if abs(val) > normal_max: return f"{val:.2f}%"
        else: return f"{val * 100:.2f}%"
    return val

# ==========================================
# 🚀 3. 主執行迴圈
# ==========================================
def main():
    print("🚀 啟動全市場（台股 + 美股大盤 + 焦點妖股）量化特徵管線...")
    
    # 合併所有名單並去重複 (Set 可以去掉重複的代號)
    all_market_tickers = list(set(HOT_STOCKS + get_tw_stock_list() + get_us_stock_list()))
    print(f"📥 正在執行大批次下載歷史 K 線數據 (總計 {len(all_market_tickers)} 檔)...")
    
    # 批次下載價格，這步極快且不易被封
    raw_hist = yf.download(all_market_tickers, period="6mo", group_by='ticker', threads=True, progress=False)
    
    shards = {}
    success_count = 0

    for i, ticker_symbol in enumerate(all_market_tickers):
        # 防封鎖機制：每查 50 檔股票，暫停 1 秒讓 Yahoo 喘口氣
        if i > 0 and i % 50 == 0:
            time.sleep(1)

        try:
            # 1. 處理歷史價格與技術指標
            if len(all_market_tickers) == 1: df = raw_hist.copy()
            else:
                if ticker_symbol not in raw_hist.columns.levels[0]: continue
                df = raw_hist[ticker_symbol].dropna(subset=['Close'])
                
            if df.empty or len(df) < 30: continue
            
            df = calculate_technical_indicators(df)
            latest = df.iloc[-1]
            
            # 2. 獲取基本面資料 (加上 Try-Catch，避免 Yahoo 封鎖財報時導致整個迴圈崩潰)
            info = {}
            try:
                tk = yf.Ticker(ticker_symbol)
                # 使用 fast_info 確保價格絕對抓得到，info 則隨緣 (因爲抓幾千檔財報極易被封鎖)
                current_price = tk.fast_info.get('lastPrice', None)
                info = tk.info 
            except:
                current_price = None

            if current_price is None:
                current_price = round(latest['Close'], 2)
                
            # 3. 完整對齊前端所需的資料欄位
            metrics = {
                "price": clean_val(current_price),
                "change_52w": safe_pct(info.get('52WeekChange'), normal_max=5.0),
                "beta": clean_val(info.get('beta')),
                "trailing_pe": clean_val(info.get('trailingPE')),
                "peg": clean_val(info.get('pegRatio')),
                "dividend_yield": safe_pct(info.get('dividendYield'), normal_max=1.0),
                "revenue_growth": safe_pct(info.get('revenueGrowth'), normal_max=5.0),
                "roe": safe_pct(info.get('returnOnEquity'), normal_max=5.0),
                "debt_to_equity": clean_val(info.get('debtToEquity')),
                "ma5": clean_val(latest.get('MA5')),
                "ma20": clean_val(latest.get('MA20')),
                "ma60": clean_val(latest.get('MA60')),
                "rsi": clean_val(latest.get('RSI')),
                "k": clean_val(latest.get('K')),
                "d": clean_val(latest.get('D')),
                "dif": clean_val(latest.get('DIF')),
                "macd_hist": clean_val(latest.get('MACD_Hist'))
            }
            
            # 4. 資料分片路由計算
            if ".TW" in ticker_symbol or ".TWO" in ticker_symbol:
                shard_key = ticker_symbol[:2] # 台股分片
            else:
                shard_key = "US" # 美股全部塞進 US 分片
                
            if shard_key not in shards: shards[shard_key] = {}
            shards[shard_key][ticker_symbol] = metrics
            success_count += 1
            
            # 每處理完 500 檔印一次進度，讓 GitHub Actions 不會因為太安靜而超時中斷
            if success_count % 500 == 0:
                print(f"✅ 已成功計算 {success_count} 檔股票...")
                
        except Exception as e:
            continue # 單一股票錯誤直接跳過，絕不中斷整體流程

    # 5. 寫入分片資料夾
    os.makedirs('database', exist_ok=True)
    for key, data in shards.items():
        filename = f"database/data_{key}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
    print(f"🎉 任務完成！共成功更新 {success_count} 檔股票，分片已儲存於 database 資料夾。")

if __name__ == "__main__":
    main()
