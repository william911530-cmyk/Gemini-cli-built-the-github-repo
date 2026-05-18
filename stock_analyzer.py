import yfinance as yf
import pandas as pd
import json
import os
import math

# 🌟 原版技術指標運算函數 (100% 完整保留)
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

def main():
    print("🚀 啟動全大盤平行特徵提取管線...")
    
    # 🌟 這裡定義你想覆蓋的完整大盤清單 (可以自由丟入幾百到上千檔台股與美股代號)
    market_tickers = [
        "2330.TW", "2317.TW", "2454.TW", "2382.TW", "3231.TW", "3037.TW", "2603.TW",
        "AAPL", "NVDA", "TSLA", "MSFT", "AMD", "GOOGL", "AMZN", "META"
    ]
    
    # 🌟 技巧：使用 yf.download 進行大批次平行下載，只耗費 1 次請求，完全不踩流量牆
    print(f"📥 正在下載 {len(market_tickers)} 檔大盤歷史K線數據...")
    raw_data = yf.download(market_tickers, period="1y", group_by='ticker', progress=True)
    
    # 用來存放分片資料的字典
    shards = {}

    for ticker in market_tickers:
        try:
            # 提取單一股票的歷史數據
            if len(market_tickers) == 1:
                df = raw_data.copy()
            else:
                if ticker not in raw_data.columns.levels[0]: continue
                df = raw_data[ticker].dropna(subset=['Close'])
                
            if df.empty: continue
            
            # 丟入原版函數計算完整的 MA, RSI, MACD, KD
            df = calculate_technical_indicators(df)
            latest = df.iloc[-1]
            
            # 封裝要給前端看的所有指標欄位
            stock_metrics = {
                "price": round(latest['Close'], 2) if not math.isnan(latest['Close']) else "N/A",
                "ma5": round(latest['MA5'], 2) if 'MA5' in latest and not math.isnan(latest['MA5']) else "N/A",
                "ma20": round(latest['MA20'], 2) if 'MA20' in latest and not math.isnan(latest['MA20']) else "N/A",
                "ma60": round(latest['MA60'], 2) if 'MA60' in latest and not math.isnan(latest['MA60']) else "N/A",
                "rsi": round(latest['RSI'], 2) if 'RSI' in latest and not math.isnan(latest['RSI']) else "N/A",
                "k": round(latest['K'], 2) if 'K' in latest and not math.isnan(latest['K']) else "N/A",
                "d": round(latest['D'], 2) if 'D' in latest and not math.isnan(latest['D']) else "N/A",
                "dif": round(latest['DIF'], 2) if 'DIF' in latest and not math.isnan(latest['DIF']) else "N/A",
                "macd_hist": round(latest['MACD_Hist'], 2) if 'MACD_Hist' in latest and not math.isnan(latest['MACD_Hist']) else "N/A",
                "volume": int(latest['Volume']) if not math.isnan(latest['Volume']) else 0
            }
            
            # 🌟 計算資料分片的路由金鑰 (台股取前兩碼如 '23'，美股統一歸類為 'US')
            if ".TW" in ticker or ".TWO" in ticker:
                shard_key = ticker[:2]
            else:
                shard_key = "US"
                
            if shard_key not in shards:
                shards[shard_key] = {}
                
            shards[shard_key][ticker] = stock_metrics
            
        except Exception as e:
            print(f"❌ 處理 {ticker} 時發生錯誤: {e}")

    # 🌟 將分片字典各自寫入獨立的 JSON 檔案中 (例如 data_23.json)
    os.makedirs('database', exist_ok=True)
    for key, data in shards.items():
        filename = f"database/data_{key}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"💾 成功導出分片資料庫: {filename} ({len(data)} 檔股票)")

if __name__ == "__main__":
    main()
