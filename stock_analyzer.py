import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import datetime

def calculate_technical_indicators(df):
    """
    計算基礎技術指標: MA, RSI, MACD, KD
    """
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

def get_latest_news(ticker_symbol):
    """
    獲取最新新聞摘要 (簡化版：從 Yahoo Finance 抓取)
    """
    try:
        url = f"https://finance.yahoo.com/quote/{ticker_symbol}/news"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        news_items = soup.find_all('h3', limit=3)
        return [item.get_text() for item in news_items]
    except:
        return ["無法獲取新聞"]

def stock_analysis(ticker_symbol):
    print(f"\n--- 正在分析股票: {ticker_symbol} ---\n")
    
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info
    hist = ticker.history(period="1y")
    
    # 基礎價格與動能
    current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
    change_52w = info.get('52WeekChange', 'N/A')
    
    # 估值指標
    trailing_pe = info.get('trailingPE', 'N/A')
    forward_pe = info.get('forwardPE', 'N/A')
    pe_gap = 'N/A'
    if isinstance(trailing_pe, (int, float)) and isinstance(forward_pe, (int, float)):
        pe_gap = trailing_pe - forward_pe
        
    peg = info.get('pegRatio', 'N/A')
    pb = info.get('priceToBook', 'N/A')
    beta = info.get('beta', 'N/A')
    dividend_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 'N/A'
    
    # 成長與財務
    revenue_growth = info.get('revenueGrowth', 'N/A')
    earnings_growth = info.get('earningsGrowth', 'N/A')
    short_ratio = info.get('shortRatio', 'N/A')
    ebitda = info.get('ebitda', 'N/A')
    profit_margins = info.get('profitMargins', 'N/A')
    roe = info.get('returnOnEquity', 'N/A')
    debt_to_equity = info.get('debtToEquity', 'N/A')
    total_revenue = info.get('totalRevenue', 'N/A') # 近似 Q1 收入
    
    # 技術指標計算
    hist = calculate_technical_indicators(hist)
    latest = hist.iloc[-1] if not hist.empty else None
    
    # 輸出結果
    print(f"【基本資訊與價格】")
    print(f"當前股價: {current_price}")
    print(f"52週漲幅: {change_52w:.2%}" if isinstance(change_52w, float) else f"52週漲幅: {change_52w}")
    print(f"股價動能 (Beta): {beta}")
    print(f"空頭比例: {short_ratio}")
    
    print(f"\n【估值指標】")
    print(f"追蹤 PE: {trailing_pe}")
    print(f"預期 PE: {forward_pe}")
    print(f"本益比落差: {pe_gap}")
    print(f"PEG: {peg}")
    print(f"股價淨值比 (P/B): {pb}")
    print(f"股息殖利率: {dividend_yield}%")
    
    print(f"\n【成長與財務指標】")
    print(f"營收成長率 (YOY): {revenue_growth}")
    print(f"盈餘成長率 (3年期估算): {earnings_growth}")
    print(f"EBITDA: {ebitda}")
    print(f"利潤率: {profit_margins}")
    print(f"ROE: {roe}")
    print(f"D/E (債資比): {debt_to_equity}")
    print(f"總收入 (TTM/最近): {total_revenue}")
    
    if latest is not None:
        print(f"\n【技術指標 (最新)】")
        print(f"MA5: {latest['MA5']:.2f} | MA20: {latest['MA20']:.2f} | MA60: {latest['MA60']:.2f}")
        print(f"RSI (14): {latest['RSI']:.2f}")
        print(f"KD: K={latest['K']:.2f}, D={latest['D']:.2f}")
        print(f"MACD: DIF={latest['DIF']:.2f}, Hist={latest['MACD_Hist']:.2f}")
        print(f"當日成交量: {latest['Volume']}")

    print(f"\n【最新即時資訊】")
    news = get_latest_news(ticker_symbol)
    for n in news:
        print(f"- {n}")
    
    print(f"\n註: GF Value, 預期 FY26 營收, 訂單積壓 等指標通常需付費終端機數據(如 Bloomberg/GuruFocus)，此處以現有開源數據替代。")

if __name__ == "__main__":
    symbol = input("請輸入股票代號 (例如 AAPL, TSLA, 2330.TW): ")
    try:
        stock_analysis(symbol)
    except Exception as e:
        print(f"分析失敗: {e}")
