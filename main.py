# flask_korlark.py
from flask import Flask, jsonify, request
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
        response = requests.get(KORLARK_API_URL, params={"server": "1"})
        response.raise_for_status()
        api_data = response.json()
        return jsonify(api_data)  # 원래 API 데이터를 그대로 반환
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# POST 메서드 추가 (카카오톡 챗봇용, 가공 없이 원본 데이터 전달)
@app.route("/korlark", methods=["POST"])
def korlark_webhook():
    try:
        response = requests.get(KORLARK_API_URL, params={"server": "1"})
        response.raise_for_status()
        api_data = response.json()

        import json
        text_response = json.dumps(api_data, ensure_ascii=False)

        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [
                    {"simpleText": {"text": text_response}}
                ]
            }
        })
    except Exception as e:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [
                    {"simpleText": {"text": f"API 호출 실패: {e}"}}
                ]
            }
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Railway 할당 포트 사용
    app.run(host="0.0.0.0", port=port)


