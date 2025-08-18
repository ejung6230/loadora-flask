# flask_korlark.py
from flask import Flask, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

# KorLark API URL
KORLARK_API_URL = "https://api.korlark.com/lostark/merchant/reports"

@app.route("/")
def home():
    return "KorLark API Flask 서버 실행 중"

@app.route("/korlark", methods=["GET"])
def korlark_proxy():
    try:
        # React에서 server 파라미터를 보낼 수도 있지만, 기본값 1로 설정
        response = requests.get(KORLARK_API_URL, params={"server": "1"})
        response.raise_for_status()
        api_data = response.json()
        return jsonify(api_data)  # 원래 API 데이터를 그대로 반환
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Railway 할당 포트 사용
    app.run(host="0.0.0.0", port=port)




