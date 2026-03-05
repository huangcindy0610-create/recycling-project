from google import genai
from PIL import Image
import os
import re
import hashlib

# ==========================================
# 設定與初始化
# ==========================================
MY_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyDVv7Wt-S0e0G5rCXKiCR_6Iut1ZZFi58E")
client = genai.Client(api_key=MY_API_KEY)

# 使用穩定版模型，解決 404 問題
MODEL_NAME = "gemini-1.5-flash" 

XP_PER_LEVEL = 50

# --- 🎭 角色稱號清單 ---
CHARACTERS = {
    0:  "🌱 回收見習生",
    5:  "🌿 綠色守護者",
    10: "🛡️ 地球防衛隊",
    15: "🔥 環保熱血戰士",
    20: "🌊 海洋淨化使使",
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
    return (xp // XP_PER_LEVEL)

def get_current_character(level: int) -> str:
    unlocked_levels = sorted(CHARACTERS.keys(), reverse=True)
    for unlock_lvl in unlocked_levels:
        if level >= unlock_lvl:
            return CHARACTERS[unlock_lvl]
    return CHARACTERS[0]

def recognize_item(image_path: str) -> str:
    try:
        image = Image.open(image_path)
        prompt = """請辨識袋子裡的物品(忽略袋子)。用繁體中文簡潔回答：
        物品名稱: 
        物品材質: 
        注意：直接回答即可。"""
        response = client.models.generate_content(model=MODEL_NAME, contents=[prompt, image])
        return response.text
    except Exception as e:
        return f"AI 辨識失敗: {str(e)}"

def generate_recycling_quiz(item_description: str):
    # 植入你要求的九大類官方規定
    rules = "1.容器(鐵鋁玻璃塑膠紙)倒空沖洗壓扁 2.乾電池單獨回收 3.五大電器保持完整 4.資訊物品完整 5.照明光源防破 6.農藥三沖三洗 7.碎玻璃包覆標記。"
    prompt = f"""根據規定出題：{rules}\n物品：{item_description}\n格式：
    QUESTION_START 題目 QUESTION_END
    OPTIONS_START (A)... (B)... (C)... (D)... OPTIONS_END
    ANSWER_START A ANSWER_END
    EXPLANATION_START 解說 EXPLANATION_END"""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = response.text
        q = re.search(r'QUESTION_START\s*(.*?)\s*QUESTION_END', text, re.DOTALL)
        o = re.search(r'OPTIONS_START\s*(.*?)\s*OPTIONS_END', text, re.DOTALL)
        a = re.search(r'ANSWER_START\s*([A-D])\s*ANSWER_END', text, re.DOTALL | re.IGNORECASE)
        e = re.search(r'EXPLANATION_START\s*(.*?)\s*EXPLANATION_END', text, re.DOTALL)
        return q.group(1).strip(), o.group(1).strip(), a.group(1).upper().strip(), e.group(1).strip()
    except:
        return "如何回收此物？", "(A)丟垃圾 (B)資源回收", "B", "請依照當地規定。"
