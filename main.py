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
    "1": "루페온", 
    "2": "실리안", 
    "3": "아만", 
    "4": "아브렐슈드",
    "5": "카단",
    "6": "카마인",
    "7": "카제로스", 
    "8": "니나브"
}

# 지역 ID → 지역 이름 매핑
REGION_MAP = {str(i): f"지역{i}" for i in range(1, 300)}
# REGION_MAP = {
#     "1": "지역1", 
#     "2": "지역2", 
#     "3": "지역3", 
#     "4": "지역4",
#     "5": "지역5", 
#     "6": "지역6", 
#     "7": "지역7", 
#     "8": "지역8",
#     "9": "지역9", 
#     "10": "지역10",
#     "11": "지역11",
#     "12": "지역12", 
#     "13": "지역13", 
#     "14": "지역14", 
#     "15": "지역15",
#     "16": "지역16", 
#     "17": "지역17", 
#     "18": "지역18",
#     "19": "지역19",
#     "20": "지역20", 
#     "21": "지역21", 
#     "22": "지역22"
# }

# 아이템 ID → 아이템 이름 매핑
ITEM_MAP = {str(i): f"아이템{i}" for i in range(1, 300)}

# ITEM_MAP = {
#     "1": "전설호감도", 
#     "2": "에스더 루테란", 
#     "6": "에스더 갈라투르",
#     "7": "바훈투르", 
#     "12": "아이템12", 
#     "13": "아이템13", 
#     "9": "아이템9",
#     "24": "아이템24", 
#     "25": "아이템25", 
#     "29": "아이템29", 
#     "30": "아이템30",
#     "31": "아이템31", 
#     "49": "아이템49", 
#     "50": "아이템50", 
#     "51": "아이템51",
#     "59": "아이템59",
#     "65": "아이템65", 
#     "66": "아이템66", 
#     "68": "아이템68",
#     "69": "아이템69",
#     "72": "아이템72", 
#     "74": "아이템74",
#     "85": "아이템85", 
#     "86": "아이템86", 
#     "88": "아이템88", 
#     "90": "아이템90",
#     "91": "아이템91", 
#     "96": "아이템96", 
#     "97": "아이템97", 
#     "99": "아이템99",
#     "113": "아이템113", 
#     "115": "아이템115", 
#     "119": "아이템119",
#     "121": "아이템121", 
#     "122": "아이템122", 
#     "123": "아이템123",
#     "125": "아이템125",
#     "127": "아이템127",
#     "128": "아이템128",
#     "130": "아이템130", 
#     "134": "아이템134",
#     "135": "아이템135",
#     "140": "아이템140", 
#     "142": "아이템142", 
#     "143": "아이템143",
#     "144": "아이템144", 
#     "145": "아이템145", 
#     "149": "아이템149",
#     "150": "아이템150",
#     "152": "아이템152",
#     "155": "아이템155",
#     "157": "아이템157",
#     "158": "아이템158",
#     "161": "아이템161",
#     "162": "아이템162", 
#     "163": "아이템163",
#     "167": "아이템167",
#     "168": "아이템168", 
#     "169": "아이템169", 
#     "170": "아이템170",
#     "196": "아이템196", 
#     "197": "아이템197",
#     "201": "아이템201",
#     "203": "아이템203",
#     "205": "아이템205",
#     "212": "아이템212",
#     "213": "아이템213", 
#     "216": "아이템216",
#     "217": "아이템217",
#     "221": "아이템221", 
#     "223": "아이템223",
#     "225": "아이템225",
#     "227": "아이템227", 
#     "228": "아이템228"
# }


# ------------------ 유틸 ------------------
def filter_active_reports(api_data):
    """현재 시각(KST)에 떠돌이 상인 출현 구간에 포함되는 리포트만 필터링"""
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    current_reports = []

    # 하루 4구간
    periods = [
        (22, 3, 30),  # 22:00 ~ 03:30
        (4, 9, 30),   # 04:00 ~ 09:30
        (10, 15, 30), # 10:00 ~ 15:30
        (16, 21, 30)  # 16:00 ~ 21:30
    ]

    for start_hour, end_hour, end_minute in periods:
        start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        # 다음 날로 넘어가는 구간 처리
        if end_hour < start_hour:
            end = (now + timedelta(days=1)).replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        else:
            end = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)

        if start <= now <= end:
            # 현재 구간에 포함되면 reports 배열 전체 추가
            for entry in api_data:
                current_reports.extend(entry.get("reports", []))
            break  # 이미 포함되는 구간 찾았으면 더 이상 확인하지 않음

    return current_reports



def format_reports_by_region(data):
    """ 지역별 대표 아이템 요약 문자열 생성 """
    region_entries = {}
    for entry in data:
        region_name = REGION_MAP.get(entry['regionId'], f"지역{entry['regionId']}")
        item_names = [ITEM_MAP.get(i, f"아이템{i}") for i in entry['itemIds']]
        if region_name not in region_entries:
            region_entries[region_name] = item_names

    # SERVER_ORDER 기준으로 출력 (없으면 '없음')
    lines = []
    for server in SERVER_ORDER:
        items = region_entries.get(server)
        lines.append(f"[{server}] {', '.join(items)}" if items else f"[{server}] 없음")
    return "\n".join(lines)

# ------------------ Flask endpoints ------------------
@app.route("/")
def home():
    return "KorLark API Flask 서버 실행 중"

@app.route("/korlark_summary", methods=["GET", "POST"])
def korlark_summary():
    try:
        server_ids = request.json.get("servers", list(SERVER_MAP.keys())) if request.method=="POST" else list(SERVER_MAP.keys())
        all_data = []
        for server_id in server_ids:
            resp = requests.get(KORLARK_API_URL, params={"server": server_id})
            resp.raise_for_status()
            all_data.extend(resp.json())
        current_data = filter_active_reports(all_data)
        summary_text = format_reports_by_region(current_data)

        if request.method=="POST":
            return jsonify({"version":"2.0","template":{"outputs":[{"simpleText":{"text":summary_text}}]}})
        return summary_text
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/korlark", methods=["GET","POST"])
def korlark_proxy():
    try:
        server = request.args.get("server", "1") if request.method=="GET" else request.json.get("server", "1")
        resp = requests.get(KORLARK_API_URL, params={"server": server})
        resp.raise_for_status()
        data = resp.json()
        if request.method=="POST":
            return jsonify({"version":"2.0","template":{"outputs":[{"simpleText":{"text":json.dumps(data, ensure_ascii=False)}}]}})
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------ 실행 ------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)










