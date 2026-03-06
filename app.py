import os
import hashlib
from PIL import Image
import google.generativeai as genai
from flask import Flask, render_template, request, url_for, send_from_directory, session, jsonify

# ==========================================
# 1. 初始化設定
# ==========================================
app = Flask(__name__)
# 建議在 Render 環境變數設定 FLASK_SECRET_KEY
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "recycling-secret-123")

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 模擬資料庫 (注意：Render 重新部署後會重置)
daily_usage = {}   # 格式: {"環保小隊長": 3}
uploaded_hashes = set() # 存放圖片的 SHA256
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
    """產生圖片的雜湊值，用來辨識是否重複上傳"""
    with open(image_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def recognize_item(image_path):
    if not model: return "API 未設定，無法辨識"
    try:
        img = Image.open(image_path)
        prompt = "請辨識圖片中的物品名稱與材質。格式：這是一個(物品)，材質是(材質)。"
        response = model.generate_content([prompt, img])
        return response.text.strip()
    except Exception as e:
        return f"辨識暫時忙碌中: {str(e)}"

def generate_recycling_quiz(item_description):
    """根據辨識結果產生題目"""
    item_name = item_description.split('，')[0].replace("這是一個", "")
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
    user = "環保小隊長" # 這裡未來可以改為登入系統後的用戶名
    used = daily_usage.get(user, 0)
    remaining = max(0, DAILY_LIMIT - used)
    
    return render_template('index.html', 
                           username=user, 
                           remaining_uploads=remaining, 
                           daily_limit=DAILY_LIMIT)

@app.route('/scan', methods=['POST'])
def scan_page():
    user = "環保小隊長"
    used = daily_usage.get(user, 0)

    # 1. 檢查每日限制
    if used >= DAILY_LIMIT:
        return render_template('index.html', username=user, daily_limit_error=True, 
                               remaining_uploads=0, daily_limit=DAILY_LIMIT)

    if 'file' not in request.files:
        return "請選擇檔案", 400
    
    file = request.files['file']
    if file.filename == '':
        return "檔名不可為空", 400

    # 儲存檔案
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # 2. 檢查圖片重複 (透過 Hash)
    img_hash = get_image_hash(file_path)
    if img_hash in uploaded_hashes:
        os.remove(file_path) # 刪除重複檔案節省空間
        return render_template('index.html', username=user, duplicate_error=True, 
                               remaining_uploads=DAILY_LIMIT - used, daily_limit=DAILY_LIMIT)

    # 3. 通過檢查，紀錄次數與 Hash
    uploaded_hashes.add(img_hash)
    daily_usage[user] = used + 1
    
    # 4. AI 辨識與出題
    description = recognize_item(file_path)
    q, opt, ans, expl = generate_recycling_quiz(description)
    
    # 存入 session 供 /submit_answer 使用
    session['correct_answer'] = ans
    session['explanation'] = expl

    return render_template('result.html', 
                           username=user, 
                           image_file=file.filename,
                           item_result=description,
                           question=q,
                           options=opt)

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    user_ans = data.get('answer')
    
    correct_ans = session.get('correct_answer', 'B')
    explanation = session.get('explanation', '尚無解析')
    
    is_correct = (user_ans == correct_ans)
    gained_xp = XP_REWARD_CORRECT if is_correct else XP_REWARD_WRONG
    
    return jsonify({
        "correct": is_correct,
        "gained_xp": gained_xp,
        "correct_answer": correct_ans,
        "explanation": explanation,
        "leveled_up": False,
        "new_level": 1
    })

# ==========================================
# 4. 啟動設定
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
