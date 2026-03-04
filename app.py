from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, jsonify
import os
from functools import wraps
from QA import (
    recognize_item, generate_recycling_quiz, get_level,
    XP_REWARD_CORRECT, XP_REWARD_WRONG, get_image_hash
)
from auth import (
    register_user, login_user, get_user_xp_by_username,
    update_user_xp_by_username, is_duplicate_image_for_user,
    save_to_history_for_user, can_upload_today,
    increment_daily_upload, get_remaining_uploads,
    DAILY_UPLOAD_LIMIT
)
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# =========================
# Flask App
# =========================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# =========================
# Upload config
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# =========================
# Health check (給 Render)
# =========================
@app.route('/healthz')
def healthz():
    return "ok", 200

# =========================
# NFC API
# =========================
NFC_API_URL = "https://curvy-humorously-elna.ngrok-free.dev/view"

# =========================
# 使用時長計算
# =========================
def get_weekly_usage():
    weekly_seconds = {i: 0 for i in range(7)}
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
            return weekly_seconds

        rows = table.find_all('tr')[1:]
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                try:
                    start_time = datetime.strptime(cols[2].text.strip(), '%Y-%m-%d %H:%M:%S')
                    if monday <= start_time <= sunday:
                        h, m, s = map(int, cols[4].text.strip().split(':'))
                        weekly_seconds[start_time.weekday()] += h*3600 + m*60 + s
                except:
                    pass
    except Exception as e:
        print("NFC error:", e)

    return {d: round(s / 3600, 1) for d, s in weekly_seconds.items()}

def get_weekly_sessions():
    weekly_sessions = {i: [] for i in range(7)}
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
                    start = datetime.strptime(cols[2].text.strip(), '%Y-%m-%d %H:%M:%S')
                    if monday <= start <= sunday:
                        weekly_sessions[start.weekday()].append({
                            "start": cols[2].text.split(" ")[1],
                            "end": cols[3].text.split(" ")[1] if cols[3].text else "-",
                            "duration": cols[4].text
                        })
                except:
                    pass
    except Exception as e:
        print("NFC detail error:", e)

    return weekly_sessions

def get_chart_data():
    usage = get_weekly_usage()
    sessions = get_weekly_sessions()
    return [usage[i] for i in range(7)], [sessions[i] for i in range(7)]

# =========================
# Login decorator
# =========================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return wrapper

# =========================
# Auth routes
# =========================
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        ok, msg = login_user(
            request.form.get('username', '').strip(),
            request.form.get('password', '')
        )
        if ok:
            session['username'] = request.form['username']
            return redirect(url_for('home'))
        return render_template('login.html', error=msg)
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    ok, msg = register_user(
        request.form.get('username', '').strip(),
        request.form.get('password', '')
    )
    return render_template('login.html', success=msg if ok else None, error=None if ok else msg)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# =========================
# Home (唯一的 /)
# =========================
@app.route('/')
@login_required
def home():
    username = session['username']
    xp = get_user_xp_by_username(username)
    level = get_level(xp)
    chart_data, sessions_data = get_chart_data()

    return render_template(
        'demo_baby_v4.html',
        username=username,
        xp=xp,
        level=level,
        chart_data=chart_data,
        sessions_data=sessions_data
    )

# =========================
# Gunicorn entry
# =========================
if __name__ == '__main__':
    print("[OK] app loaded (Gunicorn mode)")
