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

# POST 메서드 추가 (카카오톡 챗봇용)
@app.route("/korlark", methods=["POST"])
def korlark_webhook():
    try:
        # 카카오톡이 보내는 JSON 받기
        req_json = request.get_json()
        # 외부 API 호출
        response = requests.get(KORLARK_API_URL, params={"server": "1"})
        response.raise_for_status()
        api_data = response.json()

        # 챗봇용 문자열 생성 (예시: 첫 3개 블록만)
        messages = []
        for block in api_data[:3]:
            start = block.get("startTime")
            end = block.get("endTime")
            for report in block.get("reports", []):
                name = report.get("user", {}).get("characterName", "알 수 없음")
                region = report.get("regionId", "알 수 없음")
                items = ", ".join(map(str, report.get("itemIds", []))) or "없음"
                upvote = report.get("upVoteCount", 0)
                messages.append(f"{start}~{end}\n상인: {name}\n지역: {region}\n아이템: {items}\n업보팅: {upvote}")

        text_response = "\n\n".join(messages) if messages else "떠돌이 상인 정보가 없습니다."

        # 카카오톡 챗봇용 JSON 응답
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
