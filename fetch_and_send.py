import os
import datetime
import pytz
import requests
import unicodedata
import math
import yfinance as yf

# --- 設定 ---
CONFIG_FILE = "stocks.txt"
# 正常動作しているお天気スクリプトと完全に同じ変数名
DOT_API_KEY = os.environ.get("QUOTE0_API_KEY")
DOT_DEVICE_ID = os.environ.get("QUOTE0_DEVICE_ID")

def load_stocks_config(filepath):
    """外部テキストファイルから設定を読み込む (.T を自動補完、#の注釈を無視)"""
    config = {}
    if not os.path.exists(filepath):
        print(f"エラー: {filepath} が見つかりません。")
        return config
        
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            parts = line.split(",")
            if len(parts) == 3:
                raw_code = parts[0].strip()
                ticker = raw_code if raw_code.endswith(".T") else f"{raw_code}.T"
                name = parts[1].strip()
                limit = float(parts[2].strip())
                config[ticker] = {"name": name, "limit": limit}
    return config

def get_display_width(text):
    """UnifontExMono16 の幅に合わせ、全角を2、半角を1として計算"""
    count = 0
    for c in text:
        if unicodedata.east_asian_width(c) in 'FWA':
            count += 2
        else:
            count += 1
    return count

def pad_text(text, target_width):
    """指定されたグリッド幅（半角文字数換算）になるように半角スペースで埋める"""
    current_width = get_display_width(text)
    padding_needed = target_width - current_width
    if padding_needed > 0:
        return text + (" " * padding_needed)
    return text

def get_nikkei_change():
    """日経平均の現在値と前日終値との増減を取得する"""
    try:
        nikkei = yf.Ticker("^N225")
        hist = nikkei.history(period="2d")
        if len(hist) >= 2:
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            change = current_price - prev_close
            sign = "+" if change >= 0 else ""
            return f" 日経平均:{sign}{change:,.0f}"
    except Exception as e:
        print(f"日経平均の取得に失敗: {e}")
    return ""

def get_stock_prices(stocks_config):
    stocks_data = []
    
    for ticker, config in stocks_config.items():
        code = ticker.split('.')[0]
        name = config["name"]
        limit = config["limit"]
        
        try:
            stock = yf.Ticker(ticker)
            todays_data = stock.history(period="2d")
            
            if len(todays_data) >= 2:
                latest_price = todays_data['Close'].iloc[-1]
                prev_close = todays_data['Close'].iloc[-2]
                
                raw_pct = ((latest_price - prev_close) / prev_close) * 100
                if raw_pct >= 0:
                    pct_change = math.floor(raw_pct)
                else:
                    pct_change = math.ceil(raw_pct)
                
                over_amount = max(0, latest_price - limit)
                
                stocks_data.append({
                    "code": code,
                    "name": name,
                    "price": latest_price,
                    "pct_change": pct_change,
                    "over_amount": over_amount,
                    "is_error": False
                })
            else:
                stocks_data.append({"code": code, "name": name, "price": 0, "pct_change": 0, "over_amount": -1, "is_error": True, "error_msg": "N/A"})
                
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            stocks_data.append({"code": code, "name": name, "price": 0, "pct_change": 0, "over_amount": -2, "is_error": True, "error_msg": "Error"})

    # 超過金額が大きい順にソート
    stocks_data.sort(key=lambda x: x["over_amount"], reverse=True)
    
    # 対象株が6以上の場合、増加値の高い5つに絞り込む
    if len(stocks_data) > 5:
        stocks_data = stocks_data[:5]
    
    text_lines = []
    for item in stocks_data:
        if item["is_error"]:
            err_label = f"  {item['error_msg']:>3}円"
            line_left = f" {err_label}        [{item['code']}] "
            full_line_content = f"{line_left}{item['name']}"
            line = pad_text(full_line_content, 37)
            text_lines.append(line)
        else:
            price_str = f"{item['price']:>6,.0f}円"
            sign = "+" if item["pct_change"] > 0 else ""
            pct_text = f"({sign}{item['pct_change']}%)"
            padded_pct = pad_text(pct_text, 6)
            code_str = f"[{item['code']}]"
            
            line_left = f" {price_str} {padded_pct} {code_str} "
            full_line_content = f"{line_left}{item['name']}"
            line = pad_text(full_line_content, 37)
            text_lines.append(line)
            
    return "\n".join(text_lines)

def send_to_dot_device(title, message):
    url = f"https://dot.mindreset.tech/api/authV2/open/device/{DOT_DEVICE_ID}/text"
    
    print("\n--- [送信データ内容ログ] ───")
    print(f"■ タイトル:\n{title}")
    print(f"■ メッセージ本文:\n{message}")
    print("────────────────────────────\n")
    
    # 💡 お天気スクリプトと完全に同じペイロード（style）構造に合わせました
    payload = {
        "refreshNow": True,
        "title": title,
        "message": message,
        "style": "UnifontExMono16"
    }
    
    headers = {
        "Authorization": f"Bearer {DOT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code in [200, 201]:
        print(f"成功: {response.json().get('message')}")
    else:
        print(f"エラー {response.status_code}: {response.text}")

def main():
    stocks_config = load_stocks_config(CONFIG_FILE)
    if not stocks_config:
        print("設定データがありません。")
        return

    jst = pytz.timezone('Asia/Tokyo')
    now_jst = datetime.datetime.now(jst)
    time_str = now_jst.strftime("%H:%M")
    
    nikkei_info = get_nikkei_change()
    title = f"{time_str}の株価{nikkei_info}"
    
    message = get_stock_prices(stocks_config)
    send_to_dot_device(title, message)

if __name__ == "__main__":
    main()
