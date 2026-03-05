import sqlite3
import os
import sys
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, session, jsonify, g
from datetime import datetime, timedelta
from functools import wraps

# 匯入自定義模組 (請確保 QA.py 裡有 get_current_character 函式)
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

# --- 1. 資料庫核心 ---
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
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS NFCtag (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    serialno TEXT NOT NULL, 
                    starttime TIMESTAMP, 
                    endtime TIMESTAMP
                )
            ''')
        print("--- [系統] 資料庫初始化成功 ---")
    except Exception as e:
        print(f"--- [錯誤] 資料庫初始化失敗: {e} ---")

init_db()

def format_duration_str(seconds):
    """將秒數轉為 00:00:00 格式"""
    seconds = int(seconds)
    return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

# --- 2. 數據計算 (供 Baby 介面圖表與彈窗使用) ---
def get_local_chart_data():
    """從資料庫讀取本週數據，並格式化為前端所需格式"""
    weekly_seconds = {i: 0 for i in range(7)}
    weekly_sessions = {i: [] for i in range(7)}
    today = datetime.now()
    # 取得本週一的日期
    monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    
    db = get_db()
    # 只抓取已結束且屬於本週的紀錄
    rows = db.execute("SELECT * FROM NFCtag WHERE endtime IS NOT NULL ORDER BY starttime ASC").fetchall()
    
    for r in rows:
        try:
            start_dt = datetime.strptime(r['starttime'], '%Y-%m-%d %H:%M:%S')
            if start_dt >= monday:
                end_dt = datetime.strptime(r['endtime'], '%Y-%m-%d %H:%M:%S')
                diff = (end_dt - start_dt).total_seconds()
                weekday = start_dt.weekday() # 0 是週一
                
                weekly_seconds[weekday] += diff
                weekly_sessions[weekday].append({
                    'start': r['starttime'].split(' ')[1], # 只拿時間
                    'end': r['endtime'].split(' ')[1],
                    'duration': format_duration_str(diff)
                })
        except:
            continue
    
    # 圖表用的數據：[週一小時, 週二小時...]
    hours_list = [round(weekly_seconds[i] / 3600, 2) for i in range(7)]
    return hours_list, weekly_sessions

# --- 3. 權限檢查器 ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# --- 4. 路由設定 ---

@app.route('/healthz')
def healthz(): return "OK", 200

# 遊戲首頁 (整合稱號、XP 與 NFC 圖表)
@app.route('/')
@login_required
def home():
    u = session['username']
    xp = get_user_xp_by_username(u)
    lvl = get_level(xp)
    
    # 根據等級獲取角色稱號 (例如：🌱 回收見習生)
    title = get_current_character(lvl)
    
    chart_data, sessions_data = get_local_chart_data()
    return render_template('demo_baby_v4.html', 
                           username=u, 
                           xp=xp, 
                           level=lvl, 
                           title=title, 
                           chart_data=chart_data, 
                           sessions_data=sessions_data)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        success, msg = login_user(u, p)
        if success:
            session['username'] = u
            return redirect(url_for('home'))
        return render_template('login.html', error=msg)
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    u = request.form.get('username', '').strip()
    p = request.form.get('password', '')
    cp = request.form.get('confirm_password', '')
    if p != cp:
        return render_template('login.html', error='兩次密碼輸入不一致')
    success, msg = register_user(u, p)
    return render_template('login.html', success=msg if success else None, error=None if success else msg)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login_page'))

# 辨識頁面
@app.route('/scan', methods=['GET', 'POST'])
@login_required
def scan_page():
    u = session['username']
    remaining = get_remaining_uploads(u)
    if request.method == 'POST':
        can, count = can_upload_today(u)
        if not can:
            return render_template('index.html', daily_limit_error=True, username=u, remaining_uploads=0, daily_limit=DAILY_UPLOAD_LIMIT)
        
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

# 提交答案
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
    if img_hash:
        save_to_history_for_user(u, img_hash)
        
    return jsonify({
        'correct': user_ans == correct,
        'gained_xp': gained,
        'current_total_xp': new_xp,
        'leveled_up': get_level(new_xp) > get_level(old_xp),
        'new_level': get_level(new_xp),
        'explanation': session.get('explanation'),
        'correct_answer': correct
    })

# NFC Tag 觸發路由 (硬體請求此網址)
@app.route('/nfc_update', methods=['GET', 'POST'])
def nfc_update():
    sno = request.args.get('sno') or request.form.get('sno')
    if not sno: return "Missing sno", 400
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    # 檢查該序號是否有未完成的紀錄
    active = db.execute("SELECT id FROM NFCtag WHERE serialno = ? AND endtime IS NULL", (sno,)).fetchone()
    
    if active:
        db.execute("UPDATE NFCtag SET endtime = ? WHERE id = ?", (now, active['id']))
        msg = f"OK: {sno} Checked Out"
    else:
        db.execute("INSERT INTO NFCtag (serialno, starttime) VALUES (?, ?)", (sno, now))
        msg = f"OK: {sno} Checked In"
    
    db.commit()
    return msg

# 舊版查看紀錄頁面 (僅作為備查)
@app.route('/view')
@login_required
def view():
    db = get_db()
    rows = db.execute("SELECT * FROM NFCtag ORDER BY id DESC LIMIT 50").fetchall()
    return f"<h1>NFC 即時紀錄</h1><p><a href='/'>返回首頁</a></p>{str([dict(r) for r in rows])}"

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Render 環境預設使用 10000 埠口
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
