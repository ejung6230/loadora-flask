# flask_korlark.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

# KorLark API URL
KORLARK_API_URL = "https://api.korlark.com/lostark/merchant/reports"

@app.route("/korlark_summary", methods=["GET", "POST"])
def korlark_summary():
    try:
        now = datetime.now(timezone.utc)
        summary_lines = ["❙ 전체 서버 떠상 정보\n"]

        # 서버 1~8
        for server_id in range(1, 9):
            resp = requests.get(KORLARK_API_URL, params={"server": str(server_id)})
            resp.raise_for_status()
            data = resp.json()

            # 현재 시간에 해당하는 블록만 필터링
            for block in data:
                start_time = datetime.fromisoformat(block.get("startTime").replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(block.get("endTime").replace("Z", "+00:00"))
                if start_time <= now <= end_time:
                    reports = block.get("reports", [])
                    for r in reports:
                        name = r.get("user", {}).get("characterName", "알수없음")
                        items = r.get("itemIds", [])
                        items_count = len(items)
                        line = f"{name}: 전설호감도 {items_count}개"
                        summary_lines.append(line)

        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [
                    {"simpleText": {"text": "\n".join(summary_lines)}}
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





