import os
import sqlite3
from flask import Flask, render_template, render_template_string, request, redirect, url_for, session
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

# ===== SQLite DB config =====
DB_NAME = os.path.join(BASE_DIR, "NFCtag.db")

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS NFCtag (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serialno TEXT NOT NULL,
                starttime TIMESTAMP,
                endtime TIMESTAMP
            )
        ''')
        conn.commit()

# ===== Format duration =====
def format_duration(seconds):
    if seconds is None:
        return "-"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:02}"

# ===== Health check =====
@app.route('/healthz')
def healthz():
    return "ok", 200

# ===== NFC database routes =====
@app.route('/nfc_update', methods=['GET'])
def nfc_update():
    sno = request.args.get('sno')
    if not sno:
        return "Missing sno", 400

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM NFCtag WHERE serialno = ? AND endtime IS NULL", (sno,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE NFCtag SET endtime = ? WHERE id = ?", (now, row[0]))
            msg = f"OK: {sno} Checked Out"
        else:
            cursor.execute("INSERT INTO NFCtag (serialno, starttime, endtime) VALUES (?, ?, NULL)", (sno, now))
            msg = f"OK: {sno} Checked In"
        conn.commit()
    return msg

@app.route('/view')
def view():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, serialno, starttime, endtime FROM NFCtag ORDER BY id DESC")
        rows = cursor.fetchall()

    data = []
    fmt = '%Y-%m-%d %H:%M:%S'
    for r in rows:
        diff_str = "-"
        color = "yellow"
        if r[3]:
            start = datetime.strptime(r[2], fmt)
            end = datetime.strptime(r[3], fmt)
            diff_str = format_duration((end - start).total_seconds())
            color = "lightgreen"
        data.append({
            "id": r[0], "sno": r[1], "start": r[2],
            "end": r[3] or "In Progress...", "duration": diff_str, "color": color
        })

    html = '''
    <html>
        <head><meta http-equiv="refresh" content="1">
        <style>
            table { width: 100%; border-collapse: collapse; font-family: sans-serif; }
            th, td { padding: 10px; border: 1px solid #ccc; text-align: center; }
        </style>
        </head>
        <body>
            <h2>NFC Tag 即時監控清單</h2>
            <table>
                <tr style="background-color: #333; color: white;">
                    <th>ID</th><th>Serial No</th><th>Start Time</th><th>End Time</th><th>Duration (HH:mm:ss)</th>
                </tr>
                {% for item in data %}
                <tr style="background-color: {{ item.color }};">
                    <td>{{ item.id }}</td><td>{{ item.sno }}</td><td>{{ item.start }}</td>
                    <td>{{ item.end }}</td><td><b>{{ item.duration }}</b></td>
                </tr>
                {% endfor %}
            </table>
        </body>
    </html>
    '''
    return render_template_string(html, data=data)

@app.route('/stat')
def stat():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT starttime, endtime FROM NFCtag WHERE endtime IS NOT NULL")
        rows = cursor.fetchall()

    total_seconds = 0
    fmt = '%Y-%m-%d %H:%M:%S'
    for r in rows:
        start = datetime.strptime(r[0], fmt)
        end = datetime.strptime(r[1], fmt)
        total_seconds += (end - start).total_seconds()

    total_time_str = format_duration(total_seconds)

    html = '''
    <html>
        <head><meta http-equiv="refresh" content="1"></head>
        <body style="font-family: sans-serif; padding: 20px;">
            <h2>NFC 統計數據</h2>
            <div style="border: 2px solid #333; padding: 15px; display: inline-block;">
                <p>已完成總筆數：<span style="font-size: 1.5em; color: blue;">{{ count }}</span></p>
                <p>總累計工時：<span style="font-size: 1.5em; color: red;">{{ total_time }}</span> (HH:mm:ss)</p>
            </div>
            <br><br><a href="/view">查看詳細清單</a>
        </body>
    </html>
    '''
    return render_template_string(html, count=len(rows), total_time=total_time_str)

# ===== NFC API + Chart functionality =====
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

# ===== Auth routes (簡化) =====
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
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
