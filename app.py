from flask import Flask, request, jsonify, render_template
import os
from QA import process_image

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ===== 首頁 =====
@app.route("/")
def home():
    return render_template("index.html")


# ===== 健康檢查（Render建議一定留著）=====
@app.route("/healthz")
def healthz():
    return "ok"


# ===== AI圖片辨識 =====
@app.route("/analyze", methods=["POST"])
def analyze():

    try:

        if "image" not in request.files:
            return jsonify({
                "status": "error",
                "message": "沒有上傳圖片"
            }), 400

        file = request.files["image"]

        if file.filename == "":
            return jsonify({
                "status": "error",
                "message": "檔案名稱錯誤"
            }), 400

        # 儲存圖片
        path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(path)

        # AI辨識
        result = process_image(path)

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        })


# ===== Render 必須用這個 =====
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
