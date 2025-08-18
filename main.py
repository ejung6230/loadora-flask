# flask_korlark.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime, timezone, timedelta
import os
import json
from item_map import ITEM_MAP


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
# ITEM_MAP


# ------------------ 유틸 ------------------
def filter_active_reports(api_data):
    """현재 시각(KST)에 떠돌이 상인 출현 구간에 포함되는 리포트만 필터링"""
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    current_reports = []
    
    # 하루 4구간
    periods = [
        (22, 3, 30),  # 오후 10:00 ~ 오전 3:30 (22:00 ~ 03:30)
        (4, 9, 30),   # 오전 4:00 ~ 오전 9:30 (04:00 ~ 09:30)
        (10, 15, 30), # 오전 10:00 ~ 오후 3:30 (10:00 ~ 15:30)
        (16, 21, 30)  # 오후 4:00 ~ 오후 9:30 (16:00 ~ 21:30)
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
    """
    서버별 떠돌이 상인 아이템 요약
    """
    server_entries = {}

    for entry in data:
        region_name = REGION_MAP.get(entry['regionId'], f"지역{entry['regionId']}")
        item_names = [ITEM_MAP.get(i, f"아이템{i}") for i in entry['itemIds']]

        # 각 서버(서버 이름)에 추가
        # 여기서는 regionId → 서버 매핑이 필요하다고 가정
        # 예시: 1~8 서버별 regionId는 따로 정의
        # 편의상 서버 이름 = SERVER_ORDER 순서 기준
        for server in SERVER_ORDER:
            if server not in server_entries:
                server_entries[server] = []

        # 단순히 모든 아이템을 루프 돌며 서버별로 넣는 경우
        # 실제로는 API에서 서버 기준 데이터를 받아야 정확함
        server_entries[SERVER_MAP.get(entry['regionId'], SERVER_ORDER[0])].extend(
            [f"{name}({region_name})" for name in item_names]
        )

    # 중복 제거 후 문자열 생성
    lines = []
    for server in SERVER_ORDER:
        items = list(dict.fromkeys(server_entries.get(server, [])))  # 중복 제거
        lines.append(f"{server}: {', '.join(items)}" if items else f"{server}: 없음")

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














