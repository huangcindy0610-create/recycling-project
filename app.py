import os
import hashlib
from PIL import Image
import pillow_heif  # 支援 iPhone HEIC 格式
import google.generativeai as genai
from flask import Flask, render_template, request, url_for, send_from_directory, session, jsonify

# 註冊 HEIF 解碼器 (必須放在 app 初始化前或啟動時)
pillow_heif.register_heif_opener()

# ==========================================
# 1. 初始化設定
# ==========================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "recycling-secret-123")

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 模擬資料庫 (Render 重啟會重置)
daily_usage = {}   
uploaded_hashes = set() 
DAILY_LIMIT = 10

API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

XP_REWARD_CORRECT = 50
XP_REWARD_WRONG = 10

# ==========================================
# 2. 功能函數
# ==========================================

def get_image_hash(image_path):
    with open(image_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def recognize_item(image_path):
    if not model: return "API 未設定，材質是未知。"
    try:
        # 開啟圖片並強制轉為 RGB 確保相容性
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        prompt = "請辨識圖片中的物品名稱與材質。格式：這是一個(物品)，材質是(材質)。"
        response = model.generate_content([prompt, img])
        
        # 如果 AI 沒回傳內容，給予預設文字
        return response.text.strip() if response.text else "這是一個物品，材質是待確認。"
    except Exception as e:
        # 即使報錯也回傳字串，確保前端模板不會崩潰
        return f"這是一個物品，材質是待確認。(原因: {str(e)})"

def generate_recycling_quiz(item_description):
    # 使用防呆分割，避免 description 格式不對導致報錯
    parts = item_description.split('，')
    item_name = parts[0].replace("這是一個", "") if len(parts) > 0 else "物品"
    
    question = f"關於「{item_name}」的回收處理方式，哪一個正確？"
    options = "(A) 直接丟進一般垃圾\n(B) 根據材質分類回收\n(C) 焚燒處理\n(D) 隨便亂丟"
    return question, options, "B", "正確答案是 B。適當的分類能讓資源重啟第二生命！"

# ==========================================
# 3. 路由設定
# ==========================================

@app.route('/healthz')
def health_check():
    return "OK", 200

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/')
def index():
    user = "環保小隊長" 
    used = daily_usage.get(user, 0)
    remaining = max(0, DAILY_LIMIT - used)
    return render_template('index.html', username=user, remaining_uploads=remaining, daily_limit=DAILY_LIMIT)

@app.route('/scan', methods=['POST'])
def scan_page():
    user = "環保小隊長"
    used = daily_usage.get(user, 0)
    
    # 用於報錯時回傳首頁的參數
    index_params = {"username": user, "remaining_uploads": max(0, DAILY_LIMIT - used), "daily_limit": DAILY_LIMIT}

    # 1. 檢查次數
    if used >= DAILY_LIMIT:
        return render_template('index.html', **index_params, daily_limit_error=True)

    file = request.files.get('file')
    if not file or file.filename == '':
        return "檔名不可為空", 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # 2. 檢查重複 (Hash)
    img_hash = get_image_hash(file_path)
    if img_hash in uploaded_hashes:
        os.remove(file_path)
        return render_template('index.html', **index_params, duplicate_error=True)

    # 3. 通過檢查
    uploaded_hashes.add(img_hash)
    daily_usage[user] = used + 1
    
    # 4. AI 辨識與出題
    description = recognize_item(file_path)
    q, opt, ans, expl = generate_recycling_quiz(description)
    
    session['correct_answer'] = ans
    session['explanation'] = expl

    # 確保所有 result.html 需要的變數都有傳入，找回你的小隊長介面！
    return render_template('result.html', 
                           username=user, 
                           image_file=file.filename,
                           item_result=description,
                           question=q,
                           options=opt)

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    is_correct = (data.get('answer') == session.get('correct_answer'))
    return jsonify({
        "correct": is_correct,
        "gained_xp": XP_REWARD_CORRECT if is_correct else XP_REWARD_WRONG,
        "correct_answer": session.get('correct_answer', 'B'),
        "explanation": session.get('explanation', '尚無解析'),
        "leveled_up": False,
        "new_level": 1
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
