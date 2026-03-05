import sqlite3
import os
import sys
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, session, jsonify, g
from datetime import datetime, timedelta
from functools import wraps

# 匯入自定義模組
from QA import (recognize_item, generate_recycling_quiz, get_level, 
                get_current_character, XP_REWARD_CORRECT, XP_REWARD_WRONG, get_image_hash)
from auth import (register_user, login_user, get_user_xp_by_username, 
                  update_user_xp_by_username, is_duplicate_image_for_user, 
                  save_to_history_for_user, can_upload_today, increment_daily_upload,
                  get_remaining_uploads, DAILY_UPLOAD_LIMIT)

app = Flask(__name__)
# 建議將此 key 設為固定字串，避免部署時自動登出
app.secret_key = os.environ.get('SECRET_KEY', 'reborn_secret_key_2026')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "NFCtag.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- 1. 資料庫基礎 ---
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_NAME, timeout=10)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS NFCtag (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                serialno TEXT NOT NULL, 
                starttime TIMESTAMP, 
                endtime TIMESTAMP
            )
        ''')
init_db()

# --- 2. 數據計算 (連動圖表與彈窗) ---
def get_local_chart_data():
    """連動資料庫，產出長條圖時數與點擊後的詳細卡片資料"""
    weekly_seconds = {i: 0 for i in range(7)}
    weekly_sessions = {i: [] for i in range(7)}
    monday = (datetime.now() - timedelta(days=datetime.now().weekday())).replace(hour=0, minute=0, second=0)
    db = get_db()
    rows = db.execute("SELECT * FROM NFCtag WHERE endtime IS NOT NULL ORDER BY starttime ASC").fetchall()
    for r in rows:
        try:
            sd = datetime.strptime(r['starttime'], '%Y-%m-%d %H:%M:%S')
            if sd >= monday:
                diff = (datetime.strptime(r['endtime'], '%Y-%m-%d %H:%M:%S') - sd).total_seconds()
                w = sd.weekday()
                weekly_seconds[w] += diff
                weekly_sessions[w].append({
                    'start': r['starttime'].split(' ')[1],
                    'end': r['endtime'].split(' ')[1],
                    'duration': f"{int(diff//3600):02}:{int((diff%3600)//60):02}:{int(diff%60):02}"
                })
        except: continue
    return [round(weekly_seconds[i] / 3600, 2) for i in range(7)], weekly_sessions

# --- 3. 權限檢查器 ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# --- 4. 路由設定 ---

# 【重要】Render 健康檢查路由
@app.route('/healthz')
def healthz():
    return "OK", 200

@app.route('/')
@login_required
def home():
    u = session['username']
    xp = get_user_xp_by_username(u)
    lvl = get_level(xp)
    title = get_current_character(lvl) # 稱號連動
    chart, sessions = get_local_chart_data() # 數據連動
    return render_template('demo_baby_v4.html', username=u, xp=xp, level=lvl, title=title, chart_data=chart, sessions_data=sessions)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        u, p = request.form.get('username', '').strip(), request.form.get('password', '')
        # login_user 回傳 (True/False, message)
        res = login_user(u, p)
        if res[0]:
            session['username'] = u
            return redirect(url_for('home'))
        return render_template('login.html', error=res[1])
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/scan', methods=['GET', 'POST'])
@login_required
def scan_page():
    u = session['username']
    if request.method == 'POST':
        file = request.files.get('file')
        if file:
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            increment_daily_upload(u)
            item = recognize_item(path)
            q, o, a, e = generate_recycling_quiz(item)
            session.update({'correct_answer': a, 'explanation': e, 'current_image_hash': get_image_hash(path)})
            return render_template('result.html', image_file=file.filename, item_result=item, question=q, options=o, username=u)
    return render_template('index.html', username=u, remaining_uploads=get_remaining_uploads(u), daily_limit=DAILY_UPLOAD_LIMIT)

@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    ans = request.json.get('answer', '').upper()
    correct = session.get('correct_answer')
    gained = XP_REWARD_CORRECT if ans == correct else XP_REWARD_WRONG
    new_xp = update_user_xp_by_username(session['username'], gained)
    hash_val = session.get('current_image_hash')
    if hash_val: save_to_history_for_user(session['username'], hash_val)
    
    return jsonify({
        'correct': ans == correct, 
        'gained_xp': gained, 
        'new_level': get_level(new_xp), 
        'explanation': session.get('explanation'), 
        'correct_answer': correct
    })

@app.route('/nfc_update')
def nfc_update():
    sno = request.args.get('sno')
    if not sno: return "Missing sno", 400
    db = get_db()
    active = db.execute("SELECT id FROM NFCtag WHERE serialno = ? AND endtime IS NULL", (sno,)).fetchone()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if active:
        db.execute("UPDATE NFCtag SET endtime = ? WHERE id = ?", (now, active['id']))
    else:
        db.execute("INSERT INTO NFCtag (serialno, starttime) VALUES (?, ?)", (sno, now))
    db.commit()
    return "OK"

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- 5. 啟動設定 ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
