import os
import re
import hashlib
from PIL import Image
import google.generativeai as genai
from flask import Flask, render_template, request, url_for, send_from_directory

# ==========================================
# 1. 初始化設定
# ==========================================
app = Flask(__name__)

# 設定圖片上傳儲存的資料夾
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 從環境變數讀取 API KEY
API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)
    # 建議使用 gemini-1.5-flash，速度快且對圖片辨識度高
    MODEL_NAME = "gemini-1.5-flash" 
    model = genai.GenerativeModel(MODEL_NAME)
else:
    model = None
    print("警告：未設定 GEMINI_API_KEY 環境變數")

XP_REWARD_CORRECT = 50
XP_REWARD_WRONG = 10
XP_PER_LEVEL = 50

# ==========================================
# 2. 功能函數
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
    # 這裡放你原本的題目生成邏輯
    return "關於此物品的回收方式？", "(A)清洗後 (B)直接丟", "A", "解析文字"

# ==========================================
# 3. 路由設定
# ==========================================

# 新增：健康檢查路徑，解決 Render 404 問題
@app.route('/healthz')
def health_check():
    return "OK", 200

# 確保 Flask 知道去哪裡抓圖片
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/')
def index():
    return "回收專案運行中 (The recycling project is running!)"

@app.route('/scan', methods=['POST'])
def scan_page():
    if 'file' not in request.files:
        return "沒有上傳檔案", 400
    
    file = request.files['file']
    if file.filename == '':
        return "未選擇檔案", 400

    if file:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        
        # 執行辨識
        description = recognize_item(file_path)
        
        # 這裡你可以根據需求 render 你的 result.html
        # return render_template('result.html', description=description, image_file=file.filename)
        return f"辨識結果: {description}"

# ==========================================
# 4. 啟動設定
# ==========================================
if __name__ == '__main__':
    # Render 會提供 PORT 環境變數，如果沒有則預設 5000
    port = int(os.environ.get("PORT", 5000))
    # 部署到 Render 時 debug 建議設為 False
    app.run(host='0.0.0.0', port=port, debug=False)
