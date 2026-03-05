import sqlite3
import os
import sys
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, session, jsonify, g
from datetime import datetime, timedelta, date
from functools import wraps

# 匯入你的自定義模組
from QA import recognize_item, generate_recycling_quiz, get_level, XP_REWARD_CORRECT, XP_REWARD_WRONG, get_image_hash
from auth import (register_user, login_user, get_user_xp_by_username, 
                  update_user_xp_by_username, is_duplicate_image_for_user, 
                  save_to_history_for_user, can_upload_today, increment_daily_upload,
                  get_remaining_uploads, DAILY_UPLOAD_LIMIT)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'reborn_secret_key_888')

# --- 路徑設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "NFCtag.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- 1. 資料庫基礎與初始化 ---
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
    print("--- 資料庫初始化完成 ---")

init_db()

# --- 2. 輔助函式 ---
def format_duration(seconds):
    if seconds is None or seconds < 0: return "00:00:00"
    seconds = int(seconds)
    return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# 直接從資料庫讀取數據供圖表使用 (不再需要 requests 抓網址)
def get_local_chart_data():
    weekly_seconds = {i: 0 for i in range(7)}
    weekly_sessions = {i: [] for i in range(7)}
    
    today = datetime.now()
    monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

    db = get_db()
    rows = db.execute("SELECT * FROM NFCtag WHERE endtime IS NOT NULL").fetchall()
    
    fmt = '%Y-%m-%d %H:%M:%S'
    for r in rows:
        try:
            start_dt = datetime.strptime(r['starttime'], fmt)
            if monday <= start_dt <= sunday:
                end_dt = datetime.strptime(r['endtime'], fmt)
                diff = (end_dt - start_dt).total_seconds()
                weekday = start_dt.weekday()
                
                weekly_seconds[weekday] += diff
                weekly_sessions[weekday].append({
                    'start': r['starttime'].split(' ')[1],
                    'end': r['endtime'].split(' ')[1],
                    'duration': format_duration(diff)
                })
        except: continue

    hours_list = [round(weekly_seconds[i] / 3600, 1) for i in range(7)]
    return hours_list, weekly_sessions

# --- 3. 路由設定 ---

@app.route('/healthz')
def healthz(): return "OK", 200

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        u, p = request.form.get('username', '').strip(), request.form.get('password', '')
        success, msg = login_user(u, p)
        if success:
            session['username'] = u
            return redirect(url_for('home'))
        return render_template('login.html', error=msg)
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    u, p, cp = request.form.get('username', '').strip(), request.form.get('password', ''), request.form.get('confirm_password', '')
    if p != cp: return render_template('login.html', error='密碼不一致')
    success, msg = register_user(u, p)
    return render_template('login.html', success=msg if success else None, error=None if success else msg)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login_page'))

# 遊戲首頁 (整合 NFC 圖表數據)
@app.route('/')
@login_required
def home():
    u = session['username']
    xp = get_user_xp_by_username(u)
    lvl = get_level(xp)
    chart_data, sessions_data = get_local_chart_data()
    return render_template('demo_baby_v4.html', username=u, xp=xp, level=lvl, 
                           chart_data=chart_data, sessions_data=sessions_data)

# NFC 更新介面 (給硬體或手機刷卡用)
@app.route('/nfc_update', methods=['GET', 'POST'])
def nfc_update():
    sno = request.args.get('sno') or request.form.get('sno')
    if not sno: return "Missing sno", 400
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    active = db.execute("SELECT id FROM NFCtag WHERE serialno = ? AND endtime IS NULL", (sno,)).fetchone()
    if active:
        db.execute("UPDATE NFCtag SET endtime = ? WHERE id = ?", (now, active['id']))
        msg = f"OK: {sno} Checked Out"
    else:
        db.execute("INSERT INTO NFCtag (serialno, starttime) VALUES (?, ?)", (sno, now))
        msg = f"OK: {sno} Checked In"
    db.commit()
    return msg

# 傳統表格檢視頁面
@app.route('/view')
@login_required
def view():
    db = get_db()
    rows = db.execute("SELECT * FROM NFCtag ORDER BY id DESC LIMIT 50").fetchall()
    data = []
    for r in rows:
        duration = "-"
        if r['endtime']:
            diff = (datetime.strptime(r['endtime'], '%Y-%m-%d %H:%M:%S') - 
                    datetime.strptime(r['starttime'], '%Y-%m-%d %H:%M:%S')).total_seconds()
            duration = format_duration(diff)
        data.append({**dict(r), "duration": duration})
    return render_template_string("<h1>NFC Logs</h1><table border='1'>{% for i in data %}<tr><td>{{i.serialno}}</td><td>{{i.starttime}}</td><td>{{i.duration}}</td></tr>{% endfor %}</table>", data=data)

# AI 掃描辨識
@app.route('/scan', methods=['GET', 'POST'])
@login_required
def scan_page():
    u = session['username']
    remaining = get_remaining_uploads(u)
    if request.method == 'POST':
        can, count = can_upload_today(u)
        if not can: return render_template('index.html', daily_limit_error=True, username=u, remaining_uploads=0, daily_limit=DAILY_UPLOAD_LIMIT)
        file = request.files.get('file')
        if file and file.filename:
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            img_hash = get_image_hash(path)
            if is_duplicate_image_for_user(u, img_hash):
                return render_template('index.html', duplicate_error=True, username=u, remaining_uploads=remaining, daily_limit=DAILY_UPLOAD_LIMIT)
            increment_daily_upload(u)
            item = recognize_item(path)
            q, opt, ans, expl = generate_recycling_quiz(item)
            session.update({'correct_answer': ans, 'explanation': expl, 'current_image_hash': img_hash})
            return render_template('result.html', image_file=file.filename, item_result=item, question=q, options=opt, username=u)
    return render_template('index.html', username=u, remaining_uploads=remaining, daily_limit=DAILY_UPLOAD_LIMIT)

@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    u = session['username']
    user_ans = request.json.get('answer', '').upper()
    correct = session.get('correct_answer')
    gained = XP_REWARD_CORRECT if user_ans == correct else XP_REWARD_WRONG
    old_xp = get_user_xp_by_username(u)
    new_xp = update_user_xp_by_username(u, gained)
    img_hash = session.get('current_image_hash')
    if img_hash: save_to_history_for_user(u, img_hash)
    return jsonify({
        'correct': user_ans == correct,
        'gained_xp': gained,
        'current_total_xp': new_xp,
        'leveled_up': get_level(new_xp) > get_level(old_xp),
        'new_level': get_level(new_xp),
        'explanation': session.get('explanation'),
        'correct_answer': correct
    })

@app.route('/uploads/<filename>')
def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
