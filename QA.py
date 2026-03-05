import google.generativeai as genai
from PIL import Image
import os
import re
import hashlib

# ==========================================
# 初始化 Gemini (統一使用標準 SDK)
# ==========================================
API_KEY = os.environ.get("GEMINI_API_KEY", "你的備用KEY")
genai.configure(api_key=API_KEY)
MODEL_NAME = "gemini-1.5-flash"
model = genai.GenerativeModel(MODEL_NAME)

# 遊戲平衡
XP_REWARD_CORRECT = 50
XP_REWARD_WRONG = 10
XP_PER_LEVEL = 50

def get_image_hash(image_path):
    with open(image_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def get_level(xp):
    return (xp or 0) // XP_PER_LEVEL

def recognize_item(image_path):
    try:
        img = Image.open(image_path)
        prompt = "請辨識圖片中的物品。用繁體中文簡潔回答：物品名稱、主要材質。不要使用特殊符號。"
        response = model.generate_content([prompt, img])
        return response.text.strip()
    except Exception as e:
        return f"AI 辨識失敗: {str(e)}"

def generate_recycling_quiz(item_description):
    prompt = f"根據此物品：{item_description}，出一個回收知識選擇題。格式必須包含：QUESTION_START 題目 QUESTION_END OPTIONS_START (A) (B) OPTIONS_END ANSWER_START 答案字母 ANSWER_END EXPLANATION_START 解析 EXPLANATION_END"
    try:
        response = model.generate_content(prompt)
        text = response.text
        q = re.search(r'QUESTION_START(index.html)?(.*?)QUESTION_END', text, re.S).group(2).strip()
        o = re.search(r'OPTIONS_START(.*?)OPTIONS_END', text, re.S).group(1).strip()
        a = re.search(r'ANSWER_START\s*([A-D])\s*ANSWER_END', text, re.I).group(1).upper()
        e = re.search(r'EXPLANATION_START(.*?)EXPLANATION_END', text, re.S).group(1).strip()
        return q, o, a, e
    except:
        return "如何處理此類回收？", "(A)清洗後回收 (B)直接丟棄", "A", "保持回收物乾淨是基本原則。"
