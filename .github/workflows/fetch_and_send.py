import os
import datetime
import pytz
import requests
import unicodedata
import yfinance as yf

# --- 設定 ---
CONFIG_FILE = "stocks.txt"
DOT_API_KEY = os.environ.get("DOT_API_KEY")
DOT_DEVICE_ID = os.environ.get("DOT_DEVICE_ID")

def load_stocks_config(filepath):
    """外部テキストファイルから設定を読み込む (.T を自動補完)"""
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
                # .T がついていなければ自動で付与
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
        # リアルタイム現在値と前日データを取得するため period="1d" で取得
        # (イントラデイの最新行に現在値が入る、または history から前日終値情報がメタデータとして取れる)
        # 確実な前日終値を取得するために2日分取得し、最新データを現在値、1つ前を前日終値として計算します
        hist = nikkei.history(period="2d")
        if len(hist) >= 2:
            current_price = hist['Close'].iloc[-1]  # 現在値
            prev_close = hist['Close'].iloc[-2]     # 前日終値
            change = current_price - prev_close
            sign = "+" if change >= 0 else ""
            return f" 日経平均:{sign}{change:,.0f}"
    except Exception as e:
        print(f"日経平均の取得に失敗: {e}")
    return ""

def get_stock_prices(stocks_config):
    stocks_data = []
    
    for ticker, config in stocks_config.items():
        code = ticker.split('.')[0] # 表示時は .T を除いた数字のみにする
        name = config["name"]
        limit = config["limit"]
        
        try:
            stock = yf.Ticker(ticker)
            todays_data = stock.history(period="1d")
            
            if not todays_data.empty:
                latest_price = todays_data['Close'].iloc[-1]
                over_amount = max(0, latest_price - limit)
                
                stocks_data.append({
                    "code": code,
                    "name": name,
                    "price": latest_price,
                    "over_amount": over_amount,
                    "is_error": False
                })
            else:
                stocks_data.append({"code": code, "name": name, "price": 0, "over_amount": -1, "is_error": True, "error_msg": "N/A"})
                
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            stocks_data.append({"code": code, "name": name, "price": 0, "over_amount": -2, "is_error": True, "error_msg": "Error"})

    # 超過金額が大きい順にソート
    stocks_data.sort(key=lambda x: x["over_amount"], reverse=True)
    
    text_lines = []
    for item in stocks_data:
        padded_name = pad_text(item["name"], 10)
        code_str = f"[{item['code']}]"
        
        if item["is_error"]:
            err_label = f"{item['error_msg']:>5}円"
            text_lines.append(f"{err_label}        {code_str} {padded_name}")
        else:
            price_str = f"{item['price']:>6,.0f}円"
            
            if item["over_amount"] > 0:
                over_str = pad_text(f"(+{item['over_amount']:,.0f})", 7)
                line = f"{price_str} {over_str} {code_str} {padded_name}"
            else:
                over_str = " " * 7
                line = f"{price_str} {over_str} {code_str} {padded_name}"
                
            text_lines.append(line)
            
    return "\n".join(text_lines)

def send_to_dot_device(title, message):
    url = f"https://dot.mindreset.tech/api/authV2/open/device/{DEVICE_ID}/text"
    
    payload = {
        "refreshNow": True,
        "title": title,
        "message": message,
        "styles": {
            "message": {
                "fontFamily": "UnifontExMono16"
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {DOT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
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
    
    # 日経平均の「現在値 - 前日終値」の増減を取得
    nikkei_info = get_nikkei_change()
    title = f"{time_str}の株価{nikkei_info}"
    
    print("株価データを取得中...")
    message = get_stock_prices(stocks_config)
    
    print("Dot. デバイスへ送信中...")
    send_to_dot_device(title, message)

if __name__ == "__main__":
    main()
