# main.py
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# KorLark API URL
KORLARK_API_URL = "https://api.korlark.com/lostark/merchant/reports"

@app.route("/")
def home():
    return "KorLark API Flask 서버 실행 중"

@app.route("/korlark", methods=["POST"])
def korlark_api():
    try:
        data = request.get_json()
        server_param = data.get("action", {}).get("params", {}).get("server", "1")

        # KorLark API 호출
        response = requests.get(KORLARK_API_URL, params={"server": server_param})
        response.raise_for_status()
        api_data = response.json()

        # 필요한 부분만 가공 (예: reports)
        reports = []
        for period in api_data:
            for report in period.get("reports", []):
                reports.append({
                    "id": report.get("id"),
                    "user": report.get("user", {}).get("characterName"),
                    "items": report.get("itemIds"),
                    "createdAt": report.get("createdAt")
                })

        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": f"총 {len(reports)}건의 상인 보고서를 가져왔습니다."
                        }
                    }
                ]
            },
            "data": reports
        })

    except Exception as e:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [
                    {"simpleText": {"text": f"오류 발생: {str(e)}"}}
                ]
            }
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
