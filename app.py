import os
import re
import hashlib
from PIL import Image
import google.generativeai as genai
from flask import Flask, render_template, request, url_for, send_from_directory # 確保導入這些

# ==========================================
# 1. 初始化設定
# ==========================================
app = Flask(__name__)

# 設定圖片上傳儲存的資料夾
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)
    MODEL_NAME = "gemini-1.5-flash" # 修正模型名稱建議使用 1.5-flash 較穩定
    model = genai.GenerativeModel(MODEL_NAME)
else:
    model = None
    print("警告：未設定 GEMINI_API_KEY 環境變數")

XP_REWARD_CORRECT = 50
XP_REWARD_WRONG = 10
XP_PER_LEVEL = 50

# ==========================================
# 2. 功能函數 (保留你原本的邏輯)
# ==========================================

def get_image_hash(image_path):
    with open(image_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def get_level(xp):
    return (xp or 0) // XP_PER_LEVEL

def recognize_item(image_path):
    if not model:
        return "辨識失敗：API 未初始化。"
    try:
        img = Image.open(image_path)
        prompt = "請辨識圖片中的物品名稱與材質，用繁體中文回答。格式：這是一個(物品)，材質是(材質)。"
        response = model.generate_content([prompt, img])
        return response.text.strip()
    except Exception as e:
        return f"AI 辨識暫時忙碌中: {str(e)}"

def generate_recycling_quiz(item_description):
    # ... (保留你原本的 generate_recycling_quiz 內容)
    return "關於此物品的回收方式？", "(A)清洗後 (B)直接丟", "A", "解析文字"

# ==========================================
# 3. 路由設定 (修正 BuildError 的關鍵)
# ==========================================

# 這是你剛才補上的，確保 Flask 知道去哪裡抓圖片
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # 這裡的 'uploads' 必須與 UPLOAD_FOLDER 一致
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/')
def index():
    return "回收專案運行中"

@app.route('/scan', methods=['POST'])
def scan_page():
    # 假設這裡是你處理上傳邏輯的地方
    # 範例：image_file = "test.jpg"
    # return render_template('result.html', image_file=image_file)
    pass

if __name__ == '__main__':
    app.run(debug=True)
