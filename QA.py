from google import genai
from PIL import Image
import os
import re
import hashlib

client = genai.Client(
    api_key=os.environ.get("GOOGLE_API_KEY")
)

MODEL_NAME = "gemini-2.5-flash"

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


def generate_recycling_quiz(item_description):

    prompt = f"""
根據以下物品出一道回收題目

物品描述:
{item_description}

格式：

QUESTION_START
題目
QUESTION_END

OPTIONS_START
(A) ...
(B) ...
(C) ...
(D) ...
OPTIONS_END

ANSWER_START
A
ANSWER_END

EXPLANATION_START
說明
EXPLANATION_END
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    text = response.text

    question = re.search(r'QUESTION_START(.*?)QUESTION_END', text, re.S)
    options = re.search(r'OPTIONS_START(.*?)OPTIONS_END', text, re.S)
    answer = re.search(r'ANSWER_START(.*?)ANSWER_END', text, re.S)
    explanation = re.search(r'EXPLANATION_START(.*?)EXPLANATION_END', text, re.S)

    return (
        question.group(1).strip(),
        options.group(1).strip(),
        answer.group(1).strip(),
        explanation.group(1).strip()
    )


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
