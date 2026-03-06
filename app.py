from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, jsonify
import os
import requests
from functools import wraps
from datetime import datetime, timedelta
# --- 新增處理圖片的套件 ---
from PIL import Image
import pillow_heif

# 確保 QA.py 與 auth.py 與此檔案在同一目錄
from QA import (recognize_item, generate_recycling_quiz, get_level, 
                XP_REWARD_CORRECT, XP_REWARD_WRONG, get_image_hash)
from auth import (register_user, login_user, get_user_xp_by_username, 
                  update_user_xp_by_username, is_duplicate_image_for_user, 
                  save_to_history_for_user, can_upload_today, increment_daily_upload,
                  get_remaining_uploads, DAILY_UPLOAD_LIMIT)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_123')

# 設定圖片上傳存檔的路徑
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 後端 API 網址 (recycling-project-1)
NFC_API_URL = "https://recycling-project-1.onrender.com/view"

# === 1. NFC 數據處理函數 ===
def get_weekly_usage():
    weekly_seconds = {i: 0 for i in range(7)}
    try:
        response = requests.get(NFC_API_URL, timeout=10)
        data = response.json()
        if not isinstance(data, list): return weekly_seconds
        today = datetime.now()
        monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        for item in data:
            if item.get('start') and item.get('end'):
                try:
                    st = datetime.strptime(item['start'], '%Y-%m-%d %H:%M:%S')
                    if st >= monday:
                        et = datetime.strptime(item['end'], '%Y-%m-%d %H:%M:%S')
                        weekly_seconds[st.weekday()] += (et - st).total_seconds()
                except: continue
    except Exception as e:
        print(f"時數計算失敗: {e}")
    return {day: round(sec / 3600, 1) for day, sec in weekly_seconds.items()}

def get_weekly_sessions():
    weekly_sessions = {i: [] for i in range(7)}
    try:
        response = requests.get(NFC_API_URL, timeout=10)
        data = response.json()
        if not isinstance(data, list): return weekly_sessions
        today = datetime.now()
        monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        for item in data:
            if item.get('start'):
                try:
                    st = datetime.strptime(item['start'], '%Y-%m-%d %H:%M:%S')
                    if st >= monday:
                        dur = "-"
                        if item.get('end'):
                            diff = datetime.strptime(item['end'], '%Y-%m-%d %H:%M:%S') - st
                            h, m = divmod(int(diff.total_seconds()), 3600)
                            m, s = divmod(m, 60)
                            dur = f"{h:02}:{m:02}:{s:02}"
                        weekly_sessions[st.weekday()].append({
                            'start': item['start'].split(' ')[1],
                            'end': item['end'].split(' ')[1] if item.get('end') else "進行中",
                            'duration': dur
                        })
                except: continue
    except: pass
    return weekly_sessions

def get_chart_data():
    try:
        usage = get_weekly_usage()
        sessions = get_weekly_sessions()
        hours_list = [usage.get(i, 0.0) for i in range(7)]
        sessions_list = [sessions.get(i, []) for i in range(7)]
        return hours_list, sessions_list
    except Exception as e:
        print(f"圖表封裝錯誤: {e}")
        return [0.0]*7, [[] for _ in range(7)]

# === 2. 登入裝飾器 ===
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# === 3. 核心路由 ===
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        user = request.form.get('username', '').strip()
        pwd = request.form.get('password', '')
        success, msg = login_user(user, pwd)
        if success:
            session['username'] = user
            return redirect(url_for('home'))
        return render_template('login.html', error=msg)
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    user = request.form.get('username', '').strip()
    pwd = request.form.get('password', '')
    if pwd != request.form.get('confirm_password', ''):
        return render_template('login.html', error='密碼輸入不一致')
    success, msg = register_user(user, pwd)
    return render_template('login.html', 
                           success='註冊成功，請登入！' if success else None, 
                           error=None if success else msg)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def home():
    username = session['username']
    xp = get_user_xp_by_username(username)
    hours_list, sessions_list = get_chart_data()
    return render_template('demo_baby_v4.html', 
                           xp=xp, 
                           level=get_level(xp), 
                           username=username, 
                           chart_data=hours_list, 
                           sessions_data=sessions_list)

@app.route('/scan', methods=['GET', 'POST'])
@login_required
def scan_page():
    username = session['username']
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # --- 新增：處理 HEIC 轉檔邏輯 ---
            if filename.lower().endswith('.heic'):
                try:
                    heif_file = pillow_heif.read_heif(filepath)
                    image = Image.frombytes(
                        heif_file.mode, 
                        heif_file.size, 
                        heif_file.data,
                        "raw",
                    )
                    # 更改副檔名為 .jpg
                    new_filename = filename.rsplit('.', 1)[0] + ".jpg"
                    new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                    image.save(new_filepath, "JPEG")
                    
                    # 更新後續辨識使用的路徑與檔名
                    filepath = new_filepath
                    filename = new_filename
                except Exception as e:
                    return f"HEIC 轉檔失敗: {e}"
            # --------------------------

            # AI 辨識與題目生成 (傳入的是處理過的 filepath)
            item_result = recognize_item(filepath)
            if "失敗" in item_result or "忙碌" in item_result:
                return f"AI 辨識發生錯誤: {item_result}"
                
            q, o, a, e = generate_recycling_quiz(item_result)
            session.update({'correct_answer': a, 'explanation': e})
            
            return render_template('result.html', 
                                   image_file=filename, 
                                   item_result=item_result, 
                                   question=q, 
                                   options=o, 
                                   username=username)
                                   
    return render_template('index.html', 
                           username=username, 
                           remaining_uploads=get_remaining_uploads(username))

@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    user_ans = request.json.get('answer', '').upper()
    correct_ans = session.get('correct_answer')
    xp = XP_REWARD_CORRECT if user_ans == correct_ans else XP_REWARD_WRONG
    new_xp = update_user_xp_by_username(session['username'], xp)
    return jsonify({
        'correct': user_ans == correct_ans, 
        'gained_xp': xp, 
        'current_total_xp': new_xp
    })

@app.route('/healthz')
def healthz():
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
