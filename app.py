from flask import Flask, request, jsonify, render_template
import os
from QA import process_image

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return "ok"


@app.route("/analyze", methods=["POST"])
def analyze():

    if "image" not in request.files:
        return jsonify({"error": "沒有圖片"}), 400

    file = request.files["image"]

    path = os.path.join(UPLOAD_FOLDER, file.filename)

    file.save(path)

    result = process_image(path)

    return jsonify(result)


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)
