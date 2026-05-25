import yfinance as yf
import pandas as pd
import json
import os
import math

# 🌟 100% 保留你原版的技術指標運算邏輯
def calculate_technical_indicators(df):
    if df.empty or len(df) < 30:
        return df
    
    # MA (Moving Average)
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp1 - exp2
    df['MACD_Signal'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['DIF'] - df['MACD_Signal']
    
    # KD
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    df['RSV'] = 100 * (df['Close'] - low_min) / (high_max - low_min)
    
    df['K'] = 50.0
    df['D'] = 50.0
    for i in range(1, len(df)):
        if pd.isna(df['RSV'].iloc[i]):
            continue
        df.loc[df.index[i], 'K'] = df['K'].iloc[i-1] * (2/3) + df['RSV'].iloc[i] * (1/3)
        df.loc[df.index[i], 'D'] = df['D'].iloc[i-1] * (2/3) + df['K'].iloc[i] * (1/3)
        
    return df

def clean_val(val, is_pct=False, multiplier=1):
    """資料防呆清洗器"""
    if val is None or (isinstance(val, float) and math.isnan(val)) or val == 'N/A':
        return 'N/A'
    if is_pct and isinstance(val, (int, float)):
        return f"{val * multiplier:.2f}%"
    if isinstance(val, float):
        return round(val, 2)
    return val

def safe_pct(val, normal_max=1.0):
    """當 val > normal_max 時，視為已經是百分比數值，不乘 100"""
    if val is None or (isinstance(val, float) and math.isnan(val)) or val == 'N/A':
        return 'N/A'
    if isinstance(val, (int, float)):
        if abs(val) > normal_max:    # 可能已為百分比格式
            return f"{val:.2f}%"
        else:
            return f"{val * 100:.2f}%"
    return val

def main():
    print("🚀 啟動全市場（台股 + 美股）量化特徵管線...")
    
    # 🌟 在這裡隨意加入你想監測的所有台股與美股代號
    market_tickers = [
        "2330.TW", "2317.TW", "2454.TW", "2382.TW", "3231.TW", 
        "AAPL", "NVDA", "TSLA", "MSFT", "AMD", "GOOGL", "AMZN", "META","NVDA", "ARM", "PLTR", "BE", "CRWD", "DDOG", "AMD", "SNOW", "MDB", "NET", "ZS", "NOW", "TSLA", "SMCI", "VRT", "CELH", "APP", "PATH", "SYM", "AI", "SOFI", "HOOD", "COIN", "MSTR", "UBER",
             "TSM", "AVGO", "MU", "META", "GOOGL", "AMZN", "WDC", "STX", "DELL", "ASML", "QCOM", "AMAT", "LRCX", "KLAC", "MRVL", "ANET", "SNPS", "CDNS", "ORCL", "TXN", "ADI", "NXPI", "ON", "ACN", "IBM",
             "WDAY", "DOCN", "U", "RBLX", "ZM", "PINS", "ETSY", "SHOP", "SQ", "ROKU", "TEAM", "GTLB", "ESTC", "DT", "DASH", "LYFT", "SE", "MELI", "CHWY", "CVNA", "AFRM", "UPST", "TOST", "BILL", "ENPH",
             "CSCO", "INTC", "T", "VZ", "BABA", "JD", "BIDU", "NTAP", "PSTG", "JNPR", "FFIV", "GLW", "SWKS", "QRVO", "MCHP", "TER", "ENTG", "LSCC", "WOLF", "TMUS", "ZTS", "CTRA", "TPR", "NEE", "DUK"
    ]
    
    print(f"📥 正在執行大批次下載歷史K線數據 (總計 {len(market_tickers)} 檔)...")
    # 平行抓取歷史價格
    raw_hist = yf.download(market_tickers, period="1y", group_by='ticker', progress=True)
    
    shards = {}

    for ticker_symbol in market_tickers:
        print(f"⚙️ 正在處理特徵工程: {ticker_symbol}")
        try:
            # 1. 處理歷史價格與技術指標
            if len(market_tickers) == 1:
                df = raw_hist.copy()
            else:
                if ticker_symbol not in raw_hist.columns.levels[0]: continue
                df = raw_hist[ticker_symbol].dropna(subset=['Close'])
                
            if df.empty or len(df) < 30: continue
            
            df = calculate_technical_indicators(df)
            latest = df.iloc[-1]
            
            # 2. 獲取基本面資料
            tk = yf.Ticker(ticker_symbol)
            info = tk.info
            
            # 使用你原版的 info.get 與收盤價雙保險邏輯
            current_price = info.get('currentPrice', info.get('regularMarketPrice', None))
            if current_price is None:
                current_price = round(latest['Close'], 2)
                
            # 3. 完整對齊前端所需的 12 個資料欄位
            metrics = {
                "price": clean_val(current_price),
                "change_52w": safe_pct(info.get('52WeekChange'), normal_max=5.0),          # ✅ 改用 safe_pct
                "beta": clean_val(info.get('beta')),
                "trailing_pe": clean_val(info.get('trailingPE')),
                "peg": clean_val(info.get('pegRatio')),
                "dividend_yield": safe_pct(info.get('dividendYield'), normal_max=1.0),     # ✅ 改用 safe_pct
                "revenue_growth": safe_pct(info.get('revenueGrowth'), normal_max=5.0),      # ✅ 改用 safe_pct
                "roe": safe_pct(info.get('returnOnEquity'), normal_max=5.0),                # ✅ 改用 safe_pct
                "debt_to_equity": clean_val(info.get('debtToEquity')),

                # 技術面欄位維持原樣
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
                shard_key = ticker_symbol[:2]
            else:
                shard_key = "US"
                
            if shard_key not in shards:
                shards[shard_key] = {}
            shards[shard_key][ticker_symbol] = metrics
            
        except Exception as e:
            print(f"❌ {ticker_symbol} 處理失敗: {e}")

    # 5. 寫入分片資料夾
    os.makedirs('database', exist_ok=True)
    for key, data in shards.items():
        filename = f"database/data_{key}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"💾 導出分片成功: {filename} ({len(data)} 檔)")

if __name__ == "__main__":
    main()
