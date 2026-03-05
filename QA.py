from google import genai
from PIL import Image
import os
import re
import hashlib

# 建立 Gemini 客戶端
# 請確保 Render 的 Environment Variables 已設定 GOOGLE_API_KEY
client = genai.Client(
    api_key=os.environ.get("GOOGLE_API_KEY")
)

# 修正模型名稱：目前最穩定且快速的是 gemini-1.5-flash 或 gemini-2.0-flash
MODEL_NAME = "gemini-1.5-flash" 

HISTORY_FILE = "processed_history.txt"
XP_FILE = "user_xp.txt"

XP_REWARD_CORRECT = 50
XP_REWARD_WRONG = 10
XP_PER_LEVEL = 50

CHARACTERS = {
    0: "🌱 回收見習生",
    5: "🌿 綠色守護者",
    10: "🛡️ 地球防衛隊",
    15: "🔥 環保熱血戰士",
    20: "🌊 海洋淨化使者",
    25: "⛰️ 山林守護神",
    30: "🌍 行星指揮官",
    35: "🌟 銀河回收大師",
    40: "👑 宇宙環保霸主",
    50: "💎 傳說中的清潔神"
}

# --- 新增：等級計算函式 (修正之前的 ImportError) ---
def get_level(xp):
    """根據 XP 計算等級：每 50 點升一級，從 Lv.1 開始"""
    if xp is None:
        xp = 0
    return (xp // XP_PER_LEVEL) + 1

def get_image_hash(image_path):
    sha256_hash = hashlib.sha256()
    with open(image_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def is_duplicate_image(img_hash):
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        hashes = {line.strip() for line in f}
    return img_hash in hashes

def save_to_history(img_hash):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(img_hash + "\n")

def recognize_item(image_path):
    try:
        image = Image.open(image_path)
        prompt = """
        請辨識圖片中袋子裡的物品 (忽略袋子本身)
        請回答
        物品名稱:
        物品材質:
        使用繁體中文
        """
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, image]
        )
        return response.text
    except Exception as e:
        return f"辨識失敗: {str(e)}"

def generate_recycling_quiz(item_description):
    prompt = f"""
    根據以下物品出一道回收題目
    物品描述: {item_description}

    格式必須嚴格遵守：
    QUESTION_START 題目內容 QUESTION_END
    OPTIONS_START (A)選項1 (B)選項2 (C)選項3 (D)選項4 OPTIONS_END
    ANSWER_START A ANSWER_END
    EXPLANATION_START 解說內容 EXPLANATION_END
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        text = response.text

        # 增加安全取值判斷，避免正則匹配失敗導致崩潰
        q = re.search(r'QUESTION_START(.*?)QUESTION_END', text, re.S)
        o = re.search(r'OPTIONS_START(.*?)OPTIONS_END', text, re.S)
        a = re.search(r'ANSWER_START(.*?)ANSWER_END', text, re.S)
        e = re.search(r'EXPLANATION_START(.*?)EXPLANATION_END', text, re.S)

        return (
            q.group(1).strip() if q else "這件物品該如何回收？",
            o.group(1).strip() if o else "(A)丟垃圾桶 (B)資源回收 (C)廚餘 (D)大型廢棄物",
            a.group(1).strip() if a else "B",
            e.group(1).strip() if e else "請依照當地環保局規定回收。"
        )
    except Exception as e:
        return ("題目生成失敗", "(A) 錯誤 (B) 錯誤", "A", str(e))

def process_image(image_path):
    try:
        img_hash = get_image_hash(image_path)
        if is_duplicate_image(img_hash):
            return {
                "status": "duplicate",
                "message": "這張圖片已經測試過"
            }

        item = recognize_item(image_path)
        question, options, answer, explanation = generate_recycling_quiz(item)
        save_to_history(img_hash)

        return {
            "status": "success",
            "item": item,
            "question": question,
            "options": options,
            "answer": answer,
            "explanation": explanation
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
