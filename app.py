<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Baby Animation V4 - Reborn</title>
    <link rel="stylesheet" href="static/style_v4.css">
    <style>
        /* 這裡保留你所有的動畫 CSS 強制覆蓋 */
        .stat-highlight { color: #ff0000; }
        .cup-full { transition: clip-path 3s cubic-bezier(0.4, 0, 0.2, 1) !important; }
        .character {
            background-image: url('static/baby.png') !important;
            background-size: contain !important;
            background-repeat: no-repeat !important;
            background-position: bottom center !important;
            transition: background-image 0.3s ease;
        }
        .character.cat {
            background-image: url('static/cat.png') !important;
            background-size: 280% auto !important;
            background-position: 10% calc(100% + 130px) !important;
        }
        .character.fox {
            background-image: url('static/fox.png') !important;
            background-size: contain !important;
            background-position: center bottom !important;
        }
        .char-clipper { bottom: 125px !important; }
        .active .character { transition-delay: 0s !important; transform: translateY(120%); }
        .character.jump {
            transform: translateY(1%) !important;
            opacity: 1;
            transition: transform 0.4s cubic-bezier(0.2, 1, 0.3, 1) !important;
        }
        .character.cat.jump { animation: catReveal 0.8s ease forwards !important; transform: none !important; }
        @keyframes catReveal {
            0% { clip-path: inset(100% 0 0 0); transform: translateY(1%); }
            40% { clip-path: inset(60% 0 0 0); transform: translateY(1%); }
            100% { clip-path: inset(0 0 0 0); transform: translateY(1%); }
        }
        .bubble.show-bubble {
            opacity: 1; transform: scale(1);
            transition: 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            display: flex; flex-direction: column; justify-content: center; align-items: center;
        }
        .splash-container { position: absolute; bottom: 125px; left: 50%; transform: translate(-50%, 0); z-index: 60; }
        .droplet { position: absolute; width: 10px; height: 10px; background: #5A3A29; border-radius: 50%; }
        
        /* 導航箭頭樣式 */
        .nav-arrow, .nav-arrow-left {
            position: absolute; top: 55%; transform: translateY(-50%);
            font-size: 30px; color: rgba(90, 58, 41, 0.6); cursor: pointer;
            z-index: 90; background: rgba(255, 255, 255, 0.4);
            width: 40px; height: 60px; display: flex; align-items: center; justify-content: center;
            border-radius: 10px; backdrop-filter: blur(2px);
        }
        .nav-arrow { right: 15px; }
        .nav-arrow-left { left: 15px; display: none; }
        .nav-arrow-left.show { display: flex; }
        .unlock-hint { position: absolute; right: 5px; top: 49%; color: rgba(100, 100, 100, 0.7); font-size: 11px; font-weight: bold; }
    </style>
</head>

<body class="baby">
    <div class="user-bar" style="position: fixed; top: 0; width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 10px 20px; display: flex; justify-content: space-between; z-index: 1000;">
        <span class="username">👤 {{ username }}</span>
        <a href="/logout" style="color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 15px; font-size: 12px;">登出</a>
    </div>

    <div class="app-container" onclick="play()">
        <div class="header-box" style="margin-top: 50px;">Reborn</div>

        <div class="stats-box">
            <div class="exp-wrapper" style="width: 90%; margin: auto; cursor: pointer;">
                <div class="exp-header" style="display: flex; justify-content: space-between; font-weight: bold;">
                    <span>我的經驗值 (EXP)</span>
                    <span id="level-display" style="color:#FF9800;">Lvl. {{ level | default(1) }}</span>
                </div>
                <div class="exp-progress-container" style="background: #eee; height: 12px; border-radius: 6px; overflow: hidden; margin-top: 5px;">
                    <div class="exp-progress-fill" id="exp-fill" style="width: 0%; height: 100%; background: linear-gradient(90deg, #FFC107, #FF9800); transition: width 0.5s;"></div>
                </div>
            </div>
        </div>

        <div class="scene">
            <div class="char-clipper">
                <div class="character"></div>
            </div>
            <div class="cup-empty"></div>
            <div class="cup-full"></div>
        </div>

        <div class="bubble">
            <span id="encourage-msg" style="font-size: 13px;"></span>
            <a href="/scan" onclick="event.stopPropagation();" 
               style="text-decoration: none; font-size: 18px; cursor: pointer; margin-top: 10px; display: block; color: #5A3A29; font-weight: bold;">
                📷 拍照挑戰
            </a>
        </div>

        <div class="chart-title-outer" style="margin-top: 20px; text-align: center; font-weight: bold; color: #5A3A29;">本週咖啡時光 (小時)</div>
        <div class="chart-box" style="display: flex; padding: 15px; background: white; border-radius: 12px; margin: 10px auto; width: 90%; border: 1px solid #eee;">
            <div class="chart-y-axis" style="display: flex; flex-direction: column; justify-content: space-between; font-size: 11px; color: #999;">
                <span>6h</span><span>4h</span><span>2h</span><span>0h</span>
            </div>
            <div class="chart-content" style="flex: 1; margin-left: 10px; display: flex; flex-direction: column;">
                <div class="chart-bars" style="display: flex; justify-content: space-around; align-items: flex-end; height: 100px; border-bottom: 1px solid #ddd; border-left: 1px solid #ddd;">
                    {% for i in range(7) %}
                    {% set hours = chart_data[i] if chart_data else 0 %}
                    {% set pct = (hours / 6 * 100) if hours <= 6 else 100 %}
                    <div class="bar-group" style="flex: 1; display: flex; flex-direction: column; align-items: center;" onclick="showDayDetails({{ i }}, '星期{{ ['一','二','三','四','五','六','日'][i] }}')">
                        <div class="bar" style="height: {{ pct }}%; width: 60%; background: linear-gradient(180deg, #7B5544, #5A3A29); border-radius: 4px 4px 0 0;"></div>
                        <span style="font-size: 11px; margin-top: 5px;">{{ ['一','二','三','四','五','六','日'][i] }}</span>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <div class="nav-arrow-left" id="nav-arrow-left" onclick="event.stopPropagation(); goBack();">&#10094;</div>
        <div class="unlock-hint" id="unlock-hint">Lv.5 解鎖</div>
        <div class="nav-arrow" onclick="event.stopPropagation(); goForward();">&#10095;</div>
    </div>

    <div id="day-details-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 2000; justify-content: center; align-items: center;">
        <div style="background: white; padding: 20px; border-radius: 15px; width: 85%; max-width: 320px; text-align: center;">
            <h3 id="day-modal-title">記錄</h3>
            <div id="day-sessions-list" style="max-height: 250px; overflow-y: auto; margin: 15px 0;"></div>
            <button onclick="document.getElementById('day-details-modal').style.display='none'" style="background: #5A3A29; color: white; border: none; padding: 10px 25px; border-radius: 20px;">關閉</button>
        </div>
    </div>

    <script>
        const sessionsData = {{ sessions_data | tojson | safe }};
        const character = document.querySelector('.character');
        const bubble = document.querySelector('.bubble');
        const scene = document.querySelector('.scene');
        
        let currentExp = {{ xp | default(0) }};
        let currentLevel = {{ level | default(1) }};
        let isPlaying = false;

        // --- 初始化 UI ---
        function updateExpUI() {
            let levelExp = currentExp % 50;
            const pct = (levelExp / 50) * 100;
            document.getElementById('exp-fill').style.width = pct + '%';
            document.getElementById('level-display').innerText = 'Lvl. ' + currentLevel;
        }

        // --- 角色切換邏輯 ---
        const characters = ['baby', 'cat', 'fox'];
        const characterUnlockLevels = [0, 5, 10];
        let currentCharacterIndex = parseInt(localStorage.getItem('currentCharacterIndex')) || 0;

        function applyCharacterClass() {
            character.classList.remove('cat', 'fox');
            if (characters[currentCharacterIndex] !== 'baby') {
                character.classList.add(characters[currentCharacterIndex]);
            }
            updateArrowState();
        }

        function goForward() {
            if (currentCharacterIndex < characters.length - 1 && currentLevel >= characterUnlockLevels[currentCharacterIndex + 1]) {
                currentCharacterIndex++;
                saveState();
            } else {
                alert(`升到 Lv.${characterUnlockLevels[currentCharacterIndex + 1]} 即可解鎖！`);
            }
        }

        function goBack() {
            if (currentCharacterIndex > 0) {
                currentCharacterIndex--;
                saveState();
            }
        }

        function saveState() {
            localStorage.setItem('currentCharacterIndex', currentCharacterIndex);
            applyCharacterClass();
        }

        function updateArrowState() {
            document.getElementById('nav-arrow-left').classList.toggle('show', currentCharacterIndex > 0);
            const hint = document.getElementById('unlock-hint');
            if (currentCharacterIndex < 2 && currentLevel < characterUnlockLevels[currentCharacterIndex + 1]) {
                hint.innerText = `Lv.${characterUnlockLevels[currentCharacterIndex + 1]} 解鎖`;
                hint.style.display = 'block';
            } else {
                hint.style.display = 'none';
            }
        }

        // --- 動畫播放 ---
        function createSplash() {
            const splash = document.createElement('div');
            splash.className = 'splash-container';
            scene.appendChild(splash);
            for (let i = 0; i < 15; i++) {
                let d = document.createElement('div');
                d.className = 'droplet';
                splash.appendChild(d);
                const r = Math.random() * Math.PI * 2;
                const f = 40 + Math.random() * 60;
                const dx = Math.cos(r) * f;
                const dy = Math.sin(r) * f - 40;
                d.animate([
                    { transform: 'translate(0,0)', opacity: 1 },
                    { transform: `translate(${dx}px, ${dy}px)`, opacity: 0 }
                ], { duration: 800, fill: 'forwards' }).onfinish = () => d.remove();
            }
        }

        function play() {
            if (isPlaying || scene.classList.contains('active')) return;
            isPlaying = true;
            scene.classList.add('filling', 'active');
            setTimeout(() => {
                character.classList.add('jump');
                createSplash();
            }, 2950);
            setTimeout(() => {
                bubble.classList.add('show-bubble');
                generateEncouragement();
                isPlaying = false;
            }, 3500);
        }

        function generateEncouragement() {
            const msg = {{ chart_data | sum }} > 3 ? "回收小天才！✨" : "要記得做回收喔！☕";
            document.getElementById('encourage-msg').innerText = msg;
        }

        function showDayDetails(day, name) {
            const list = document.getElementById('day-sessions-list');
            document.getElementById('day-modal-title').innerText = `📅 ${name} 使用記錄`;
            const sessions = sessionsData[day] || [];
            list.innerHTML = sessions.length ? sessions.map(s => `
                <div style="background: #f9f9f9; padding: 10px; margin-bottom: 5px; border-radius: 8px; border: 1px solid #eee;">
                    <b>${s.start} - ${s.end}</b><br><small>時長: ${s.duration}</small>
                </div>
            `).join('') : "今天還沒喝咖啡喔～";
            document.getElementById('day-details-modal').style.display = 'flex';
        }

        window.onload = () => {
            updateExpUI();
            applyCharacterClass();
        };
    </script>
</body>
</html>
