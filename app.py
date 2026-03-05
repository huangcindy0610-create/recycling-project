import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session
from datetime import datetime
from functools import wraps

# ===== Flask App =====
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ===== SQLite DB config =====
BASE_DIR = os.path.abspath(os.path.dirname(__file__))import os
import sqlite3
from flask import Flask, render_template_string, request
from datetime import datetime

# ===== Flask App =====
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ===== SQLite DB config =====
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, "NFCtag.db")


# ===== 初始化資料庫 (Render / Gunicorn 也會執行) =====
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS NFCtag (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serialno TEXT NOT NULL,
                starttime TEXT,
                endtime TEXT
            )
        ''')
        conn.commit()


init_db()


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


# ===== NFC update (寫入資料庫) =====
@app.route('/nfc_update')
def nfc_update():

    sno = request.args.get('sno')

    if not sno:
        return "Missing sno", 400

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM NFCtag WHERE serialno=? AND endtime IS NULL",
            (sno,)
        )

        row = cursor.fetchone()

        if row:
            cursor.execute(
                "UPDATE NFCtag SET endtime=? WHERE id=?",
                (now, row[0])
            )
            msg = f"{sno} Checked Out"
        else:
            cursor.execute(
                "INSERT INTO NFCtag (serialno,starttime,endtime) VALUES (?,?,NULL)",
                (sno, now)
            )
            msg = f"{sno} Checked In"

        conn.commit()

    return msg


# ===== 即時監控頁面 =====
@app.route('/view')
def view():

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id,serialno,starttime,endtime FROM NFCtag ORDER BY id DESC"
        )

        rows = cursor.fetchall()

    data = []
    fmt = '%Y-%m-%d %H:%M:%S'

    for r in rows:

        duration = "-"
        color = "yellow"

        if r[3]:
            start = datetime.strptime(r[2], fmt)
            end = datetime.strptime(r[3], fmt)

            seconds = (end - start).total_seconds()
            duration = format_duration(seconds)

            color = "lightgreen"

        data.append({
            "id": r[0],
            "sno": r[1],
            "start": r[2],
            "end": r[3] or "In Progress...",
            "duration": duration,
            "color": color
        })

    html = '''
    <html>
    <head>
    <meta http-equiv="refresh" content="2">
    <style>
    body{font-family:sans-serif}
    table{width:100%;border-collapse:collapse}
    th,td{padding:10px;border:1px solid #ccc;text-align:center}
    </style>
    </head>

    <body>

    <h2>NFC Tag 即時監控清單</h2>

    <table>

    <tr style="background:#333;color:white">
    <th>ID</th>
    <th>Serial No</th>
    <th>Start</th>
    <th>End</th>
    <th>Duration</th>
    </tr>

    {% for i in data %}

    <tr style="background:{{i.color}}">

    <td>{{i.id}}</td>
    <td>{{i.sno}}</td>
    <td>{{i.start}}</td>
    <td>{{i.end}}</td>
    <td><b>{{i.duration}}</b></td>

    </tr>

    {% endfor %}

    </table>

    </body>
    </html>
    '''

    return render_template_string(html, data=data)


# ===== 統計頁 =====
@app.route('/stat')
def stat():

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT starttime,endtime FROM NFCtag WHERE endtime IS NOT NULL"
        )

        rows = cursor.fetchall()

    total_seconds = 0

    fmt = '%Y-%m-%d %H:%M:%S'

    for r in rows:
        start = datetime.strptime(r[0], fmt)
        end = datetime.strptime(r[1], fmt)

        total_seconds += (end - start).total_seconds()

    total_time = format_duration(total_seconds)

    html = '''

    <html>

    <body style="font-family:sans-serif;padding:20px">

    <h2>NFC 統計</h2>

    <p>完成筆數: <b>{{count}}</b></p>

    <p>總時間: <b>{{total}}</b></p>

    <a href="/view">查看列表</a>

    </body>

    </html>

    '''

    return render_template_string(
        html,
        count=len(rows),
        total=total_time
    )


# ===== 本地執行 (Render 不會用到) =====
if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=int(os.environ.get("PORT", 10000)),
        debug=True
    )
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

# ===== Gunicorn entry =====
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)

