name: Stock Analysis Daily Run

on:
  schedule:
    - cron: '40 5 * * 1-5'  # 台灣時間週一至週五下午 1:40 執行
  workflow_dispatch:      # 支援手動點擊執行

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: pip install pandas yfinance requests beautifulsoup4 lxml

      - name: Run Analysis
        env:
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_USER_ID: ${{ secrets.LINE_USER_ID }}
        run: python main.py

      - name: Save CSV Result
        uses: actions/upload-artifact@v3
        with:
          name: Daily-Stock-Report
          path: "*.csv"
