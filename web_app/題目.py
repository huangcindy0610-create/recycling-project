import google.generativeai as genai
from PIL import Image

# ... (其他的 import 和 API_KEY 設定保持不變) ...

def identify_trash_type(images.jpg):
    """
    使用 Gemini Flash 模型辨識垃圾種類
    """
    # 這裡設定您要使用的模型名稱
    # 如果想用最新的 2.0 實驗版，可改為 'gemini-2.0-flash-exp'
    model_name = 'gemini-2.5-flash' 
    
    try:
        model = genai.GenerativeModel(model_name)
    except Exception:
        # 如果模型名稱打錯或帳號沒權限，會退回到預設
        st.warning(f"無法存取 {model_name}，切換回 gemini-2.5-flash")
        model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 優化後的提示詞 (Prompt)，讓 AI 更專注於分類
    prompt = """
    你是一個專業的資源回收分類助理。請仔細觀察這張圖片。
    
    圖片中主要的主題物品是什麼？請將其分類為以下其中一項：
    1. plastic_bottle (寶特瓶、塑膠瓶)
    2. paper_cup (紙杯)
    3. paper_bag (紙袋)
    4. can (鋁罐、鐵罐、金屬罐)
    5. glass (玻璃瓶)
    6. carton (新鮮屋、牛奶盒、飲料紙盒)
    7. unknown (如果圖片模糊、沒有物品，或不屬於上述類別)

    請注意：
    - 如果是壓扁的寶特瓶，依然是 plastic_bottle。
    - 如果是手拿著物品，請忽略手部，專注於物品本身。
    
    回傳格式限制：
    請「只回傳」上述的英文代碼 (例如: plastic_bottle)，不要回傳任何其他文字、標點符號或解釋。
    """
    
    try:
        # 設定 generation_config 可以控制輸出的隨機性，設為 0 讓答案更穩定
        response = model.generate_content(
            [prompt, images.jpg],
            generation_config=genai.types.GenerationConfig(temperature=0.0)
        )
        
        # 清除可能多餘的空白
        result = response.text.strip()
        
        # 簡單的防呆檢查，如果 AI 回傳了一大串話，強制視為 unknown
        valid_types = ["plastic_bottle", "paper_cup", "paper_bag", "can", "glass", "carton", "unknown"]
        if result not in valid_types:
            # 有時候 AI 會很熱心地回傳 "這是一個 plastic_bottle"，所以我們試著檢查關鍵字
            for v_type in valid_types:
                if v_type in result:
                    return v_type
            return "unknown"
            
        return result

    except Exception as e:
        # 在終端機印出錯誤以便除錯
        print(f"AI 辨識錯誤: {e}")
        return "unknown"