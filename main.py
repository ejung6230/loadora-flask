# flask_korlark.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime, timezone
import os

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

# KorLark API URL
KORLARK_API_URL = "https://api.korlark.com/lostark/merchant/reports"

def filter_current_reports(data):
    """현재 시간 기준 활성화된 서버 데이터만 반환"""
    now_utc = datetime.now(timezone.utc)
    result = []

    for period in data:
        start = datetime.fromisoformat(period['startTime'].replace("Z", "+00:00"))
        end = datetime.fromisoformat(period['endTime'].replace("Z", "+00:00"))
        if start <= now_utc <= end:
            result.append(period)
    return result

@app.route("/korlark_summary", methods=["GET", "POST"])
def korlark_summary():
    try:
        # 서버별 데이터 가져오기 (GET/POST 동일)
        response = requests.get(KORLARK_API_URL, params={"server": "1"})
        response.raise_for_status()
        api_data = response.json()

        # 현재 시간 기준 데이터만 필터
        current_data = filter_current_reports(api_data)

        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [
                    {"simpleText": {"text": f"{current_data}"}}
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

@app.route("/")
def home():
    return "KorLark API Flask 서버 실행 중"

@app.route("/korlark", methods=["GET"])
def korlark_proxy():
    try:
        server = request.args.get("server", "1")  # 기본값 1
        response = requests.get(KORLARK_API_URL, params={"server": server})
        response.raise_for_status()
        api_data = response.json()
        return jsonify(api_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# POST 메서드 추가 (카카오톡 챗봇용, 가공 없이 원본 데이터 전달)
@app.route("/korlark", methods=["POST"])
def korlark_webhook():
    try:
        server = request.json.get("server", "1")  # POST에서는 JSON 본문에서 받음
        response = requests.get(KORLARK_API_URL, params={"server": server})
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






