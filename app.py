from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, jsonify
import os
import requests
from functools import wraps
from datetime import datetime, timedelta
# 確保 QA.py 與 auth.py 在同一個目錄下
from QA import (recognize_item, generate_recycling_quiz, get_level, 
                XP_REWARD_CORRECT, XP_REWARD_WRONG, get_image_hash)
from auth import (register_user, login_user, get_user_xp_by_username, 
                  update_user_xp_by_username, is_duplicate_image_for_user, 
                  save_to_history_for_user, can_upload_today, increment_daily_upload,
                  get_remaining_uploads, DAILY_UPLOAD_LIMIT)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_123')

# 設定圖片上傳路徑
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 後端資料庫 API 網址
NFC_API_URL = "https://recycling-project-1.onrender.com/view"

# === 修正：使用 JSON 抓取數據 (不再使用 BeautifulSoup) ===
def get_weekly_usage():
    weekly_seconds = {i: 0 for i in range(7)}
    try:
        response = requests.get(NFC_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json() # 取得 JSON 列表

        today = datetime.now()
        monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        
        for item in data:
            if item.get('start') and item.get('end'):
                try:
                    start_t = datetime.strptime(item['start'], '%Y-%m-%d %H:%M:%S')
                    if start_t >= monday:
                        end_t = datetime.strptime(item['end'], '%Y-%m-%d %H:%M:%S')
                        weekly_seconds[start_t.weekday()] += (end_t - start_t).total_seconds()
                except: continue
    except Exception as e:
        print(f"NFC 數據抓取失敗: {e}")
    return {day: round(sec / 3600, 1) for day, sec in weekly_seconds.items()}

def get_weekly_sessions():
    weekly_sessions = {i: [] for i in range(7)}
    try:
        response = requests.get(NFC_API_URL, timeout=10)
        data = response.json()
        today = datetime.now()
        monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

        for item in data:
            if item.get('start'):
                try:
                    start_t = datetime.strptime(item['start'], '%Y-%m-%d %H:%M:%S')
                    if start_t >= monday:
                        duration = "-"
                        if item.get('end'):
                            diff = datetime.strptime(item['end'], '%Y-%m-%d %H:%M:%S') - start_t
                            h, m = divmod(int(diff.total_seconds()), 3600)
                            m, s = divmod(m, 60)
                            duration = f"{h:02}:{m:02}:{s:02}"
                        
                        weekly_sessions[start_t.weekday()].append({
                            'start': item['start'].split(' ')[1],
                            'end': item['end'].split(' ')[1] if item.get('end') else "ING",
                            'duration': duration
                        })
                except: continue
    except: pass
    return weekly_sessions

def get_chart_data():
    usage = get_weekly_usage()
    sessions = get_weekly_sessions()
    return [usage[i] for i in range(7)], [sessions[i] for i in range(7)]

# === 路由設定 (Login, Home, Scan 等) ===
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session: return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
@login_required
def home():
    username = session['username']
    xp = get_user_xp_by_username(username)
    chart_data, sessions_data = get_chart_data()
    return render_template('demo_baby_v4.html', xp=xp, level=get_level(xp), 
                           username=username, chart_data=chart_data, sessions_data=sessions_data)

@app.route('/scan', methods=['GET', 'POST'])
@login_required
def scan_page():
    username = session['username']
    if request.method == 'POST':
        can_up, count = can_upload_today(username)
        if not can_up: return render_template('index.html', daily_limit_error=True)
        
        file = request.files.get('file')
        if file and file.filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            img_hash = get_image_hash(filepath)
            
            if is_duplicate_image_for_user(username, img_hash):
                return render_template('index.html', duplicate_error=True)
            
            increment_daily_upload(username)
            item_result = recognize_item(filepath)
            if "失敗" in item_result: return f"AI 錯誤: {item_result}"
            
            q, o, a, e = generate_recycling_quiz(item_result)
            session.update({'correct_answer': a, 'explanation': e, 'current_image_hash': img_hash})
            return render_template('result.html', image_file=file.filename, item_result=item_result, 
                                   question=q, options=o, username=username)
    return render_template('index.html', username=username, remaining_uploads=get_remaining_uploads(username))

@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    username = session['username']
    user_ans = request.json.get('answer', '').upper()
    correct_ans = session.get('correct_answer')
    gained_xp = XP_REWARD_CORRECT if user_ans == correct_ans else XP_REWARD_WRONG
    
    new_xp = update_user_xp_by_username(username, gained_xp)
    if session.get('current_image_hash'):
        save_to_history_for_user(username, session['current_image_hash'])
    
    return jsonify({'correct': user_ans == correct_ans, 'gained_xp': gained_xp, 'current_total_xp': new_xp})

@app.route('/healthz')
def healthz(): return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
