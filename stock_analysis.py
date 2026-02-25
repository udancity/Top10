import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import requests
import os
from bs4 import BeautifulSoup
import re
import logging
import json

# 1. 基本設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('StockAnalysis')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

LINE_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')

# 2. 工具函數區 (必須放在 main 之前)
def get_yahoo_rank_list(rank_type="down"):
    url = f"https://tw.stock.yahoo.com/rank/change-{rank_type}?category=all"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200: return []
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
    if len(series) < period: return pd.Series([50] * len(series))
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker_num, stock_name):
    for suffix in [".TW", ".TWO"]:
        ticker = f"{ticker_num}{suffix}"
        try:
            df = yf.download(ticker, period="1y", progress=False, auto_adjust=True, threads=False)
            if df.empty or len(df) < 60: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            close_series = df['Close']
            last_price = float(close_series.iloc[-1])
            prev_price = float(close_series.iloc[-2])
            change_pct = ((last_price - prev_price) / prev_price) * 100
            ma20 = close_series.rolling(window=20).mean().iloc[-1]
            rsi_series = calculate_rsi(close_series, 14)
            rsi = rsi_series.iloc[-1]
            return {
                "代號": ticker_num, "股名": stock_name, "現價": round(last_price, 2),
                "漲跌幅%": round(change_pct, 2), "RSI(14)": round(rsi, 1),
                "20日均線": round(ma20, 2), "位階": "線上" if last_price > ma20 else "線下",
                "更新時間": datetime.now().strftime('%H:%M')
            }
        except: continue
    return None

def send_line_push(df_up, df_down):
    if not LINE_TOKEN or not LINE_USER_ID: return
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    msg = f"📊 台股雙向掃描 ({now_str})\n" + "─" * 15 + "\n"
    msg += "📈 漲幅 Top 10\n"
    for _, r in df_up.sort_values("漲跌幅%", ascending=False).head(10).iterrows():
        msg += f"• {r['代號']} {r['股名']} | {r['漲跌幅%']:+.1f}% | {r['現價']}\n"
    msg += "\n📉 跌幅 Top 10\n"
    for _, r in df_down.sort_values("漲跌幅%", ascending=True).head(10).iterrows():
        msg += f"• {r['代號']} {r['股名']} | {r['漲跌幅%']:+.1f}% | {r['現價']}\n"
    url = "https://api.line.me/v2/bot/message/multicast"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    user_ids = LINE_USER_ID.split(',')
    payload = {"to": [u.strip() for u in user_ids], "messages": [{"type": "text", "text": msg}]}
    requests.post(url, headers=headers, json=payload)

# 3. HTML 生成函數
def generate_html(df_up, df_down):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    style = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
        body {{ font-family: 'Noto Sans TC', sans-serif; background-color: #ffffff; color: #5d534a; margin: 0; padding: 40px 20px; }}
        .container {{ max-width: 1100px; margin: auto; }}
        h1 {{ font-size: 28px; color: #8c7851; text-align: center; letter-spacing: 2px; }}
        .timestamp {{ text-align: center; color: #b5a18a; font-size: 14px; margin-bottom: 40px; }}
        .flex-container {{ display: flex; gap: 30px; flex-wrap: wrap; }}
        .column {{ flex: 1; min-width: 320px; background: #faf8f5; padding: 25px; border-radius: 25px; border: 1px solid #f0ede9; }}
        h2 {{ font-size: 20px; border-bottom: 2px solid #e8e4de; padding-bottom: 15px; }}
        .up-title {{ color: #88a47c; }} .down-title {{ color: #c88a8a; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 15px; }}
        th {{ text-align: left; color: #b5a18a; padding: 12px 8px; border-bottom: 1px solid #eee; }}
        td {{ padding: 15px 8px; border-bottom: 1px dashed #e8e4de; }}
        @media (max-width: 768px) {{ .flex-container {{ flex-direction: column; }} }}
    </style>
    """
    full_html = f"""<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8">{style}</head>
    <body><div class="container"><h1>🌿 每日漲跌排名</h1><div class="timestamp">更新於：{now_str}</div>
    <div class="flex-container">
    <div class="column"><h2 class="up-title">▲ 強勢</h2>{df_up.to_html(index=False) if not df_up.empty else '無數據'}</div>
    <div class="column"><h2 class="down-title">▼ 弱勢</h2>{df_down.to_html(index=False) if not df_down.empty else '無數據'}</div>
    </div></div></body></html>"""
    return full_html

# 4. 主程式
def main():
    logger.info("🚀 啟動分析系統...")
    up_raw = get_yahoo_rank_list("up")
    down_raw = get_yahoo_rank_list("down")

    results_up = [res for s in up_raw if (res := analyze_stock(s['ticker'], s['name']))]
    results_down = [res for s in down_raw if (res := analyze_stock(s['ticker'], s['name']))]

    df_up = pd.DataFrame(results_up)
    df_down = pd.DataFrame(results_down)

    if not df_up.empty or not df_down.empty:
        # 存 HTML
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(generate_html(df_up, df_down))
        
        # 存 JSON
        data_json = {
            "update_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "up_list": df_up.to_dict(orient='records'),
            "down_list": df_down.to_dict(orient='records')
        }
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(data_json, f, ensure_ascii=False, indent=4)

        # 存 Excel
        with pd.ExcelWriter(f"Stock_Report_{datetime.now().strftime('%Y%m%d')}.xlsx") as writer:
            if not df_up.empty: df_up.to_excel(writer, sheet_name='漲幅', index=False)
            if not df_down.empty: df_down.to_excel(writer, sheet_name='跌幅', index=False)

        send_line_push(df_up, df_down)
        logger.info("✅ 任務完成")

if __name__ == "__main__":
    main()
