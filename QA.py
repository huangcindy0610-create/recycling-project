"""
使用 Gemini 辨識袋子裡物品並產生回收選擇題 (含重複圖片偵測 + 經驗值系統 + 角色解鎖)
"""

from google import genai
from PIL import Image
import os
import re
import sys
import hashlib

# ==========================================
# 使用 Render 的環境變數讀取 API Key
# ==========================================
client = genai.Client(
    api_key=os.environ.get("GOOGLE_API_KEY")
)

MODEL_NAME = "gemini-2.5-flash"

# 檔案設定
HISTORY_FILE = "processed_history.txt"
XP_FILE = "user_xp.txt"

# --- 🎮 遊戲平衡設定 ---
XP_REWARD_CORRECT = 50
XP_REWARD_WRONG = 10
XP_PER_LEVEL = 50       # 50 XP 升一級

# --- 🎭 角色稱號清單 (每 5 等解鎖) ---
# 你可以在這裡自由新增更多角色
CHARACTERS = {
    0:  "🌱 回收見習生",       # 初始角色 (Lv.0)
    5:  "🌿 綠色守護者",       # Lv.5 解鎖
    10: "🛡️ 地球防衛隊",       # Lv.10 解鎖
    15: "🔥 環保熱血戰士",     # Lv.15 解鎖
    20: "🌊 海洋淨化使者",     # Lv.20 解鎖
    25: "⛰️ 山林守護神",       # Lv.25 解鎖
    30: "🌍 行星指揮官",       # Lv.30 解鎖
    35: "🌟 銀河回收大師",     # Lv.35 解鎖
    40: "👑 宇宙環保霸主",     # Lv.40 解鎖
    50: "💎 傳說中的清潔神",   # Lv.50 解鎖
}

def get_image_hash(image_path: str) -> str:
    """計算圖片雜湊值"""
    sha256_hash = hashlib.sha256()
    with open(image_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def is_duplicate_image(img_hash: str) -> bool:
    """檢查圖片是否重複"""
    if not os.path.exists(HISTORY_FILE):
        return False
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        existing_hashes = {line.strip() for line in f}
    return img_hash in existing_hashes

def save_to_history(img_hash: str):
    """儲存圖片紀錄"""
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(img_hash + "\n")

# --- 經驗值與角色系統 ---
def get_user_xp() -> int:
    """讀取經驗值"""
    if not os.path.exists(XP_FILE):
        return 0
    try:
        with open(XP_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except:
        return 0

def update_user_xp(gained_xp: int) -> int:
    """更新經驗值"""
    current_xp = get_user_xp()
    new_total = current_xp + gained_xp
    with open(XP_FILE, "w", encoding="utf-8") as f:
        f.write(str(new_total))
    return new_total

def get_level(xp: int) -> int:
    """計算等級 (0 XP = Lv.0)"""
    return (xp // XP_PER_LEVEL)

def get_next_level_progress(xp: int) -> str:
    """計算升級進度"""
    current_level_xp = xp % XP_PER_LEVEL
    remaining = XP_PER_LEVEL - current_level_xp
    return f"{current_level_xp}/{XP_PER_LEVEL} (再 {remaining} XP 升級)"

def get_current_character(level: int) -> str:
    """
    根據目前等級取得對應的角色稱號
    邏輯：找出等級小於等於目前等級的最高階角色
    """
    # 將所有解鎖等級由大到小排序
    unlocked_levels = sorted(CHARACTERS.keys(), reverse=True)
    
    for unlock_lvl in unlocked_levels:
        if level >= unlock_lvl:
            return CHARACTERS[unlock_lvl]
    
    return CHARACTERS[0] # 預設回傳第一個
# ---------------------------

def recognize_item(image_path: str) -> str:
    """AI 辨識"""
    try:
        if not os.path.exists(image_path):
            return "錯誤：找不到圖片檔案"
        image = Image.open(image_path)
    except Exception as e:
        return f"讀取圖片失敗: {e}"

    prompt = """請仔細觀察這張圖片，辨識袋子裡面放著的物品。
    請只針對「物品」回答（忽略袋子本身），用繁體中文簡潔回答：
    物品可能是: (填寫物品名稱)
    物品材質: (填寫材質)
    
    注意：不要使用任何特殊符號如 * 或 - ，直接回答即可。
    """
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=[prompt, image])
        return response.text
    except Exception as e:
        return f"AI 辨識失敗: {e}"

def generate_recycling_quiz(item_description: str) -> tuple[str, str, str]:
    """AI 出題 - 依據環保署官方規定"""
    
    # 環保署官方回收規定參考資料
    recycling_rules = """
    【台灣環保署官方回收規定 - 9大類36項】
    
    1. 容器類：鐵、鋁、玻璃、塑膠(1-7號)、紙容器(含鋁箔包、紙餐具)
       - 通用規則：「倒空、沖洗、壓扁」
       - 紙餐具規則：「清、分、疊」(清殘渣、分開放、疊合)
       
    2. 塑膠辨識碼：
       - 1號PET：寶特瓶
       - 2號HDPE：鮮奶瓶、清潔劑瓶
       - 3號PVC：保鮮膜、水管
       - 4號LDPE：塑膠袋
       - 5號PP：豆漿瓶、微波容器
       - 6號PS：養樂多瓶、保麗龍
       - 7號OTHER：其他材質
       
    3. 乾電池：錳鋅、鹼錳、鋰電池、鎳鎘、鎳氫、鈕扣電池
       - 務必從電子產品中取出單獨回收
       
    4. 電子電器五大類：電視機、電冰箱、洗衣機、冷氣機、電風扇
       - 保持完整，不可私自拆解
       
    5. 資訊物品：筆電、桌機、顯示器、印表機、鍵盤、平板
       - 保持完整，不可私自拆解
       
    6. 照明光源：螢光燈管、省電燈泡、LED燈
       - 小心輕放避免破碎
       
    7. 農藥容器：需「三沖三洗」後回收
    
    8. 玻璃容器：若破碎需用厚紙包覆並註明「碎玻璃」
    
    【非回收項目】陶瓷、木製家具、菸蒂、紙尿褲、髒污塑膠袋
    """
    
    prompt = f"""根據以下物品描述，請依照台灣環保署官方規定設計一道回收選擇題。

{recycling_rules}

物品描述: {item_description}

設計規則:
1. 題目必須依照上述官方規定出題
2. 四個選項 (A/B/C/D)：只有一個正確答案
3. 選項要有誘答性，但正確答案必須符合官方規定
4. 解說要簡短有力，不超過2句話
5. 不要使用任何特殊符號如 * 或 - 或 ** 等

格式範例：
QUESTION_START
題目...
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
✅ 正確做法說明
💡 小技巧
EXPLANATION_END
    """ 
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = response.text
        
        question_match = re.search(r'QUESTION_START\s*(.*?)\s*QUESTION_END', text, re.DOTALL)
        options_match = re.search(r'OPTIONS_START\s*(.*?)\s*OPTIONS_END', text, re.DOTALL)
        answer_match = re.search(r'ANSWER_START\s*([A-Da-d])\s*ANSWER_END', text, re.DOTALL)
        explanation_match = re.search(r'EXPLANATION_START\s*(.*?)\s*EXPLANATION_END', text, re.DOTALL)
        
        question = question_match.group(1).strip() if question_match else "題目解析失敗"
        options = options_match.group(1).strip() if options_match else "選項解析失敗"
        answer = answer_match.group(1).upper().strip() if answer_match else "?"
        explanation = explanation_match.group(1).strip() if explanation_match else "解說解析失敗"
        
        # Changed: Return structured data instead of pre-formatted string
        return question, options, answer, explanation
    except Exception as e:
        return "產生題目失敗", "選項產生失敗", "?", str(e)

def main():
    if len(sys.argv) < 2:
        print(f"❌ 錯誤：未提供圖片路徑")
        print(f"使用方式: python {sys.argv[0]} <圖片路徑>")
        return
    
    image_path = sys.argv[1]

    # --- 顯示玩家狀態 (含角色) ---
    current_xp = get_user_xp()
    level = get_level(current_xp)
    character_title = get_current_character(level)
    progress_str = get_next_level_progress(current_xp)
    
    print("\n" + "="*50)
    print(f"👤 玩家：{character_title}") 
    print(f"🎖️ 等級：Lv.{level}")
    print(f"📊 經驗：{progress_str}")
    print("="*50)

    # 檢查重複
    print(f"🔒 正在檢查圖片是否重複...")
    try:
        current_hash = get_image_hash(image_path)
        if is_duplicate_image(current_hash):
            print("\n" + "!"*50)
            print("⚠️  這張圖片之前已經測試過了！")
            print("請更換一張新的圖片再來挑戰。")
            print("!"*50 + "\n")
            return
    except Exception as e:
        print(f"❌ 雜湊計算失敗: {e}")
        return
    
    # AI 流程
    print(f"🔍 圖片檢查通過，正在使用 AI 辨識物品...")
    item_result = recognize_item(image_path)
    if "失敗" in item_result or "錯誤" in item_result:
        print(f"❌ {item_result}")
        return

    print("\n=== 辨識結果 ===")
    print(item_result)
    
    print("\n📚 正在產生回收選擇題...")
    question, options, answer, explanation = generate_recycling_quiz(item_result)
    
    if question == "產生題目失敗":
        print(f"❌ 題目產生失敗: {explanation}")
        return

    print("\n" + "="*50)
    print("          ♻️ 回收知識小測驗 ♻️")
    print("="*50 + "\n")
    print(f"📝 題目：\n{question}\n\n🔘 選項：\n{options}")
    
    # 作答
    print("\n" + "-"*50)
    while True:
        try:
            user_answer = input("請輸入你的答案 (A/B/C/D): ").strip().upper()
            if user_answer in ['A', 'B', 'C', 'D']:
                break
            print("❌ 請輸入有效的選項 (A/B/C/D)")
        except KeyboardInterrupt:
            print("\n程式已中斷")
            sys.exit()
    
    # 結算
    print("\n" + "="*50)
    
    gained_xp = 0
    gained_xp = 0
    if user_answer == answer:
        gained_xp = XP_REWARD_CORRECT
        print("🎉 答對了！太棒了！")
        print(f"✨ 獲得經驗值：+{gained_xp} XP")
    else:
        gained_xp = XP_REWARD_WRONG
        print(f"😅 答錯了！正確答案是 ({answer})")
        print(f"💪 安慰獎：+{gained_xp} XP")
    
    # 更新資料
    new_total_xp = update_user_xp(gained_xp)
    new_level = get_level(new_total_xp)
    
    # --- 升級與解鎖判斷 ---
    if new_level > level:
        print("\n" + "🎊"*20)
        print(f"   恭喜升級！ 現在是 Lv.{new_level} 了！   ")
        print("🎊"*20)
        
        # 判斷是否解鎖新角色 (只要現在的等級在列表裡，且之前還沒達到這個等級)
        if new_level in CHARACTERS:
            new_char = CHARACTERS[new_level]
            print("\n" + "✨"*25)
            print(f" 🔓 解鎖新角色稱號：【{new_char}】！")
            print(f"    快去向朋友炫耀吧！")
            print("✨"*25)
    # ---------------------
    
    print(f"\n📊 目前進度：{get_next_level_progress(new_total_xp)}")
    
    print("\n" + "-"*50)
    print("📖 詳細解說")
    print("-"*50)
    for line in explanation.split('\n'):
        if line.strip():
            print(line)
    print("="*50)

    save_to_history(current_hash)

if __name__ == "__main__":
    main()
