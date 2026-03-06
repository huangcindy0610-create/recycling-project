import os
import hashlib
from PIL import Image
import pillow_heif
import google.generativeai as genai
from flask import Flask, render_template, request, url_for, send_from_directory, session, jsonify

# 支援 iPhone HEIC
pillow_heif.register_heif_opener()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "reborn-v4-key-999")

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 模擬資料庫
daily_usage = {}
uploaded_hashes = set()
DAILY_LIMIT = 10

# 模擬經驗值與圖表數據 (實際應用建議存入資料庫)
user_stats = {
    "xp": 120,      # 假設當前總 EXP
    "level": 3,     # 假設當前等級
    "chart_data": [2.5, 4.0, 1.5, 5.5, 3.2, 0, 0], # 週一到週日的咖啡時數
    "sessions_data": [
        [{"duration": "45m", "start": "09:00", "end": "09:45"}, {"duration": "1h", "start": "14:00", "end": "15:00"}], # 週一
        [{"duration": "2h", "start": "10:00", "end": "12:00"}], # 週二
        [], [], [], [], [] # 週三~週日 (範例)
    ]
}

API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("models/gemini-1.5-flash")
else:
    model = None

# ================= 路由設定 =================

@app.route('/')
def index():
    user = "環保小隊長"
    return render_template('index.html', 
                           username=user, 
                           xp=user_stats["xp"],
                           level=user_stats["level"],
                           chart_data=user_stats["chart_data"],
                           sessions_data=user_stats["sessions_data"],
                           remaining_uploads=DAILY_LIMIT - daily_usage.get(user, 0),
                           daily_limit=DAILY_LIMIT)

@app.route('/healthz')
def health_check(): return "OK", 200

@app.route('/uploads/<filename>')
def uploaded_file(filename): return send_from_directory(UPLOAD_FOLDER, filename)

# 沿用之前的 scan 與 submit 邏輯...
@app.route('/scan', methods=['GET', 'POST'])
def scan_page():
    if request.method == 'GET':
        # 這裡也要確保首頁參數存在，以免報錯
        return render_template('index.html', username="環保小隊長", xp=user_stats["xp"], level=user_stats["level"], chart_data=user_stats["chart_data"], sessions_data=user_stats["sessions_data"], remaining_uploads=DAILY_LIMIT, daily_limit=DAILY_LIMIT)
    
    # 處理 POST 辨識邏輯 (沿用之前的程式碼)
    # ...
    return "辨識功能正常運作中"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
