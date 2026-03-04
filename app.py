from flask import Flask, render_template, request, redirect, url_for, session
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from functools import wraps

# ===== Flask App =====
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ===== Upload config =====
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ===== Health check =====
@app.route('/healthz')
def healthz():
    return "ok", 200

# ===== Example NFC API (保持原功能) =====
NFC_API_URL = "https://curvy-humorously-elna.ngrok-free.dev/view"

def get_weekly_usage():
    weekly_seconds = {i: 0 for i in range(7)}
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'ngrok-skip-browser-warning': 'true'}
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
        headers = {'User-Agent': 'Mozilla/5.0', 'ngrok-skip-browser-warning': 'true'}
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

# ===== Login decorator =====
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return wrapper

# ===== Auth routes (最簡化示範) =====
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        session['username'] = username
        return redirect(url_for('home'))
    return "Login Page (簡化示範)"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ===== Home =====
@app.route('/')
@login_required
def home():
    username = session['username']
    chart_data, sessions_data = get_chart_data()
    return f"Hello {username}! Weekly usage: {chart_data}"

# ===== Gunicorn entry =====
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
