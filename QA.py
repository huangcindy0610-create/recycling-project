import google.generativeai as genai
from PIL import Image
import os
import re
import hashlib

# 統一使用 google-generativeai 套件
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)
MODEL_NAME = "gemini-1.5-flash"
model = genai.GenerativeModel(MODEL_NAME)

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
        response = model.generate_content(["請辨識圖片中的物品名稱與材質，用繁體中文回答。", img])
        return response.text.strip()
    except Exception as e:
        return f"辨識失敗: {str(e)}"

def generate_recycling_quiz(item_description):
    try:
        prompt = f"針對{item_description}出一個回收選擇題。格式：QUESTION_START 題目 QUESTION_END OPTIONS_START (A) (B) OPTIONS_END ANSWER_START 答案字母 ANSWER_END EXPLANATION_START 解析 EXPLANATION_END"
        response = model.generate_content(prompt)
        text = response.text
        q = re.search(r'QUESTION_START(.*?)QUESTION_END', text, re.S).group(1).strip()
        o = re.search(r'OPTIONS_START(.*?)OPTIONS_END', text, re.S).group(1).strip()
        a = re.search(r'ANSWER_START\s*([A-D])\s*ANSWER_END', text, re.I).group(1).upper()
        e = re.search(r'EXPLANATION_START(.*?)EXPLANATION_END', text, re.S).group(1).strip()
        return q, o, a, e
    except:
        return "如何回收？", "(A)資源回收 (B)一般垃圾", "A", "請依規定處理。"
