from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, jsonify
import os
import requests
from functools import wraps
from datetime import datetime, timedelta
# 確保 QA.py 與 auth.py 存在
from QA import (recognize_item, generate_recycling_quiz, get_level, 
                XP_REWARD_CORRECT, XP_REWARD_WRONG, get_image_hash)
from auth import (register_user, login_user, get_user_xp_by_username, 
                  update_user_xp_by_username, is_duplicate_image_for_user, 
                  save_to_history_for_user, can_upload_today, increment_daily_upload,
                  get_remaining_uploads, DAILY_UPLOAD_LIMIT)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_123')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 後端 API 網址
NFC_API_URL = "https://recycling-project-1.onrender.com/view"

# === NFC 數據抓取 ===
def get_weekly_usage():
    weekly_seconds = {i: 0 for i in range(7)}
    try:
        response = requests.get(NFC_API_URL, timeout=10)
        data = response.json()
        today = datetime.now()
        monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        for item in data:
            if item.get('start') and item.get('end'):
                st = datetime.strptime(item['start'], '%Y-%m-%d %H:%M:%S')
                if st >= monday:
                    et = datetime.strptime(item['end'], '%Y-%m-%d %H:%M:%S')
                    weekly_seconds[st.weekday()] += (et - st).total_seconds()
    except: pass
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
                        'end': item['end'].split(' ')[1] if item.get('end') else "ING",
                        'duration': dur
                    })
    except: pass
    return weekly_sessions

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session: return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# === 路由設定 ===
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
        return render_template('login.html', error='密碼不一致')
    success, msg = register_user(user, pwd)
    return render_template('login.html', success='註冊成功' if success else None, error=msg if not success else None)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def home():
    username = session['username']
    xp = get_user_xp_by_username(username)
    usage = get_weekly_usage()
    sessions = get_weekly_sessions()
    return render_template('demo_baby_v4.html', xp=xp, level=get_level(xp), 
                           username=username, chart_data=[usage[i] for i in range(7)], 
                           sessions_data=[sessions[i] for i in range(7)])

@app.route('/scan', methods=['GET', 'POST'])
@login_required
def scan_page():
    username = session['username']
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            item_result = recognize_item(filepath)
            q, o, a, e = generate_recycling_quiz(item_result)
            session.update({'correct_answer': a, 'explanation': e})
            return render_template('result.html', image_file=file.filename, item_result=item_result, 
                                   question=q, options=o, username=username)
    return render_template('index.html', username=username, remaining_uploads=get_remaining_uploads(username))

@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    user_ans = request.json.get('answer', '').upper()
    correct_ans = session.get('correct_answer')
    xp = XP_REWARD_CORRECT if user_ans == correct_ans else XP_REWARD_WRONG
    new_xp = update_user_xp_by_username(session['username'], xp)
    return jsonify({'correct': user_ans == correct_ans, 'gained_xp': xp, 'current_total_xp': new_xp})

@app.route('/healthz')
def healthz(): return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
