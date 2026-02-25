import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import requests
import os
from bs4 import BeautifulSoup
import re
import logging

# 設定 Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('StockAnalysis')

# 隱藏 yfinance 內部的錯誤日誌
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# 從環境變數讀取 LINE 設定 (GitHub Secrets)
LINE_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')

def get_yahoo_rank_list(rank_type="down"):
    """抓取 Yahoo 股市排行榜"""
    url = f"https://tw.stock.yahoo.com/rank/change-{rank_type}?category=all"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('li', class_='List(n)')
        results = []
        for row in rows:
            ticker_link = row.find('a', href=re.compile(r'/quote/(\d{4,6})'))
            if ticker_link:
                href = ticker_link.get('href')
                match = re.search(r'/quote/(\d{4,6})', href)
                if match:
                    ticker_num = match.group(1)
                    name_div = row.find('div', class_='Lh(20px)')
                    stock_name = name_div.text.strip() if name_div else "未知"
                    if not any(d['ticker'] == ticker_num for d in results):
                        results.append({'ticker': ticker_num, 'name': stock_name})
        return results[:50]
    except Exception as e:
        logger.error(f"抓取排行榜失敗: {e}")
        return []

def calculate_rsi(series, period=14):
    if len(series) < period: return 50
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    last_loss = loss.iloc[-1]
    if pd.isna(last_loss) or last_loss == 0: return 100
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker_num, stock_name):
    """分析個股技術面"""
    for suffix in [".TW", ".TWO"]:
        ticker = f"{ticker_num}{suffix}"
        try:
            df = yf.download(ticker, period="1y", progress=False, auto_adjust=True, threads=False)
            if df.empty or len(df) < 60:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            close_series = df['Close']
            last_price = float(close_series.iloc[-1])
            prev_price = float(close_series.iloc[-2])
            change_pct = ((last_price - prev_price) / prev_price) * 100

            ma20 = close_series.rolling(window=20).mean().iloc[-1]
            rsi = calculate_rsi(close_series, 14).iloc[-1]

            return {
                "代號": ticker_num,
                "股名": stock_name,
                "現價": round(last_price, 2),
                "漲跌幅%": round(change_pct, 2),
                "RSI(14)": round(rsi, 1),
                "20日均線(月線)": round(ma20, 2),
                "月線位階": "線上" if last_price > ma20 else "線下",
                "更新時間": datetime.now().strftime('%H:%M')
            }
        except:
            continue
    return None

def send_line_push(df_up, df_down):
    """發送 LINE 推播訊息"""
    if not LINE_TOKEN or not LINE_USER_ID:
        logger.warning("未設定 LINE Token 或 User ID，跳過推播。")
        return

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    msg = f"📊 台股雙向掃描 ({now_str})\n"
    msg += "─" * 15 + "\n"

    # 漲幅前 10
    msg += "📈 漲幅 Top 10\n"
    top_up = df_up.sort_values("漲跌幅%", ascending=False).head(10)
    for _, r in top_up.iterrows():
        msg += f"• {r['代號']} {r['股名']} | {r['漲跌幅%']:+.1f}% | {r['現價']}\n"

    msg += "\n📉 跌幅 Top 10\n"
    top_down = df_down.sort_values("漲跌幅%", ascending=True).head(10)
    for _, r in top_down.iterrows():
        msg += f"• {r['代號']} {r['股名']} | {r['漲跌幅%']:+.1f}% | {r['現價']}\n"

    # 傳送請求
    url = "https://api.line.me/v2/bot/message/multicast"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    user_ids = LINE_USER_ID.split(',')
    payload = {"to": [u.strip() for u in user_ids], "messages": [{"type": "text", "text": msg}]}
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        logger.info(f"LINE 推播狀態: {res.status_code}")
    except Exception as e:
        logger.error(f"LINE 推播失敗: {e}")

def generate_html(df_up, df_down):
    """將 DataFrame 轉換為帶有 CSS 樣式的 HTML 字串"""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    style = """
   <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
        
        body { 
            font-family: 'Noto Sans TC', sans-serif; 
            background-color: #ffffff; /* 純白底色 */
            color: #5d534a; 
            margin: 0; 
            padding: 40px 20px;
        }
        .container { max-width: 1100px; margin: auto; }
        
        h1 { 
            font-size: 28px; 
            color: #8c7851; 
            text-align: center; 
            margin-bottom: 5px; 
            letter-spacing: 2px;
        }
        .timestamp { 
            text-align: center; 
            color: #b5a18a; 
            font-size: 14px; 
            margin-bottom: 40px; 
        }
        
        /* 雙欄佈局設定 */
        .flex-container { 
            display: flex; 
            gap: 30px; 
            flex-wrap: wrap; 
        }
        .column { 
            flex: 1; 
            min-width: 320px; 
            background: #faf8f5; /* 輕微灰白色卡片 */
            padding: 25px; 
            border-radius: 25px; 
            box-shadow: 0 10px 25px rgba(0,0,0,0.03);
            border: 1px solid #f0ede9;
        }
        
        h2 { 
            font-size: 20px; 
            margin-top: 0; 
            padding-bottom: 15px; 
            border-bottom: 2px solid #e8e4de;
            display: flex;
            align-items: center;
        }
        .up-title { color: #88a47c; } /* 森林綠 */
        .down-title { color: #c88a8a; } /* 晚霞紅 */

        table { 
            border-collapse: collapse; 
            width: 100%; 
            margin-top: 10px;
            font-size: 15px;
        }
        th { 
            text-align: left; 
            color: #b5a18a; 
            font-weight: 500; 
            padding: 12px 8px;
            border-bottom: 1px solid #eee;
        }
        td { 
            padding: 15px 8px; 
            border-bottom: 1px dashed #e8e4de; 
        }
        tr:last-child td { border-bottom: none; }
        
        .no-data { color: #ccc; font-style: italic; padding: 20px 0; }
        
        /* 手機版適應 */
        @media (max-width: 768px) {
            .flex-container { flex-direction: column; }
        }
    </style>
    """
    
    # 處理漲幅數據
    up_html = ""
 <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        {style}
    </head>
    <body>
        <div class="container">
            <h1>🌿 每日漲跌排名</h1>
            <div class="timestamp">數據更新於：{now_str}</div>
            
            <div class="flex-container">
                <div class="column">
                    <h2 class="up-title">▲ 強勢</h2>
                    {df_up.to_html(index=False, classes='stock-table') if not df_up.empty else '<p class="no-data">今日暫無強勢訊號</p>'}
                </div>
                
                <div class="column">
                    <h2 class="down-title">▼ 弱勢</h2>
                    {df_down.to_html(index=False, classes='stock-table') if not df_down.empty else '<p class="no-data">今日暫無弱勢訊號</p>'}
                </div>
            </div>
        </div>
    </body>
    </html>
"""
    return html

import json

# 將 DataFrame 轉成字典格式
data = {
    "update_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "up_list": df_up.to_dict(orient='records'),
    "down_list": df_down.to_dict(orient='records')
}

# 儲存為 data.json
with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

def main():
    print("🚀 啟動分析系統...")
    down_list = get_yahoo_rank_list("down")
    up_list = get_yahoo_rank_list("up")

    results_up = []
    for s in up_list:
        res = analyze_stock(s['ticker'], s['name'])
        if res: results_up.append(res)
        time.sleep(0.5)

    results_down = []
    for s in down_list:
        res = analyze_stock(s['ticker'], s['name'])
        if res: results_down.append(res)
        time.sleep(0.5)

    df_up = pd.DataFrame(results_up)
    df_down = pd.DataFrame(results_down)

    if not df_up.empty or not df_down.empty:
        # 儲存 Excel (選配)
        filename = f"Stock_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
        with pd.ExcelWriter(filename) as writer:
            if not df_up.empty: df_up.to_excel(writer, sheet_name='漲幅', index=False)
            if not df_down.empty: df_down.to_excel(writer, sheet_name='跌幅', index=False)
        
        # 生成 HTML 報表
        html_content = generate_html(df_up, df_down)
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("✅ HTML 報表已生成: index.html")
        
        # LINE 推播
        send_line_push(df_up, df_down)
        print("✅ 任務完成")
    else:
        print("❌ 未抓取到數據")

if __name__ == "__main__":
    main()
