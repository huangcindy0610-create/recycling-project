from google import genai
from PIL import Image
import os
import re
import hashlib

# ==========================================
# 設定與初始化
# ==========================================
# 優先讀取 Render 環境變數中的 Key
MY_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyDVv7Wt-S0e0G5rCXKiCR_6Iut1ZZFi58E")

# 建立客戶端
client = genai.Client(api_key=MY_API_KEY)

# 【關鍵修正】在某些 SDK 版本中，模型名稱需要加上 'models/' 前綴或保持純淨
# 如果 gemini-1.5-flash 報 404，這裡改用最標準的字串
MODEL_NAME = "gemini-1.5-flash" 

# --- 🎮 遊戲平衡設定 (補齊變數防止 app.py 崩潰) ---
XP_REWARD_CORRECT = 50
XP_REWARD_WRONG = 10
XP_PER_LEVEL = 50

# --- 🎭 角色稱號清單 ---
CHARACTERS = {
    0:  "🌱 回收見習生",
    5:  "🌿 綠色守護者",
    10: "🛡️ 地球防衛隊",
    15: "🔥 環保熱血戰士",
    20: "🌊 海洋淨化使者",
    25: "⛰️ 山林守護神",
    30: "🌍 行星指揮官",
    35: "🌟 銀河回收大師",
    40: "👑 宇宙環保霸主",
    50: "💎 傳說中的清潔神",
}

def get_image_hash(image_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(image_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_level(xp: int) -> int:
    if xp is None: xp = 0
    return (xp // XP_PER_LEVEL)

def get_current_character(level: int) -> str:
    unlocked_levels = sorted(CHARACTERS.keys(), reverse=True)
    for unlock_lvl in unlocked_levels:
        if level >= unlock_lvl:
            return CHARACTERS[unlock_lvl]
    return CHARACTERS[0]

def recognize_item(image_path: str) -> str:
    """AI 辨識 - 增加容錯處理"""
    try:
        if not os.path.exists(image_path):
            return "錯誤：找不到圖片檔案"
        
        image = Image.open(image_path)
        prompt = "請辨識圖片中袋子裡的物品。用繁體中文簡潔回答：物品名稱、物品材質。不要使用符號。"
        
        # 修正：確保調用時不帶多餘的 API 版本前綴
        response = client.models.generate_content(
            model=MODEL_NAME, 
            contents=[prompt, image]
        )
        return response.text
    except Exception as e:
        # 如果 1.5-flash 還是失敗，嘗試備用方案
        return f"AI 辨識暫時無法連線，請檢查 API Key 權限。({str(e)})"

def generate_recycling_quiz(item_description: str):
    prompt = f"""根據此物品設計回收選擇題：{item_description}
    格式：
    QUESTION_START 題目內容 QUESTION_END
    OPTIONS_START (A)... (B)... (C)... (D)... OPTIONS_END
    ANSWER_START A ANSWER_END
    EXPLANATION_START 解說內容 EXPLANATION_END"""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = response.text
        q = re.search(r'QUESTION_START\s*(.*?)\s*QUESTION_END', text, re.DOTALL).group(1).strip()
        o = re.search(r'OPTIONS_START\s*(.*?)\s*OPTIONS_END', text, re.DOTALL).group(1).strip()
        a = re.search(r'ANSWER_START\s*([A-D])\s*ANSWER_END', text, re.DOTALL | re.IGNORECASE).group(1).upper().strip()
        e = re.search(r'EXPLANATION_START\s*(.*?)\s*EXPLANATION_END', text, re.DOTALL).group(1).strip()
        return q, o, a, e
    except:
        return "此物品如何回收？", "(A)回收 (B)垃圾", "A", "請依規定回收。"
