# flask_korlark.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime, timezone, timedelta
import os
import json

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

# KorLark API URL
KORLARK_API_URL = "https://api.korlark.com/lostark/merchant/reports"

# 서버 이름 순서
SERVER_ORDER = ["루페온", "실리안", "아만", "아브렐슈드", "카단", "카마인", "카제로스", "니나브"]

# 서버 ID → 서버 이름 매핑
SERVER_MAP = {
    "1": "루페온", "2": "실리안", "4": "아브렐슈드",
    "7": "카제로스", "9": "카단", "10": "카마인",
    "12": "니나브", "13": "아만", "15": "루페온",
    "16": "실리안", "17": "아만", "18": "아브렐슈드",
    "20": "카단", "21": "카마인", "22": "카제로스"
}

# 아이템 ID → 아이템 이름 매핑
ITEM_MAP = {
    "1": "전설호감도", "2": "에스더 루테란", "6": "에스더 갈라투르",
    "7": "바훈투르", "12": "아이템12", "13": "아이템13", "9": "아이템9",
    "24": "아이템24", "25": "아이템25", "29": "아이템29", "30": "아이템30",
    "31": "아이템31", "49": "아이템49", "50": "아이템50", "51": "아이템51",
    "59": "아이템59", "65": "아이템65", "66": "아이템66", "68": "아이템68",
    "69": "아이템69", "72": "아이템72", "74": "아이템74",
    "85": "아이템85", "86": "아이템86", "88": "아이템88", "90": "아이템90",
    "91": "아이템91", "96": "아이템96", "97": "아이템97", "99": "아이템99",
    "113": "아이템113", "115": "아이템115", "119": "아이템119",
    "121": "아이템121", "122": "아이템122", "123": "아이템123",
    "125": "아이템125", "127": "아이템127", "128": "아이템128",
    "130": "아이템130", "134": "아이템134", "135": "아이템135",
    "140": "아이템140", "142": "아이템142", "143": "아이템143",
    "144": "아이템144", "145": "아이템145", "149": "아이템149",
    "150": "아이템150", "152": "아이템152", "155": "아이템155",
    "157": "아이템157", "158": "아이템158", "161": "아이템161",
    "162": "아이템162", "163": "아이템163", "167": "아이템167",
    "168": "아이템168", "169": "아이템169", "170": "아이템170",
    "196": "아이템196", "197": "아이템197", "201": "아이템201",
    "203": "아이템203", "205": "아이템205", "212": "아이템212",
    "213": "아이템213", "216": "아이템216", "217": "아이템217",
    "221": "아이템221", "223": "아이템223", "225": "아이템225",
    "227": "아이템227", "228": "아이템228"
}

def filter_current_reports(api_data):
    """
    현재 시간(KST)과 일치하는 데이터만 필터링
    """
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    current_reports = []

    for entry in api_data:
        created_at = datetime.fromisoformat(entry['createdAt'].replace("Z", "+00:00")).astimezone(kst)
        if (created_at.year == now.year and created_at.month == now.month and
            created_at.day == now.day and created_at.hour == now.hour and
            created_at.minute == now.minute):
            current_reports.append(entry)

    return current_reports

def format_current_reports(data):
    """
    서버별 대표 아이템 요약 문자열 반환
    """
    server_entries = {}
    for entry in data:
        server_name = SERVER_MAP.get(entry['regionId'], f"서버{entry['regionId']}")
        item_names = [ITEM_MAP.get(item_id, f"아이템{item_id}") for item_id in entry['itemIds']]
        if server_name not in server_entries:
            server_entries[server_name] = item_names  # 첫 엔트리 대표로 사용

    result_lines = []
    for server in SERVER_ORDER:
        items = server_entries.get(server)
        if items:
            result_lines.append(f"[{server}] {', '.join(items)}")
        else:
            result_lines.append(f"[{server}] 없음")

    return "\n".join(result_lines)

# ------------------ Flask endpoints ------------------

@app.route("/")
def home():
    return "KorLark API Flask 서버 실행 중"

@app.route("/korlark_summary", methods=["GET"])
def korlark_summary():
    try:
        response = requests.get(KORLARK_API_URL, params={"server": "1"})
        response.raise_for_status()
        api_data = response.json()

        current_data = filter_current_reports(api_data)
        text_response = format_current_reports(current_data) if current_data else "없음"

        return jsonify({
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": text_response}}]}
        })

    except Exception as e:
        return jsonify({
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": f"API 호출 실패: {e}"}}]}
        }), 500

@app.route("/korlark", methods=["GET"])
def korlark_proxy():
    try:
        server = request.args.get("server", "1")
        response = requests.get(KORLARK_API_URL, params={"server": server})
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/korlark", methods=["POST"])
def korlark_webhook():
    try:
        server = request.json.get("server", "1")
        response = requests.get(KORLARK_API_URL, params={"server": server})
        response.raise_for_status()
        return jsonify({
            "version": "2.0",
            "template": [{"simpleText": {"text": json.dumps(response.json(), ensure_ascii=False)}}]
        })
    except Exception as e:
        return jsonify({
            "version": "2.0",
            "template": [{"simpleText": {"text": f"API 호출 실패: {e}"}}]
        }), 500

# ------------------ 실행 ------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

