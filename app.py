import sqlite3
import os
import sys
from flask import Flask, request, render_template_string, g
from datetime import datetime

app = Flask(__name__)

# 使用絕對路徑確保資料庫位置正確
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "NFCtag.db")

# --- 1. 資料庫基礎設定 ---
def get_db():
    if 'db' not in g:
        # 增加 timeout 防止資料庫鎖定
        g.db = sqlite3.connect(DB_NAME, timeout=10)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- 2. 初始化功能 (確保在生產環境中也能運行) ---
def init_db():
    try:
        print(f"--- 系統啟動：檢查資料庫於 {DB_NAME} ---")
        conn = sqlite3.connect(DB_NAME)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS NFCtag (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serialno TEXT NOT NULL,
                starttime TIMESTAMP,
                endtime TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        print("--- 資料庫初始化成功 ---")
    except Exception as e:
        print(f"--- 資料庫初始化失敗: {str(e)} ---")
        # 這裡不退出，讓 Flask 嘗試啟動以便查看錯誤日誌

init_db()

def format_duration(seconds):
    if seconds is None or seconds < 0: return "00:00:00"
    seconds = int(seconds)
    return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

# --- 3. HTML 模板 ---
BASE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>NFC 監控系統</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, sans-serif; line-height: 1.6; padding: 20px; background: #f0f2f5; color: #333; }
        .container { max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        nav { margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #eee; }
        nav a { text-decoration: none; color: #007bff; font-weight: bold; margin-right: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }
        th, td { padding: 12px; border: 1px solid #eee; text-align: center; }
        th { background: #f8f9fa; }
        .status-in { background-color: #fff9db; }
        .status-done { background-color: #ebfbee; }
    </style>
</head>
<body>
    <div class="container">
        <nav><a href="/view">📋 即時清單</a><a href="/stat">📊 統計數據</a></nav>
        {% block content %}{% endblock %}
    </div>
</body>
</html>
'''

# --- 4. 路由設定 ---

@app.route('/healthz')
def healthz():
    return "OK", 200

@app.route('/')
def index():
    return '<script>window.location.href="/view"</script>'

@app.route('/nfc_update', methods=['GET'])
def nfc_update():
    sno = request.args.get('sno')
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

@app.route('/view')
def view():
    db = get_db()
    rows = db.execute("SELECT * FROM NFCtag ORDER BY id DESC LIMIT 50").fetchall()
    data = []
    fmt = '%Y-%m-%d %H:%M:%S'
    for r in rows:
        duration, cls = "-", "status-in"
        if r['endtime']:
            try:
                diff = (datetime.strptime(r['endtime'], fmt) - datetime.strptime(r['starttime'], fmt)).total_seconds()
                duration, cls = format_duration(diff), "status-done"
            except:
                pass
        data.append({**dict(r), "duration": duration, "class": cls})

    content = '''
    <h2>NFC 即時監控</h2>
    <table>
        <tr><th>序號</th><th>開始</th><th>結束</th><th>耗時</th></tr>
        {% for i in data %}
        <tr class="{{ i.class }}">
            <td>{{ i.serialno }}</td><td>{{ i.starttime }}</td>
            <td>{{ i.endtime or '進行中...' }}</td><td><b>{{ i.duration }}</b></td>
        </tr>
        {% endfor %}
    </table>
    '''
    return render_template_string(BASE_HTML.replace('{% block content %}{% endblock %}', content), data=data)

@app.route('/stat')
def stat():
    db = get_db()
    rows = db.execute("SELECT starttime, endtime FROM NFCtag WHERE endtime IS NOT NULL").fetchall()
    total_sec = 0
    for r in rows:
        try:
            diff = (datetime.strptime(r['endtime'], '%Y-%m-%d %H:%M:%S') - datetime.strptime(r['starttime'], '%Y-%m-%d %H:%M:%S')).total_seconds()
            total_sec += diff
        except:
            pass
            
    content = f'''
    <h2>數據統計</h2>
    <div style="background: #e7f5ff; padding: 20px; border-radius: 8px;">
        <p>已完成次數：<span style="font-size: 1.5em; color: #1c7ed6;">{len(rows)}</span></p>
        <p>累計總工時：<span style="font-size: 1.5em; color: #d6336c;">{format_duration(total_sec)}</span></p>
    </div>
    '''
    return render_template_string(BASE_HTML.replace('{% block content %}{% endblock %}', content))

# --- 5. 埠口綁定 (Render 關鍵) ---
if __name__ == '__main__':
    # 這裡確保本地執行時也能運作
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
