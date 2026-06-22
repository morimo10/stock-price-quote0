name: Send Stock Price to Dot Device

on:
  schedule:
    # 例: 平日の日本時間 9:00〜15:00 の間に毎時0分に実行する場合 (UTC 0:00〜6:00)
    - cron: '0 0-6 * * 1-5'
  workflow_dispatch: # 手動実行用のボタンを有効化

jobs:
  run-script:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests pytz yfinance unicodedata2

      - name: Run Stock Script
        # 💡 ここでGitHubのSecretsを、Pythonが読み込める環境変数に紐付けています
        env:
          QUOTE0_API_KEY_2: ${{ secrets.QUOTE0_API_KEY_2 }}
          QUOTE0_DEVICE_ID_2: ${{ secrets.QUOTE0_DEVICE_ID_2 }}
        run: |
          python fetch_and_send.py
