import os
import hashlib
from PIL import Image
import google.generativeai as genai
from flask import Flask, render_template, request, url_for, send_from_directory, session, jsonify

# ==========================================
# 1. 初始化設定
# ==========================================
app = Flask(__name__)
# 必須設定 Secret Key 才能使用 session 功能
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "recycling-secret-123")

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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

def recognize_item(image_path):
    if not model: return "API 未設定"
    try:
        img = Image.open(image_path)
        prompt = "請辨識圖片中的物品名稱與材質。格式：這是一個(物品)，材質是(材質)。"
        response = model.generate_content([prompt, img])
        return response.text.strip()
    except Exception as e:
        return f"辨識出錯: {str(e)}"

def generate_recycling_quiz(item_description):
    """
    這裡暫時使用靜態題目，若要更強大，
    可以改用 Gemini 根據 item_description 生成 json 格式題目。
    """
    question = f"關於「{item_description.split('，')[0]}」的回收方式？"
    options = "(A) 丟入一般垃圾\n(B) 依照材質分類回收\n(C) 直接沖進馬桶\n(D) 埋進土裡"
    correct_answer = "B"
    explanation = "大部分具備明確材質（如塑膠、金屬、紙類）的物品應清洗乾淨後交給資源回收車。"
    return question, options, correct_answer, explanation

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
    # 這裡建議你有一個首頁 index.html 用來上傳圖片
    return "回收專案運行中，請透過 POST /scan 上傳圖片。"

@app.route('/scan', methods=['POST'])
def scan_page():
    if 'file' not in request.files:
        return "未選擇檔案", 400
    
    file = request.files['file']
    if file.filename == '':
        return "檔名為空", 400

    # 儲存圖片
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    # 1. AI 辨識物品
    description = recognize_item(file_path)
    
    # 2. 生成題目
    q, opt, ans, expl = generate_recycling_quiz(description)
    
    # 3. 將正確答案存入 Session，供稍後比對
    session['correct_answer'] = ans
    session['explanation'] = expl

    # 4. 渲染你的 HTML 模板
    return render_template('result.html', 
                           username="環保小隊長", 
                           image_file=file.filename,
                           item_result=description,
                           question=q,
                           options=opt)

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    user_ans = data.get('answer')
    
    correct_ans = session.get('correct_answer', 'A')
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
