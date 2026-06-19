import os
import datetime
import pytz
import requests
import unicodedata
import yfinance as yf

# --- 設定 ---
CONFIG_FILE = "stocks.txt"
QUOTE0_API_URL = os.environ.get("QUOTE0_API_URL")
QUOTE0_API_TOKEN = os.environ.get("QUOTE0_API_TOKEN")

def load_stocks_config(filepath):
    """外部テキストファイルから設定を読み込む"""
    config = {}
    if not os.path.exists(filepath):
        print(f"エラー: {filepath} が見つかりません。")
        return config
        
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): # 空行やコメントをスキップ
                continue
            parts = line.split(",")
            if len(parts) == 3:
                ticker = parts[0].strip()
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
    """日経平均の前日比（増減）を取得する"""
    try:
        nikkei = yf.Ticker("^N225")
        hist = nikkei.history(period="2d") # 前日比計算のために2日分取得
        if len(hist) >= 2:
            current_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            change = current_price - prev_price
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
            # ズレ防止のため、エラー時も超過スペース用のダミー幅（7マス）を確保
            text_lines.append(f"{err_label}        {code_str} {padded_name}")
        else:
            price_str = f"{item['price']:>6,.0f}円"
            
            if item["over_amount"] > 0:
                # 超過分表示部分。文字の最大幅を考慮して左寄せ（例: "(+100) "）
                over_str = pad_text(f"(+{item['over_amount']:,.0f})", 7)
                line = f"{price_str} {over_str} {code_str} {padded_name}"
            else:
                # 超過していない場合は、同じ幅の半角スペースで埋めて位置を維持
                over_str = " " * 7
                line = f"{price_str} {over_str} {code_str} {padded_name}"
                
            text_lines.append(line)
            
    return "\n".join(text_lines)

def send_to_quote0(title, body):
    payload = {"title": title, "body": body}
    headers = {
        "Authorization": f"Bearer {QUOTE0_API_TOKEN}",
        "Content-Type": "application/json"
    }
    response = requests.post(QUOTE0_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        print("Successfully sent to Quote/0")
    else:
        print(f"Failed to send: {response.status_code}, {response.text}")

def main():
    # 外部設定ファイルの読み込み
    stocks_config = load_stocks_config(CONFIG_FILE)
    if not stocks_config:
        print("設定が空のため処理を終了します。")
        return

    jst = pytz.timezone('Asia/Tokyo')
    now_jst = datetime.datetime.now(jst)
    time_str = now_jst.strftime("%H:%M")
    
    # 日経平均の増減を取得してタイトルにドッキング
    nikkei_info = get_nikkei_change()
    title = f"{time_str}の株価{nikkei_info}"
    
    print("Fetching stock prices...")
    body = get_stock_prices(stocks_config)
    
    print(f"Sending to Quote/0:\n[Title]: {title}\n[Body]:\n{body}")
    send_to_quote0(title, body)

if __name__ == "__main__":
    main()
