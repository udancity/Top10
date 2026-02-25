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

# 設定 Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('StockAnalysis')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# LINE 設定
LINE_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')

# ... (保留你原本的 get_yahoo_rank_list, calculate_rsi, analyze_stock 函數) ...

def generate_html(df_up, df_down):
    """將 DataFrame 轉換為帶有 CSS 樣式的 HTML 字串"""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    style = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
        body {{ 
            font-family: 'Noto Sans TC', sans-serif; 
            background-color: #ffffff; color: #5d534a; 
            margin: 0; padding: 40px 20px;
        }}
        .container {{ max-width: 1100px; margin: auto; }}
        h1 {{ font-size: 28px; color: #8c7851; text-align: center; letter-spacing: 2px; }}
        .timestamp {{ text-align: center; color: #b5a18a; font-size: 14px; margin-bottom: 40px; }}
        .flex-container {{ display: flex; gap: 30px; flex-wrap: wrap; }}
        .column {{ 
            flex: 1; min-width: 320px; background: #faf8f5; 
            padding: 25px; border-radius: 25px; 
            box-shadow: 0 10px 25px rgba(0,0,0,0.03); border: 1px solid #f0ede9;
        }}
        h2 {{ font-size: 20px; border-bottom: 2px solid #e8e4de; padding-bottom: 15px; }}
        .up-title {{ color: #88a47c; }}
        .down-title {{ color: #c88a8a; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 15px; }}
        th {{ text-align: left; color: #b5a18a; padding: 12px 8px; border-bottom: 1px solid #eee; }}
        td {{ padding: 15px 8px; border-bottom: 1px dashed #e8e4de; }}
        .no-data {{ color: #ccc; font-style: italic; padding: 20px 0; }}
        @media (max-width: 768px) {{ .flex-container {{ flex-direction: column; }} }}
    </style>
    """
    
    # 這裡修正了變數名稱一致性
    full_html = f"""<!DOCTYPE html>
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
</html>"""
    return full_html

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
        # 1. 存 Excel
        filename = f"Stock_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
        with pd.ExcelWriter(filename) as writer:
            if not df_up.empty: df_up.to_excel(writer, sheet_name='漲幅', index=False)
            if not df_down.empty: df_down.to_excel(writer, sheet_name='跌幅', index=False)

        # 2. 生成 HTML
        html_content = generate_html(df_up, df_down)
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html_content)

        # 3. 產出 JSON (移進 main 函數內)
        data_json = {
            "update_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "up_list": df_up.to_dict(orient='records') if not df_up.empty else [],
            "down_list": df_down.to_dict(orient='records') if not df_down.empty else []
        }
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(data_json, f, ensure_ascii=False, indent=4)

        # 4. LINE 推播
        send_line_push(df_up, df_down)
        print("✅ 全部任務完成：Excel, HTML, JSON 皆已產出")
    else:
        print("❌ 未抓取到數據")

if __name__ == "__main__":
    main()
