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

# 서버 이름 순서
SERVER_ORDER = ["루페온", "실리안", "아만", "아브렐슈드", "카단", "카마인", "카제로스", "니나브"]

# 서버 ID → 서버 이름 매핑
SERVER_MAP = {
    "1": "루페온",
    "2": "실리안",
    "3": "아만",
    "4": "아브렐슈드",
    "5": "카단",
    "6": "카마인",
    "7": "카제로스",
    "8": "니나브",
}

# 아이템 ID → 아이템 이름 매핑 (예시)
ITEM_MAP = {
    "17": "전설호감도",
    "18": "에스더 루테란",
    "19": "에스더 갈라투르",
    "22": "바훈투르",
    "33": "전설호감도",
    "36": "전설호감도",
    "37": "전설호감도",
    "39": "전설호감도",
    "41": "전설호감도",
    "44": "전설호감도",
    "46": "전설호감도",
    "53": "전설호감도",
    "55": "전설호감도",
    "57": "전설호감도",
    "58": "전설호감도",
    # 실제 필요한 모든 아이템 ID 매핑 필요
}

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


def format_current_reports(data):
    """서버별 대표 엔트리 요약 및 판매 마감 시간 표시"""
    now_utc = datetime.now(timezone.utc)
    if not data:
        return ""  # 여기서 '현재는 떠상 판매시간이 아닙니다.' 제거

    server_items = {name: [] for name in SERVER_ORDER}
    end_times = []

    for period in data:
        start = datetime.fromisoformat(period['startTime'].replace("Z", "+00:00"))
        end = datetime.fromisoformat(period['endTime'].replace("Z", "+00:00"))
        end_times.append(end)

        for report in period['reports']:
            server_name = SERVER_MAP.get(report['regionId'], f"서버{report['regionId']}")
            for item_id in report['itemIds']:
                item_name = ITEM_MAP.get(item_id, f"아이템{item_id}")
                server_items[server_name].append(item_name)

    lines = []
    for server_name in SERVER_ORDER:
        items = list(dict.fromkeys(server_items[server_name]))  # 중복 제거
        text = ", ".join(items) if items else "없음"
        lines.append(f"{server_name}: {text}")

    if end_times:
        nearest_end = min(end_times)
        remaining = nearest_end - now_utc
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        lines.append(f"\n판매 마감까지 {hours}시간 {minutes}분 남았습니다.")

    return "\n".join(lines)


@app.route("/korlark_summary", methods=["GET", "POST"])
def korlark_summary():
    try:
        response = requests.get(KORLARK_API_URL, params={"server": "1"})
        response.raise_for_status()
        api_data = response.json()


        current_data = filter_current_reports(api_data)

        if not current_data:
            text_response = "현재는 떠상 판매시간이 아닙니다."
        else:
            text_response = format_current_reports(current_data)

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

@app.route("/korlark", methods=["POST"])
def korlark_webhook():
    try:
        server = request.json.get("server", "1")
        response = requests.get(KORLARK_API_URL, params={"server": server})
        response.raise_for_status()
        api_data = response.json()
        import json
        text_response = format_current_reports(filter_current_reports(api_data))
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
