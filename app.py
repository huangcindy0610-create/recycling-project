from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, jsonify
import os
from functools import wraps
from QA import (recognize_item, generate_recycling_quiz, get_level, 
                XP_REWARD_CORRECT, XP_REWARD_WRONG, get_image_hash)
from auth import (register_user, login_user, get_user_xp_by_username, 
                  update_user_xp_by_username, is_duplicate_image_for_user, 
                  save_to_history_for_user, can_upload_today, increment_daily_upload,
                  get_remaining_uploads, DAILY_UPLOAD_LIMIT)
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
# 設定圖片上傳存檔的路徑 (使用絕對路徑比較保險)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# NFC 監控 API URL
NFC_API_URL = "https://curvy-humorously-elna.ngrok-free.dev/view"

# === 使用時長計算 ===
def get_weekly_usage():
    """
    從 NFC API 抓取數據，計算本週每天的使用時長（小時）
    返回: dict {0: 星期一時數, 1: 星期二時數, ..., 6: 星期日時數}
    """
    # 初始化每天的秒數
    weekly_seconds = {i: 0 for i in range(7)}  # 0=週一, 6=週日
    
    try:
        # 抓取 NFC 監控頁面
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'ngrok-skip-browser-warning': 'true'  # 跳過 ngrok 警告
        }
        response = requests.get(NFC_API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 解析 HTML 表格
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        
        if not table:
            return weekly_seconds
        
        rows = table.find_all('tr')[1:]  # 跳過表頭
        
        # 計算本週的日期範圍 (週一到週日)
        today = datetime.now()
        # 找到本週一的日期
        monday = today - timedelta(days=today.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        # 本週日的結束
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                try:
                    # 解析開始時間
                    start_time_str = cols[2].text.strip()
                    start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
                    
                    # 檢查是否在本週範圍內
                    if monday <= start_time <= sunday:
                        # 解析使用時長 (HH:mm:ss)
                        duration_str = cols[4].text.strip()
                        h, m, s = map(int, duration_str.split(':'))
                        total_seconds = h * 3600 + m * 60 + s
                        
                        # 計算是星期幾 (0=週一, 6=週日)
                        weekday = start_time.weekday()
                        weekly_seconds[weekday] += total_seconds
                except Exception as e:
                    continue
        
    except Exception as e:
        print(f"抓取 NFC 數據失敗: {e}")
    
    # 將秒數轉換為小時（保留一位小數）
    weekly_hours = {day: round(seconds / 3600, 1) for day, seconds in weekly_seconds.items()}
    
    return weekly_hours

def get_weekly_sessions():
    """
    從 NFC API 抓取數據，取得本週每天的詳細使用記錄
    返回: dict {0: [{start, end, duration}, ...], 1: [...], ...}
    """
    # 初始化每天的記錄列表
    weekly_sessions = {i: [] for i in range(7)}  # 0=週一, 6=週日
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'ngrok-skip-browser-warning': 'true'
        }
        response = requests.get(NFC_API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        
        if not table:
            return weekly_sessions
        
        rows = table.find_all('tr')[1:]
        
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                try:
                    start_time_str = cols[2].text.strip()
                    end_time_str = cols[3].text.strip()
                    duration_str = cols[4].text.strip()
                    
                    start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
                    
                    if monday <= start_time <= sunday:
                        weekday = start_time.weekday()
                        weekly_sessions[weekday].append({
                            'start': start_time_str.split(' ')[1],  # 只取時間部分
                            'end': end_time_str.split(' ')[1] if ' ' in end_time_str else end_time_str,
                            'duration': duration_str
                        })
                except Exception as e:
                    continue
        
    except Exception as e:
        print(f"抓取 NFC 詳細數據失敗: {e}")
    
    return weekly_sessions

def get_chart_data():
    """
    取得圖表所需的數據格式
    返回: tuple (list [週一時數, ...], dict {0: [sessions], ...})
    """
    weekly_usage = get_weekly_usage()
    weekly_sessions = get_weekly_sessions()
    # 轉換為列表格式 [週一, 週二, ..., 週日]
    hours_list = [weekly_usage[i] for i in range(7)]
    # 轉換 sessions 為列表格式
    sessions_list = [weekly_sessions[i] for i in range(7)]
    return hours_list, sessions_list

# === 登入驗證裝飾器 ===
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# === 認證相關路由 ===

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        success, message = login_user(username, password)
        
        if success:
            session['username'] = username
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error=message)
    
    # 如果已登入，直接跳轉首頁
    if 'username' in session:
        return redirect(url_for('home'))
    
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # 檢查密碼確認
    if password != confirm_password:
        return render_template('login.html', error='兩次密碼輸入不一致')
    
    success, message = register_user(username, password)
    
    if success:
        return render_template('login.html', success='註冊成功！請登入')
    else:
        return render_template('login.html', error=message)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login_page'))

# === 遊戲相關路由 ===

# 1. 首頁：顯示 Baby 動畫 (帶有 EXP 資訊和週間使用時長)
@app.route('/')
@login_required
def home():
    username = session['username']
    current_xp = get_user_xp_by_username(username)
    level = get_level(current_xp)
    
    # 取得本週使用時長數據和詳細記錄
    chart_data, sessions_data = get_chart_data()
    
    return render_template('demo_baby_v4.html', 
                           xp=current_xp, 
                           level=level, 
                           username=username,
                           chart_data=chart_data,
                           sessions_data=sessions_data)

# 2. 辨識頁面：處理上傳與生成題目
@app.route('/scan', methods=['GET', 'POST'])
@login_required
def scan_page():
    username = session['username']
    remaining = get_remaining_uploads(username)
    
    if request.method == 'POST':
        # --- 檢查每日上傳限制 ---
        can_upload, upload_count = can_upload_today(username)
        if not can_upload:
            return render_template('index.html', 
                                   daily_limit_error=True, 
                                   username=username,
                                   remaining_uploads=0,
                                   daily_limit=DAILY_UPLOAD_LIMIT)
        
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)

        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            
            # --- 檢查重複圖片 (使用用戶專屬歷史) ---
            try:
                img_hash = get_image_hash(filepath)
                if is_duplicate_image_for_user(username, img_hash):
                    # 返回帶有錯誤訊息的頁面
                    return render_template('index.html', 
                                           duplicate_error=True, 
                                           username=username,
                                           remaining_uploads=remaining,
                                           daily_limit=DAILY_UPLOAD_LIMIT)
            except Exception as e:
                return f"圖片處理錯誤: {e}"
            
            # --- 增加上傳次數 ---
            increment_daily_upload(username)
            
            # 呼叫 QA.py 的功能
            item_result = recognize_item(filepath)
            
            if "失敗" in item_result or "錯誤" in item_result:
                 return f"發生錯誤: {item_result}"

            question, options, answer, explanation = generate_recycling_quiz(item_result)

            # Store quiz state in session for verification
            session['correct_answer'] = answer
            session['explanation'] = explanation
            session['current_image'] = file.filename
            session['current_image_hash'] = img_hash  # Save hash for later

            # 這裡把 image_file 傳給 result.html
            return render_template('result.html', 
                                   image_file=file.filename,
                                   item_result=item_result,
                                   question=question,
                                   options=options,
                                   username=username)

    return render_template('index.html', 
                           username=username,
                           remaining_uploads=remaining,
                           daily_limit=DAILY_UPLOAD_LIMIT)

# 3. 處理回答
@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    username = session['username']
    data = request.json
    user_answer = data.get('answer', '').upper()
    correct_answer = session.get('correct_answer', '')
    explanation = session.get('explanation', '')
    
    result = {
        'correct': False,
        'message': '',
        'gained_xp': 0,
        'current_total_xp': 0,
        'leveled_up': False,
        'new_level': 0,
        'explanation': explanation,
        'correct_answer': correct_answer
    }

    if user_answer == correct_answer:
        result['correct'] = True
        result['gained_xp'] = XP_REWARD_CORRECT
        result['message'] = '答對了！'
    else:
        result['correct'] = False
        result['gained_xp'] = XP_REWARD_WRONG
        result['message'] = '答錯了...'

    # Update backend stats (使用用戶專屬的 XP)
    old_xp = get_user_xp_by_username(username)
    old_level = get_level(old_xp)
    
    new_total_xp = update_user_xp_by_username(username, result['gained_xp'])
    new_level = get_level(new_total_xp)
    
    result['current_total_xp'] = new_total_xp
    result['new_level'] = new_level
    
    if new_level > old_level:
        result['leveled_up'] = True

    # 答題完成後，將圖片 hash 存入用戶專屬的歷史紀錄
    img_hash = session.get('current_image_hash')
    if img_hash:
        save_to_history_for_user(username, img_hash)

    return jsonify(result)

# 4. 讀取圖片路由
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 5. API: 取得用戶資訊
@app.route('/api/user_info')
@login_required
def get_user_info():
    username = session['username']
    xp = get_user_xp_by_username(username)
    level = get_level(xp)
    return jsonify({
        'username': username,
        'xp': xp,
        'level': level
    })
if __name__ == '__main__':
    print("[OK] Running via Gunicorn")

