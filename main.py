# flask_korlark.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime, timezone, timedelta
import os
import json
import time
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

# 🔑 발급받은 JWT 토큰
JWT_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6IktYMk40TkRDSTJ5NTA5NWpjTWk5TllqY2lyZyIsImtpZCI6IktYMk40TkRDSTJ5NTA5NWpjTWk5TllqY2lyZyJ9.eyJpc3MiOiJodHRwczovL2x1ZHkuZ2FtZS5vbnN0b3ZlLmNvbSIsImF1ZCI6Imh0dHBzOi8vbHVkeS5nYW1lLm9uc3RvdmUuY29tL3Jlc291cmNlcyIsImNsaWVudF9pZCI6IjEwMDAwMDAwMDA1ODU3OTMifQ.pGbLttyxM_QTAJxMGW2XeMYQ1TSfArJiyLv-TK4yxZJDes4nhnMfAlyJ6nSmVMHT6q2P_YqGkavwhCkfYAylI94FR74G47yeQuWLu3abw76wzBGN9pVRtCLu6OJ4RcIexr0rpQLARZhIiuNUrr3LLN_sbV7cNUQfQGVr0v9x77cbxVI5hPgSgAWAIcMX4Z7a6wj4QSnl7qi9HBZG1CH8PQ7ftGuBgFG7Htbh2ABj3xyza44vrwPN5VL-S3SUQtnJ1azOTfXvjCTJjPZv8rOmCllK9dMNoPFRjj7bsjeooYHfhK1rF9yiCJb9tdVcTa2puxs3YKQlZpN9UvaVhqquQg"

GEMINI_API_KEY = "AIzaSyBsxfr_8Mw-7fwr_PqZAcv3LyGuI0ybv08"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"

HEADERS = {
    "accept": "application/json",
    "authorization": f"bearer {JWT_TOKEN}"
}

def organize_characters_by_server(char_list):
    organized = {}
    for c in char_list:
        server = c.get("ServerName", "Unknown")
        organized.setdefault(server, []).append(c)
    return organized

@app.route("/fallback", methods=["POST"])
def fallback():
    # 특수문자 참고 ❘ ❙ ❚ ❛ ❜
    try:
        json_data = request.get_json()
        user_input = json_data.get("userRequest", {}).get("utterance", "").strip()
        use_share_button = False  # True: 공유 버튼 있는 카드, False: simpleText

        response_text = ""
        items = []
        
        inspection_item = [
            {
                "title": "⚠️ 현재 로스트아크 서버 점검 중입니다.",
                "description": "잠시 후 다시 시도해주세요.",
                "buttons": [
                    {
                        "label": "공식 공지 이동",
                        "action": "webLink",
                        "webLinkUrl": "https://lostark.game.onstove.com/News/Notice/List"
                    }
                ]
            }
        ]

        # ---------- 1. 공지 관련 패턴 ----------
        match_notice = re.match(r"^(\.공지|공지|\.ㄱㅈ|ㄱㅈ)$", user_input)
        if match_notice:
            url = "https://developer-lostark.game.onstove.com/news/notices"
        
            notice_types = ["공지", "점검", "상점", "이벤트"]
            all_notices = []
            server_down = False  # 서버 점검 여부 플래그
        
            for notice_type in notice_types:
                try:
                    resp = requests.get(url, headers=HEADERS, params={"type": notice_type}, timeout=5)
                    resp.raise_for_status()
                    notices = resp.json()
                    for n in notices:
                        n["Type"] = notice_type
                        all_notices.append(n)
                except requests.exceptions.HTTPError as e:
                    if resp.status_code == 503:
                        items = inspection_item
                        server_down = True
                        break
                    continue
                except Exception:
                    raise # 실패한 타입부터 무시하고 작업 종료
        
            if not server_down and all_notices:  # ✅ 서버 점검이 아닐 때만 공지 정리
                # 날짜 기준 최신순 정렬
                from datetime import datetime, timezone, timedelta
                def parse_date(date_str):
                    try:
                        dt_obj = datetime.fromisoformat(date_str.replace("Z", ""))
                        return dt_obj
                    except Exception:
                        return datetime.min
        
                all_notices.sort(key=lambda x: parse_date(x.get("Date", "")), reverse=True)
        
                # 최신 5개만 선택
                latest_notices = all_notices[:10]
        
                cards = []
                for n in latest_notices:
                    title = n.get("Title", "")
                    date_time = n.get("Date", "")
                    link = n.get("Link", "")
                    notice_type = n.get("Type", "")
        
                    # 날짜 변환
                    try:
                        # dt_obj를 naive datetime으로 생성
                        dt_obj = datetime.fromisoformat(date_time)
                        formatted_time = dt_obj.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        formatted_time = date_time

                    # 현재 한국 시간 (naive)
                    now_kst = datetime.now()  # 이미 dt_obj와 같은 naive datetime 기준
                
                    # 🔥 NEW 여부 체크 (24시간 이내)
                    new_label = ""
                    if dt_obj and (now_kst - dt_obj) <= timedelta(hours=24):
                        new_label = "🆕 "
        
                    card = {
                        "title": f"[{notice_type}] {new_label}{title}",
                        "description": f"게시일: {formatted_time}\n",
                        "buttons": [
                            {"label": "공지 보기", "action": "webLink", "webLinkUrl": link, "highlight": True},
                            {"label": "공유하기", "action": "share", "highlight": False}
                        ]
                    }
        
                    cards.append(card)

                # 캐러셀 카드로 여러 개 삽입
                items = [
                    {
                        "simpleText": {
                            "text": f"◕ᴗ◕🌸\n최신 {len(cards)}개의 공지를 알려드릴게요.",
                            "extra": {}
                        }
                    },
                    {
                    "carousel": {
                        "type": "textCard",
                        "items": cards
                    }
                }]

            
        # ---------- 2. 모험섬 관련 패턴 ----------
        match_adventure_island = re.match(r"^(\.모험섬|모험섬|\.ㅁㅎㅅ|ㅁㅎㅅ)$", user_input)
        if match_adventure_island:
            island_content = match_adventure_island.group(1).strip()
            response_text = "◕ᴗ◕🌸\n모험섬 정보를 알려드릴게요.\n\n"
            response_text += f"[모험섬 명령어]\n내용: {island_content}"

        # ---------- 3. 원정대 관련 패턴 ----------
        match_expedition = re.match(r"^(\.원정대|원정대|\.ㅇㅈㄷ|ㅇㅈㄷ)\s*(.*)$", user_input)
        if match_expedition:
            expedition_char_name = match_expedition.group(2).strip()
            if not expedition_char_name:
                response_text = "◕_◕💧\n캐릭터 이름을 입력해주세요.\nex) .원정대 캐릭터명"
            else:
                url = f"https://developer-lostark.game.onstove.com/characters/{expedition_char_name}/siblings"

                try:
                    resp = requests.get(url, headers=HEADERS, timeout=5)
                    resp.raise_for_status()
                    data = resp.json()
        
                    organized_chars = organize_characters_by_server(data)
                    if organized_chars:
                        expedition_text = f"◕ᴗ◕🌸\n❛{expedition_char_name}❜ 님의 원정대 정보\n\n"
                        for server, chars in organized_chars.items():
                            chars.sort(key=lambda x: x['ItemAvgLevel'], reverse=True)
                            expedition_text += f"[{server} 서버]\n"
                            for c in chars:
                                expedition_text += f"- {c['CharacterName']} Lv{c['CharacterLevel']} {c['CharacterClassName']} ({c['ItemAvgLevel']})\n"
                            expedition_text += "\n"
        
                        response_text = expedition_text.strip()
                except requests.exceptions.HTTPError as e:
                    if resp.status_code == 503:
                        items = inspection_item
                    else:
                        response_text = f"원정대 정보를 불러올 수 없습니다. (오류 코드: {resp.status_code})"
                except Exception as e:
                    response_text = "⚠️ 서버와의 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    


        # ---------- 4. 이벤트 정보 관련 패턴 ----------
        match_event = re.match(r"^(\.이벤트|이벤트|\.ㅇㅂㅌ|ㅇㅂㅌ)$", user_input)
        if match_event:
            url = "https://developer-lostark.game.onstove.com/news/events"
        
            try:
                from datetime import datetime, timezone, timedelta
                
                resp = requests.get(url, headers=HEADERS, timeout=5)
                resp.raise_for_status()  # HTTP 오류 시 예외 발생
        
                events = resp.json()
                if not events:
                    response_text = "현재 진행 중인 이벤트가 없습니다."
                    items = []
                else:
                    cards = []
                    
                    for ev in events:
                        title = ev.get("Title", "")
                        thumbnail = ev.get("Thumbnail", "")
                        link = ev.get("Link", "")
                        start_date = ev.get("StartDate", "")
                        end_date = ev.get("EndDate", "")
                        
                        formatted_time = f"{start_date} ~ {end_date}"

                        # 현재 시간
                        now_kst = datetime.now()
                    
                        try:
                            start_obj = datetime.fromisoformat(start_date)
                            end_obj = datetime.fromisoformat(end_date)
                            formatted_time = f"{start_obj.strftime('%Y-%m-%d %H:%M')} ~ {end_obj.strftime('%Y-%m-%d %H:%M')}"

                            # D-day 계산
                            delta = (end_obj.date() - now_kst.date()).days
                            if delta > 0:
                                dday_str = f"D-{delta}"
                            elif delta == 0:
                                dday_str = "D-Day"
                            else:
                                dday_str = f"D+{abs(delta)}"
                        except Exception as e:
                            logging.error("날짜 변환 중 오류 발생: %s", e)
                            dday_str = "기간 확인 불가"

                    
                        # 🔥 NEW 여부 체크 (24시간 이내)
                        new_label = ""
                        if start_obj and timedelta(0) <= (now_kst - start_obj) <= timedelta(hours=24):
                            new_label = "🆕 "
                    
                        card = {
                            "title": f"[이벤트] {new_label}{title}",
                            "description": f"기간: {formatted_time} ({dday_str})\n",
                            "thumbnail": {
                                "imageUrl": f"{thumbnail}",
                                "link": {"web": ""},
                                "fixedRatio": False,
                                "altText": ""
                            },
                            "buttons": [
                                {"label": "이벤트 보기", "action": "webLink", "webLinkUrl": link, "highlight": True},
                                {"label": "공유하기", "highlight": False, "action": "share"}
                            ]
                        }
                        cards.append(card)

                    items.append({
                        "simpleText": {
                            "text": f"◕ᴗ◕🌸\n진행중인 {len(cards)}개의 이벤트를 알려드릴게요.",
                            "extra": {}
                        }
                    })
                    
                    cards_per_page = 10
                    # cards: 모든 이벤트 카드 리스트를 10개씩 나눠서 삽입
                    for i in range(0, len(cards), cards_per_page):
                        chunk = cards[i:i + cards_per_page]  # 10개씩 분할
                        carousel = {
                            "carousel": {
                                "type": "basicCard",
                                "items": chunk
                            }
                        }
                        
                        items.append(carousel)

        
            except requests.exceptions.HTTPError as e:
                if resp.status_code == 503:
                    response_text = "서비스 점검 중입니다. 잠시 후 다시 시도해주세요."
                else:
                    response_text = f"이벤트 정보를 불러올 수 없습니다. (오류 코드: {resp.status_code})"
                items = []
            except Exception as e:
                response_text = f"⚠️ 이벤트 정보를 가져오는 중 오류가 발생했습니다. ({e})"
                items = []
        
        
        # ---------- 5. 전체 서버 떠상 관련 패턴 ----------
        match_merchant = re.match(r"^(\.떠상|떠상|\.ㄸㅅ|ㄸㅅ|떠돌이상인)$", user_input)
        if match_merchant:
            server_ids = list(SERVER_MAP.keys())
            all_data = []

            def fetch_server_data(server_id):
                """서버별 떠상 데이터 가져오기"""
                try:
                    resp = requests.get(
                        KORLARK_API_URL,
                        params={"server": server_id},
                        timeout=5
                    )
                    resp.raise_for_status()
                    server_data = resp.json()
            
                    # 각 entry의 reports 안쪽에 server 정보 추가
                    for entry in server_data:
                        for report in entry.get("reports", []):
                            report["serverId"] = server_id
                            report["serverName"] = SERVER_MAP.get(server_id, server_id)
                            report["startTime"] = entry.get("startTime", "")
                            report["endTime"] = entry.get("endTime", "")
                    return server_data
            
                except Exception as e:
                    logger.error(f"[ERROR] 서버({server_id}) 처리 실패: {e}")
                    return []  # 실패 시 빈 리스트 반환
            
            # 병렬 처리 (스레드풀)
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_server = {executor.submit(fetch_server_data, sid): sid for sid in server_ids}
                for future in as_completed(future_to_server):
                    server_data = future.result()
                    if server_data:
                        all_data.extend(server_data)

            # 떠상 요약 텍스트 생성
            current_data = filter_active_reports(all_data)
            is_on_sale = get_remaining_time_text() == "현재 시각은 판매 구간이 아닙니다."
            response_text = "◕ᴗ◕🌸\n전체 서버 떠상 정보를 알려드릴게요.\n\n"
            response_text += format_reports_by_region(current_data, is_on_sale)
            response_text += f"\n\n{get_remaining_time_text()}"
        
            if len(response_text) <= 400:
                use_share_button = True
                
        # ---------- 6. 주급 관련 패턴 ----------
        match_weekly = re.match(r"^(\.주급|주급|\.ㅈㄱ|ㅈㄱ)\s*(.*)$", user_input)
        if match_weekly:
            weekly_text = match_weekly.group(2).strip()
            if not weekly_text:
                response_text = "◕_◕💧\n캐릭터 이름을 입력해주세요.\nex) .주급 캐릭터명"
            else:
                response_text = f"◕ᴗ◕🌸\n❛{weekly_text}❜ 님의 주급 정보를 알려드릴게요.\n\n"
                response_text += f"[주급 명령어]\n내용: {weekly_text}"


        # ---------- 7. 클리어골드 관련 패턴 ----------
        match_cleargold = re.match(r"^(\.클골|클골|\.ㅋㄱ|ㅋㄱ|\.클리어골드|클리어골드|\.ㅋㄹㅇㄱㄷ|ㅋㄹㅇㄱㄷ)\s*(.*)$", user_input)
        if match_cleargold:
            dungeon_name = match_cleargold.group(2).strip()
            if not dungeon_name:
                response_text = (
                    "◕_◕💧\n조회할 던전을 입력해주세요.\n"
                    "ex) .클골 4막, .클골 하기르"
                )
            else:
                response_text = "◕ᴗ◕🌸\n던전 클골 정보를 알려드릴게요.\n\n"
                response_text += f"[던전 명령어]\n내용: {dungeon_name}"
                
        # ---------- 8. 특정 캐릭터 정보 관련 패턴 ----------
        match_info = re.match(r"^(\.정보|정보|\.ㅈㅂ|ㅈㅂ)\s*(.*)$", user_input)
        if match_info:
            info_char_name = match_info.group(2).strip()
            if not info_char_name:
                response_text = "◕_◕💧\n캐릭터 이름을 입력해주세요.\nex) .정보 캐릭터명"
            else:
                # 공식 api에서 데이터 받아오기
                data = fetch_armory(info_char_name, "summary")
                
                # 데이터를 보기좋게 텍스트로 정제하기 (참조 : https://flask-production-df81.up.railway.app/armories/아도라o/summary)
                # response_text = match_info_to_text(data)

                # 전투정보실 바로가기 URL
                armory_url = f"https://lostark.game.onstove.com/Profile/Character/{info_char_name}"
                
                # 로펙(LOPEC) 바로가기 URL
                lopec_url = f"https://lopec.kr/mobile/search/search.html?headerCharacterName={info_char_name}"
                
                
                if data:
                    # 데이터가 있을 때만 텍스트 + 이미지 + 버튼
                    character_image = data["ArmoryProfile"]["CharacterImage"]
                    items = [
                        {
                            "textCard": {
                                "description": f"◕ᴗ◕🌸\n❛{info_char_name}❜ 님의 캐릭터 정보를 알려드릴게요\n\n",
                                "buttons": [
                                    {"label": "전투정보실 보기", "action": "webLink", "webLinkUrl": armory_url, "highlight": True},
                                    {"label": "로펙 보기", "action": "webLink", "webLinkUrl": lopec_url, "highlight": True},
                                    {"label": "공유하기", "highlight": False, "action": "share"}
                                ],
                                "lock": False,
                                "forwardable": False
                            }
                        },
                        {
                            "simpleImage": {
                                "imageUrl": character_image,
                                "altText": f"{info_char_name} 캐릭터 이미지"
                            }
                        },
                        {
                            "simpleText": {
                                "text": "캐릭터 정보",
                                "extra": {}
                            }
                        }
                    ]
                else:
                    # 데이터 없으면 텍스트 카드만
                    items = [
                        {
                            "textCard": {
                                "description": "◕_◕💧\n최신화된 캐릭터 정보가 존재하지 않습니다.",
                                "buttons": [],
                                "lock": False,
                                "forwardable": False
                            }
                        }
                    ]

        
        # ---------- 카카오 챗봇 응답 포맷 ----------
        
        if not response_text and not items:
            # ❌ 응답이 없으면 textCard + 사용 방법 GO 버튼
            response = {
                "version": "2.0",
                "template": {
                    "outputs": [
                        {
                            "textCard": {
                                "description": "◕_◕💧\n유효한 명령어를 입력해주세요.",
                                "buttons": [
                                    {
                                      "label": "사용 방법 GO",
                                      "highlight": True,
                                      "action": "webLink",
                                      "webLinkUrl": "http://pf.kakao.com/_tLVen/110482315"
                                    }
                                ],
                                "lock": False,
                                "forwardable": False
                            }
                        }
                    ],
                    "quickReplies": []
                }
            }
        elif items:
            response = {
                "version": "2.0",
                "template": {
                    "outputs": items,
                    "quickReplies": []
                }
            }
        else:
            if use_share_button:
                # ✅ 응답이 있으면 공유 버튼 있는 textCard
                response = {
                    "version": "2.0",
                    "template": {
                        "outputs": [
                            {
                                "textCard": {
                                    "description": response_text,
                                    "buttons": [
                                        {"label": "공유하기", "highlight": False, "action": "share"}
                                    ],
                                    "lock": False,
                                    "forwardable": False
                                }
                            }
                        ],
                        "quickReplies": []
                    }
                }
            else:
                # ✅ 응답이 있으면 simpleText
                response = {
                    "version": "2.0",
                    "template": {
                        "outputs": [
                            {"simpleText": {"text": response_text}}
                        ],
                        "quickReplies": []
                    }
                }

        return jsonify(response)
    except Exception as e:
        # 1️⃣ 로그 기록 (stack trace 포함)
        logger.exception("예외 발생: %s", e)
        
        # 2️⃣ 챗봇용 메시지 생성
        response_text = f"◕_◕💧\n에러가 발생했습니다: {str(e)}"
        response = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {"simpleText": {"text": response_text}}
                ],
                "quickReplies": []
            }
        }
        
        # 3️⃣ JSON으로 반환 (HTTP 500) 인데, 그냥 챗봇으로 응답함
        return jsonify(response)

def match_info_to_text(data):
    """
    ArkGrid JSON 데이터를 읽기 쉬운 텍스트로 변환하는 함수
    
    Args:
        data: 특정 유저 JSON 데이터 (dict 또는 JSON 문자열)
    
    Returns:
        str: 변환된 텍스트
    """
    # 문자열인 경우 JSON으로 파싱
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return "잘못된 JSON 형식입니다."
    
    if not isinstance(data, dict) not in data:
        return "데이터가 없습니다."

    # 아크 그리드
    arkgrid_data = data['ArkGrid']
    
    # 아크패시브
    arkPassive_data = data['ArkPassive']
    
    # 장착 아바타 정보
    armoryAvatars_data = data['ArmoryAvatars']

    # 장착 카드 정보
    armoryCard_data = data['ArmoryCard']

    # 장착 각인 정보
    armoryEngraving_data = data['ArmoryEngraving']

    # 장착 장비 정보
    armoryEquipment_data = data['ArmoryEquipment']

    # 장착 보석 정보
    armoryGem_data = data['ArmoryGem']

    # 장착 젬 정보
    gem_data = data['Gems']

    # 프로필 정보
    armoryProfile_data = data['ArmoryProfile']

    # 스킬트리 정보
    armorySkills_data = data['ArmorySkills']

    # 수집 전체 정보
    collectibles_data = data['Collectibles']

    # 모코코 수집 정보 / "Type": "모코코 씨앗"
    mococo_collectible_data = next((item for item in data["Collectibles"] if item["Type"] == "모코코 씨앗"), None)

    # 섬의마음 수집 정보 / "Type": "섬의 마음"
    island_heart_collectible_data = next((item for item in data["Collectibles"] if item["Type"] == "섬의 마음"), None)

    # 미술품 수집 정보 / "Type": "위대한 미술품"
    great_art_collectible_data = next((item for item in data["Collectibles"] if item["Type"] == "위대한 미술품"), None)

    # 징표 수집 정보 / "Type": "이그네아의 징표"
    igneas_mark_collectible     = next((item for item in data["Collectibles"] if item["Type"] == "이그네아의 징표"), None)
    
    # 모험물 수집 정보 / "Type": "항해 모험물"
    naval_adventure_collectible = next((item for item in data["Collectibles"] if item["Type"] == "항해 모험물"), None)

    # 세계수잎 수집 정보 / "Type": "세계수의 잎"
    world_tree_leaf_collectible = next((item for item in data["Collectibles"] if item["Type"] == "세계수의 잎"), None)

    # 오르페우스별 수집 정보 / "Type": "오르페우스의 별"
    orpheus_star_collectible    = next((item for item in data["Collectibles"] if item["Type"] == "오르페우스의 별"), None)

    # 오르골 수집 정보 / "Type": "기억의 오르골"
    memory_musicbox_collectible = next((item for item in data["Collectibles"] if item["Type"] == "기억의 오르골"), None)

    # 해도 수집 정보 / "Type": "크림스네일의 해도"
    crim_snail_map_collectible  = next((item for item in data["Collectibles"] if item["Type"] == "크림스네일의 해도"), None)


    # 콜로세움 정보
    colosseumInfo_data = data['ColosseumInfo']
    
    
    result_text = ""
    
    # 아크 그리드 효과 처리
    if 'Effects' in arkgrid_data and arkgrid_data['Effects']:
        result_text += "아크 그리드 효과:\n"
        for effect in arkgrid_data['Effects']:
            name = effect.get('Name', '알 수 없음')
            level = effect.get('Level', 0)
            tooltip = effect.get('Tooltip', '')
            
            # HTML 태그에서 수치 추출
            percentage = extract_percentage(tooltip)
            result_text += f"- {name} (레벨 {level}): {percentage}\n"
        result_text += "\n"
    
    # 젬 정보 처리
    if 'Slots' in arkgrid_data and arkgrid_data['Slots']:
        result_text += "젬 정보:\n"
        for slot_idx, slot in enumerate(arkgrid_data['Slots']):
            if 'Gems' in slot and slot['Gems']:
                for gem_idx, gem in enumerate(slot['Gems']):
                    grade = gem.get('Grade', '알 수 없음')
                    is_active = gem.get('IsActive', False)
                    icon_url = gem.get('Icon', '')
                    
                    # 툴팁에서 젬 이름과 타입 추출
                    tooltip = gem.get('Tooltip', '')
                    gem_name, gem_type = extract_gem_info(tooltip)
                    
                    result_text += f"슬롯 {slot_idx + 1} - 젬 {gem_idx + 1}:\n"
                    result_text += f"  - 등급: {grade}\n"
                    result_text += f"  - 이름: {gem_name}\n"
                    result_text += f"  - 타입: {gem_type}\n"
                    result_text += f"  - 활성 상태: {'활성' if is_active else '비활성'}\n"
                    if icon_url:
                        result_text += f"  - 아이콘 URL: {icon_url}\n"
                    result_text += "\n"
    
    return result_text.strip()



# Armories 엔드포인트 매핑
VALID_ENDPOINTS = [
    "summary", "profiles", "equipment", "avatars", "combat-skills", 
    "engravings", "cards", "gems", "colosseums", "collectibles", "arkpassive"
]


def fetch_armory(character_name, endpoint):
    if endpoint not in VALID_ENDPOINTS:
        raise ValueError("Invalid endpoint")
    
    path = "" if endpoint == "summary" else endpoint
    url = f"https://developer-lostark.game.onstove.com/armories/characters/{character_name}"
    if path:
        url += f"/{path}"

    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

@app.route("/armories/<character_name>/<endpoint>", methods=["GET"])
def get_armory(character_name, endpoint):
    try:
        data = fetch_armory(character_name, endpoint)
        return jsonify(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500



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

# 리스트 매핑
LIST_MAP = [
    {"regionId":"1",
     "name":"아르테미스",
     "npcName":"벤",
     "group":1,
     "items":[
         {"id":"238","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"1","type":1,"name":"시이라","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"239","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"8","type":2,"name":"두근두근 상자","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_02_230.png","default":False,"hidden":False},
         {"id":"7","type":2,"name":"아르테미스 성수","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_23.png","default":False,"hidden":False},
         {"id":"6","type":2,"name":"레온하트 감자","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_108.png","default":False,"hidden":False},
         {"id":"5","type":2,"name":"더욱 화려한 꽃다발","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_03_133.png","default":False,"hidden":False},
         {"id":"4","type":1,"name":"카마인","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}, 
         {"id":"3","type":1,"name":"레온하트 네리아","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"2","type":1,"name":"바루투","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"2",
     "name":"유디아",
     "npcName":"루카스",
     "group":2,
     "items":[
         {"id":"11","type":1,"name":"천둥","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"10","type":1,"name":"자이언트 웜","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"9","type":1,"name":"모리나","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"241","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"240","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"14","type":2,"name":"하늘을 비추는 기름","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_01_117.png","default":False,"hidden":False},
         {"id":"13","type":2,"name":"유디아 주술서","grade":3,"icon":"efui_iconatlas/use/use_8_39.png","default":False,"hidden":False},
         {"id":"12","type":2,"name":"유디아 천연소금","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_64.png","default":False,"hidden":False}
     ]},
    {"regionId":"3",
     "name":"루테란 서부",
     "npcName":"말론",
     "group":3,
     "items":[
         {"id":"243","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"242","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"16","type":1,"name":"베르하트","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"15","type":1,"name":"카도건","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"17","type":1,"name":"하셀링크","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"21","type":2,"name":"사슬전쟁 실록","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_01_155.png","default":False,"hidden":False},
         {"id":"20","type":2,"name":"흑장미","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_02_95.png","default":False,"hidden":False},
         {"id":"19","type":2,"name":"견고한 새장","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_02_46.png","default":False,"hidden":False},
         {"id":"22","type":3,"name":"머리초","grade":3,"icon":"efui_iconatlas/use/use_2_139.png","default":True,"hidden":False},
         {"id":"18","type":2,"name":"레이크바 토마토 주스","grade":3,"icon":"efui_iconatlas/use/use_1_224.png","default":False,"hidden":False}
     ]},
    {"regionId":"4",
     "name":"루테란 동부",
     "npcName":"모리스",
     "group":2,
     "items":[
         {"id":"283","type":1,"name":"진저웨일","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"245","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"31","type":3,"name":"드라이에이징 된 고기","grade":2,"icon":"efui_iconatlas/use/use_2_193.png","default":True,"hidden":False},
         {"id":"23","type":1,"name":"모르페오","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"24","type":1,"name":"푸름 전사 브리뉴","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"25","type":1,"name":"미한","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"26","type":1,"name":"데런 아만","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"27","type":2,"name":"디오리카 밀짚모자","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_183.png","default":False,"hidden":False},
         {"id":"28","type":2,"name":"루테란의 검 모형","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_161.png","default":False,"hidden":False},
         {"id":"29","type":2,"name":"아제나포리움 브로치","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_57.png","default":False,"hidden":False},
         {"id":"30","type":2,"name":"사슬전쟁 실록","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_01_155.png","default":False,"hidden":False},
         {"id":"244","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True}
     ]},
    {"regionId":"5",
     "name":"루테란 동부",
     "npcName":"버트",
     "group":3,
     "items":[
         {"id":"247","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"246","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"39","type":3,"name":"뜨거운 초코 커피","grade":2,"icon":"efui_iconatlas/all_quest/all_quest_02_32.png","default":True,"hidden":False},
         {"id":"32","type":1,"name":"집행관 솔라스","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"33","type":1,"name":"녹스","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"34","type":1,"name":"세리아","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"35","type":2,"name":"디오리카 밀짚모자","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_183.png","default":False,"hidden":False},
         {"id":"36","type":2,"name":"루테란의 검 모형","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_161.png","default":False,"hidden":False},
         {"id":"37","type":2,"name":"아제나포리움 브로치","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_57.png","default":False,"hidden":False},
         {"id":"38","type":2,"name":"사슬전쟁 실록","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_01_155.png","default":False,"hidden":False},
         {"id":"282","type":1,"name":"에스더 루테란","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"6",
     "name":"토토이크",
     "npcName":"올리버",
     "group":3,
     "items":[
         {"id":"45","type":2,"name":"특대 무당벌레 인형","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_03_113.png","default":False,"hidden":False},
         {"id":"44","type":2,"name":"모코코 당근","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_172.png","default":False,"hidden":False},
         {"id":"41","type":1,"name":"수호자 에오로","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"40","type":1,"name":"창조의 알","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"43","type":2,"name":"동글동글한 유리조각","grade":3,"icon":"efui_iconatlas/use/use_3_129.png","default":False,"hidden":False},
         {"id":"248","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"249","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"42","type":1,"name":"모카모카","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"46","type":2,"name":"수줍은 바람꽃가루","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_01_66.png","default":False,"hidden":False}
     ]},
    {"regionId":"7",
     "name":"애니츠",
     "npcName":"맥",
     "group":2,
     "items":[
         {"id":"284","type":1,"name":"가디언 루","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"52","type":2,"name":"강태공의 낚싯대","grade":4,"icon":"efui_iconatlas/lifelevel/lifelevel_01_59.png","default":False,"hidden":False},
         {"id":"51","type":2,"name":"비무제 참가 인장","grade":3,"icon":"efui_iconatlas/use/use_8_38.png","default":False,"hidden":False},
         {"id":"50","type":1,"name":"웨이","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"49","type":1,"name":"수령도사","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"48","type":1,"name":"객주도사","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"47","type":1,"name":"월향도사","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"250","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"251","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"285","type":1,"name":"에스더 시엔","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"8",
     "name":"아르데타인",
     "npcName":"녹스",
     "group":3,
     "items":[
         {"id":"55","type":1,"name":"카인","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"253","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"252","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"54","type":1,"name":"슈테른 네리아","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"57","type":2,"name":"고급 축음기","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_01_90.png","default":False,"hidden":False},
         {"id":"56","type":2,"name":"에너지 X7 캡슐","grade":3,"icon":"efui_iconatlas/use/use_8_42.png","default":False,"hidden":False},
         {"id":"58","type":3,"name":"아드레날린 강화 수액","grade":2,"icon":"efui_iconatlas/all_quest/all_quest_01_31.png","default":True,"hidden":False},
         {"id":"53","type":1,"name":"아이히만 박사","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"9",
     "name":"베른 북부",
     "npcName":"피터",
     "group":1,
     "items":[
         {"id":"255","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"59","type":1,"name":"페일린","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"60","type":1,"name":"기드온","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"61","type":1,"name":"라하르트","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"62","type":2,"name":"기사단 가입 신청서","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_141.png","default":False,"hidden":False},
         {"id":"63","type":2,"name":"고블린 고구마","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_105.png","default":False,"hidden":False},
         {"id":"64","type":2,"name":"마법 옷감","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_207.png","default":False,"hidden":False},
         {"id":"65","type":2,"name":"마력 결정","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_02_71.png","default":False,"hidden":False},
         {"id":"66","type":2,"name":"화려한 오르골","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_56.png","default":False,"hidden":False},
         {"id":"68","type":3,"name":"위대한 미술품 #2","grade":3,"icon":"efui_iconatlas/tokenitem/tokenitem_2.png","default":False,"hidden":False},
         {"id":"67","type":2,"name":"베른 건국 기념주화","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_01_253.png","default":False,"hidden":False},
         {"id":"254","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True}
     ]},
    {"regionId":"10",
     "name":"슈샤이어",
     "npcName":"제프리",
     "group":2,
     "items":[
         {"id":"69","type":1,"name":"자베른","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"257","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"256","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"71","type":1,"name":"진 매드닉","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"73","type":2,"name":"시리우스의 성서","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_03_4.png","default":False,"hidden":False},
         {"id":"72","type":2,"name":"빛나는 정수","grade":3,"icon":"efui_iconatlas/use/use_8_41.png","default":False,"hidden":False},
         {"id":"74","type":3,"name":"사파이어 정어리","grade":2,"icon":"efui_iconatlas/use/use_3_167.png","default":True,"hidden":False},
         {"id":"70","type":1,"name":"시안","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"11",
     "name":"로헨델",
     "npcName":"아리세르",
     "group":3,
     "items":[
        {"id":"79","type":2,"name":"새벽의 마력석","grade":3,"icon":"efui_iconatlas/use/use_6_10.png","default":False,"hidden":False},
         {"id":"80","type":2,"name":"정령의 깃털","grade":3,"icon":"efui_iconatlas/use/use_6_11.png","default":False,"hidden":False},
         {"id":"81","type":2,"name":"다뉴브의 귀걸이","grade":3,"icon":"efui_iconatlas/use/use_7_132.png","default":False,"hidden":False},
         {"id":"82","type":2,"name":"실린여왕의 축복","grade":4,"icon":"efui_iconatlas/use/use_7_133.png","default":False,"hidden":False},
         {"id":"78","type":1,"name":"아제나\u0026이난나","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"77","type":1,"name":"그노시스","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"75","type":1,"name":"알리페르","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"83","type":3,"name":"두근두근 마카롱","grade":3,"icon":"efui_iconatlas/use/use_5_213.png","default":True,"hidden":False},
         {"id":"258","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"259","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"76","type":1,"name":"엘레노아","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"12",
     "name":"욘",
     "npcName":"라이티르",
     "group":1,
     "items":[
         {"id":"286","type":1,"name":"에스더 갈라투르","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"84","type":1,"name":"피에르","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"85","type":1,"name":"위대한 성 네리아","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"86","type":1,"name":"케이사르","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"87","type":1,"name":"바훈투르","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"88","type":2,"name":"피에르의 비법서","grade":3,"icon":"efui_iconatlas/use/use_8_44.png","default":False,"hidden":False},
         {"id":"89","type":2,"name":"파후투르 맥주","grade":4,"icon":"efui_iconatlas/use/use_6_84.png","default":False,"hidden":False},
         {"id":"260","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"261","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"90","type":3,"name":"뒷골목 럼주","grade":1,"icon":"efui_iconatlas/use/use_6_49.png","default":True,"hidden":False}
     ]},
    {"regionId":"13",
     "name":"페이튼",
     "npcName":"도렐라",
     "group":2,
     "items":[
         {"id":"262","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"98","type":2,"name":"붉은 달의 눈물","grade":4,"icon":"efui_iconatlas/use/use_6_231.png","default":False,"hidden":False},
         {"id":"97","type":2,"name":"바싹 마른 목상","grade":3,"icon":"efui_iconatlas/use/use_6_230.png","default":False,"hidden":False},
         {"id":"96","type":2,"name":"생존의 서","grade":3,"icon":"efui_iconatlas/use/use_6_229.png","default":False,"hidden":False},
         {"id":"99","type":3,"name":"선지 덩어리","grade":2,"icon":"efui_iconatlas/use/use_2_24.png","default":True,"hidden":False},
         {"id":"95","type":2,"name":"부러진 단검","grade":3,"icon":"efui_iconatlas/use/use_6_228.png","default":False,"hidden":False},
         {"id":"94","type":1,"name":"페데리코","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"91","type":1,"name":"굴딩","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"93","type":1,"name":"칼도르","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"92","type":1,"name":"비올레","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"263","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True}
     ]},
    {"regionId":"14",
     "name":"파푸니카",
     "npcName":"레이니",
     "group":3,
     "items":[
         {"id":"264","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"100","type":1,"name":"세토","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"101","type":1,"name":"스텔라","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"102","type":1,"name":"키케라","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"103","type":1,"name":"알비온","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"104","type":2,"name":"포튼쿨 열매","grade":3,"icon":"efui_iconatlas/use/use_7_134.png","default":False,"hidden":False},
         {"id":"105","type":2,"name":"피냐타 제작 세트","grade":3,"icon":"efui_iconatlas/use/use_7_135.png","default":False,"hidden":False},
         {"id":"106","type":2,"name":"무지개 티카티카 꽃","grade":3,"icon":"efui_iconatlas/use/use_7_136.png","default":False,"hidden":False},
         {"id":"107","type":2,"name":"오레하의 수석","grade":4,"icon":"efui_iconatlas/use/use_7_137.png","default":False,"hidden":False},
         {"id":"110","type":3,"name":"부드러운 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_01_235.png","default":False,"hidden":False},
         {"id":"111","type":3,"name":"빛나는 백금 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_01_251.png","default":False,"hidden":False},
         {"id":"109","type":3,"name":"신비한 녹색 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_01_249.png","default":True,"hidden":False},
         {"id":"108","type":3,"name":"멧돼지 생고기","grade":2,"icon":"efui_iconatlas/all_quest/all_quest_02_126.png","default":True,"hidden":False},
         {"id":"287","type":1,"name":"광기를 잃은 쿠크세이튼","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"265","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True}
     ]},
    {"regionId":"15",
     "name":"베른 남부",
     "npcName":"에반",
     "group":1,
     "items":[
         {"id":"115","type":1,"name":"제레온","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"114","type":1,"name":"루기네","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"125","type":3,"name":"집중 룬","grade":4,"icon":"efui_iconatlas/use/use_7_200.png","default":True,"hidden":False},
         {"id":"124","type":3,"name":"보석 장식 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_01_248.png","default":False,"hidden":False},
         {"id":"123","type":3,"name":"신기한 마법 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_01_238.png","default":False,"hidden":False},
         {"id":"122","type":3,"name":"질긴 가죽 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_01_246.png","default":False,"hidden":False},
         {"id":"121","type":2,"name":"사령술사의 기록","grade":4,"icon":"efui_iconatlas/use/use_9_212.png","default":False,"hidden":False},
         {"id":"120","type":2,"name":"모형 반딧불이","grade":3,"icon":"efui_iconatlas/use/use_9_211.png","default":False,"hidden":False},
         {"id":"119","type":2,"name":"깃털 부채","grade":3,"icon":"efui_iconatlas/use/use_9_210.png","default":False,"hidden":False},
         {"id":"118","type":2,"name":"페브리 포션","grade":3,"icon":"efui_iconatlas/use/use_9_209.png","default":False,"hidden":False},
         {"id":"117","type":1,"name":"천둥날개","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"116","type":1,"name":"베른 젠로드","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"267","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"266","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"112","type":1,"name":"사트라","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"113","type":1,"name":"킬리언","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"16",
     "name":"로웬",
     "npcName":"세라한",
     "group":1,
     "items":[
        {"id":"141","type":2,"name":"최상급 육포","grade":3,"icon":"efui_iconatlas/use/use_10_109.png","default":False,"hidden":False},
         {"id":"140","type":2,"name":"엔야카 향유","grade":3,"icon":"efui_iconatlas/use/use_10_108.png","default":False,"hidden":False},
         {"id":"138","type":1,"name":"다르시","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"139","type":2,"name":"늑대 이빨 목걸이","grade":3,"icon":"efui_iconatlas/use/use_10_107.png","default":False,"hidden":False},
         {"id":"137","type":1,"name":"오스피어","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"136","type":1,"name":"뮨 히다카","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"135","type":1,"name":"마리나","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"134","type":1,"name":"하눈","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"133","type":1,"name":"빌헬름","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"132","type":1,"name":"피엘라","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"131","type":1,"name":"앙케","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"130","type":1,"name":"사일러스","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"269","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"268","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"129","type":1,"name":"바스키아","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"128","type":1,"name":"아르노","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"127","type":1,"name":"레퓌스","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"126","type":1,"name":"로웬 젠로드","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"142","type":2,"name":"보온용 귀도리","grade":4,"icon":"efui_iconatlas/use/use_10_110.png","default":False,"hidden":False}
     ]},
    
    {"regionId":"17",
     "name":"엘가시아",
     "npcName":"플라노스",
     "group":1,
     "items":[
        {"id":"288","type":1,"name":"베아트리스","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"143","type":1,"name":"코니","grade":0,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"144","type":1,"name":"티엔","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"145","type":1,"name":"키르케","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"146","type":1,"name":"유클리드","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"147","type":1,"name":"프리우나","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"148","type":1,"name":"하늘 고래","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"149","type":1,"name":"별자리 큰뱀","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"150","type":1,"name":"아자키엘","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"151","type":1,"name":"벨루마테","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"152","type":1,"name":"다이나웨일","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"153","type":1,"name":"디오게네스","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"154","type":1,"name":"라우리엘","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"155","type":1,"name":"영원의 아크 카양겔","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"156","type":1,"name":"에버그레이스","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"157","type":2,"name":"빛을 머금은 과실주","grade":3,"icon":"efui_iconatlas/use/use_10_158.png","default":False,"hidden":False},
         {"id":"158","type":2,"name":"별자리 큰뱀의 껍질","grade":3,"icon":"efui_iconatlas/use/use_10_159.png","default":False,"hidden":False},
         {"id":"159","type":2,"name":"크레도프 유리경","grade":3,"icon":"efui_iconatlas/use/use_10_160.png","default":False,"hidden":False},
         {"id":"160","type":2,"name":"행운의 초롱별 꽃","grade":4,"icon":"efui_iconatlas/use/use_10_161.png","default":False,"hidden":False},
         {"id":"161","type":3,"name":"향기 나는 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_01_240.png","default":False,"hidden":False},
         {"id":"162","type":3,"name":"반짝이는 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_01_243.png","default":False,"hidden":False},
         {"id":"270","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"271","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True}
     ]},
    {"regionId":"18",
     "name":"플레체",
     "npcName":"페드로",
     "group":2,
     "items":[
        {"id":"165","type":1,"name":"안토니오 주교","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"173","type":3,"name":"미술품 캐리어","grade":4,"icon":"efui_iconatlas/use/use_11_63.png","default":False,"hidden":False},
         {"id":"167","type":1,"name":"클라우디아","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"273","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"272","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"163","type":1,"name":"자크라","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"164","type":1,"name":"로잘린 베디체","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"170","type":2,"name":"정체불명의 입","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_02_21.png","default":False,"hidden":False},
         {"id":"171","type":2,"name":"컬러풀 집게 장난감","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_02_17.png","default":False,"hidden":False},
         {"id":"172","type":2,"name":"불과 얼음의 축제","grade":4,"icon":"efui_iconatlas/all_quest/all_quest_01_85.png","default":False,"hidden":False},
         {"id":"168","type":1,"name":"어린 아만","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"169","type":2,"name":"교육용 해도","grade":3,"icon":"efui_iconatlas/all_quest/all_quest_01_51.png","default":False,"hidden":False},
         {"id":"166","type":1,"name":"알폰스 베디체","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"19",
     "name":"볼다이크",
     "npcName":"구디스",
     "group":3,
     "items":[
        {"id":"181","type":1,"name":"라자람","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"180","type":1,"name":"베히모스","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"179","type":1,"name":"칼리나리 네리아","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"178","type":1,"name":"마레가","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"177","type":1,"name":"아이작","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"176","type":1,"name":"마리우","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"175","type":1,"name":"닐라이","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"174","type":1,"name":"베라드","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"275","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"274","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"195","type":3,"name":"무지개 정수","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_02_8.png","default":False,"hidden":False},
         {"id":"194","type":3,"name":"무지개 미끼","grade":1,"icon":"efui_iconatlas/all_quest/all_quest_05_47.png","default":False,"hidden":False},
         {"id":"193","type":3,"name":"마력이 스민 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_01_253.png","default":False,"hidden":False},
         {"id":"192","type":3,"name":"안정된 연성 촉매","grade":2,"icon":"efui_iconatlas/use/use_11_150.png","default":False,"hidden":False},
         {"id":"191","type":3,"name":"오징어","grade":4,"icon":"efui_iconatlas/use/use_11_127.png","default":False,"hidden":False},
         {"id":"190","type":2,"name":"볼다이칸 스톤","grade":4,"icon":"efui_iconatlas/use/use_11_135.png","default":False,"hidden":False},
         {"id":"189","type":2,"name":"속삭이는 휘스피","grade":3,"icon":"efui_iconatlas/use/use_11_136.png","default":False,"hidden":False},
         {"id":"188","type":2,"name":"쿠리구리 물약","grade":3,"icon":"efui_iconatlas/use/use_11_137.png","default":False,"hidden":False},
         {"id":"187","type":2,"name":"정체불명의 꼬리","grade":3,"icon":"efui_iconatlas/use/use_11_138.png","default":False,"hidden":False},
         {"id":"186","type":1,"name":"바르칸","grade":4,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"185","type":1,"name":"세헤라데","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"184","type":1,"name":"파이어혼","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"183","type":1,"name":"칼테이야","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"182","type":1,"name":"라카이서스","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"20",
     "name":"쿠르잔 남부",
     "npcName":"도니아",
     "group":2,
     "items":[
        {"id":"198","type":1,"name":"프타","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"197","type":1,"name":"네페르","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"196","type":1,"name":"게메트","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"276","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"277","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"210","type":3,"name":"줄기로 엮은 티아라","grade":2,"icon":"efui_iconatlas/lifelevel/lifelevel_02_21.png","default":False,"hidden":False},
         {"id":"209","type":3,"name":"구릿빛 반지","grade":2,"icon":"efui_iconatlas/lifelevel/lifelevel_02_23.png","default":False,"hidden":False},
         {"id":"208","type":3,"name":"거무스름한 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_02_13.png","default":False,"hidden":False},
         {"id":"207","type":3,"name":"군용 보급 정화제","grade":4,"icon":"efui_iconatlas/use/use_1_175.png","default":False,"hidden":False},
         {"id":"206","type":3,"name":"고급 정화제","grade":3,"icon":"efui_iconatlas/use/use_1_175.png","default":False,"hidden":False},
         {"id":"205","type":3,"name":"간이 정화제","grade":2,"icon":"efui_iconatlas/use/use_1_175.png","default":False,"hidden":False},
         {"id":"204","type":2,"name":"시들지 않는 불꽃","grade":4,"icon":"efui_iconatlas/use/use_12_2.png","default":False,"hidden":False},
         {"id":"203","type":2,"name":"흑요석 거울","grade":3,"icon":"efui_iconatlas/use/use_12_5.png","default":False,"hidden":False},
         {"id":"202","type":2,"name":"투케투스 고래 기름","grade":3,"icon":"efui_iconatlas/use/use_12_4.png","default":False,"hidden":False},
         {"id":"201","type":2,"name":"유황 버섯 납작구이","grade":3,"icon":"efui_iconatlas/use/use_12_3.png","default":False,"hidden":False},
         {"id":"200","type":1,"name":"다르키엘","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"199","type":1,"name":"까미","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False}
     ]},
    {"regionId":"21",
     "name":"쿠르잔 북부",
     "npcName":"콜빈",
     "group":1,
     "items":[
        {"id":"214","type":1,"name":"렌","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"216","type":2,"name":"아사르 가면","grade":3,"icon":"efui_iconatlas/use/use_12_125.png","default":False,"hidden":False},
         {"id":"217","type":2,"name":"전투 식량","grade":3,"icon":"efui_iconatlas/use/use_12_123.png","default":False,"hidden":False},
         {"id":"218","type":2,"name":"부서진 토우","grade":4,"icon":"efui_iconatlas/use/use_12_126.png","default":False,"hidden":False},
         {"id":"219","type":3,"name":"수상한 지도","grade":3,"icon":"efui_iconatlas/use/use_12_168.png","default":False,"hidden":False},
         {"id":"220","type":3,"name":"검은 미끼 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_02_38.png","default":False,"hidden":False},
         {"id":"221","type":3,"name":"조각난 금속 파편","grade":2,"icon":"efui_iconatlas/lifelevel/lifelevel_02_44.png","default":False,"hidden":False}
         ,{"id":"212","type":1,"name":"알키오네","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"211","type":1,"name":"아그리스","grade":1,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"278","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"279","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"213","type":1,"name":"타무트","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"215","type":2,"name":"둥근 뿌리 차","grade":3,"icon":"efui_iconatlas/use/use_12_124.png","default":False,"hidden":False}
     ]},
    {"regionId":"22",
     "name":"림레이크 남섬",
     "npcName":"재마",
     "group":1,
     "items":[
        {"id":"233","type":3,"name":"왠지 가벼운 빛바랜 황금 사과","grade":3,"icon":"efui_iconatlas/use/use_13_10.png","default":False,"hidden":False},
         {"id":"232","type":3,"name":"빛바랜 황금 사과","grade":3,"icon":"efui_iconatlas/use/use_13_10.png","default":False,"hidden":False},
         {"id":"231","type":3,"name":"밀가루","grade":2,"icon":"efui_iconatlas/lifelevel/lifelevel_02_79.png","default":False,"hidden":False},
         {"id":"230","type":2,"name":"유리 나비","grade":4,"icon":"efui_iconatlas/use/use_12_233.png","default":False,"hidden":False},
         {"id":"229","type":2,"name":"환영 잉크","grade":3,"icon":"efui_iconatlas/use/use_12_236.png","default":False,"hidden":False},
         {"id":"228","type":2,"name":"날씨 상자","grade":3,"icon":"efui_iconatlas/use/use_12_235.png","default":False,"hidden":False},
         {"id":"227","type":2,"name":"기묘한 주전자","grade":3,"icon":"efui_iconatlas/use/use_12_234.png","default":False,"hidden":False},
         {"id":"223","type":1,"name":"린","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"222","type":1,"name":"긴","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"280","type":2,"name":"영웅 호감도","grade":3,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"281","type":2,"name":"전설 호감도","grade":4,"icon":"efui_iconatlas/shop_icon/shop_icon_17.png","default":False,"hidden":True},
         {"id":"226","type":1,"name":"헤아누","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"225","type":1,"name":"란게","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"224","type":1,"name":"타라코룸","grade":2,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"237","type":1,"name":"파후","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"236","type":1,"name":"유즈","grade":3,"icon":"efui_iconatlas/use/use_2_13.png","default":False,"hidden":False},
         {"id":"235","type":3,"name":"불그스럼 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_02_92.png","default":False,"hidden":False},
         {"id":"234","type":3,"name":"비법의 주머니","grade":3,"icon":"efui_iconatlas/lifelevel/lifelevel_02_87.png","default":False,"hidden":False}
     ]}
]

# ------------------ 유틸 ------------------

# 하루 4구간 (start_hour, end_hour, end_minute)
periods = [
    (22, 3, 30),  # 22:00 ~ 03:30 (다음날)
    (4, 9, 30),   # 04:00 ~ 09:30
    (10, 15, 30), # 10:00 ~ 15:30
    (16, 21, 30)  # 16:00 ~ 21:30
]

def filter_active_reports(api_data):
    """
    현재 시각(KST)에 하루 4구간 중 하나에 포함되는 떠돌이 상인 보고서만 반환
    """
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    current_reports = []


    def in_period(dt):
        """datetime dt가 하루 4구간 중 하나에 속하는지 확인"""
        for start_hour, end_hour, end_minute in periods:
            start = dt.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            end = dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            if end <= start:  # 하루를 넘어가는 구간
                end += timedelta(days=1)
            if start <= dt <= end:
                return True
        return False

    for period in api_data:
        if not period:
            continue

        # UTC 문자열 -> datetime -> KST
        start = datetime.fromisoformat(period["startTime"].replace("Z", "+00:00")).astimezone(kst)
        end = datetime.fromisoformat(period["endTime"].replace("Z", "+00:00")).astimezone(kst)

        # 하루 4구간 포함 여부 + 현재 시각 체크
        if (in_period(start) or in_period(end)) and start <= now <= end:
            current_reports.extend(period.get("reports", []))

    return current_reports



# 예외 아이템 ID: 항상 포함
EXCEPTION_ITEMS = {"192"}  # 문자열로 itemId 넣기

def format_reports_by_region(current_data, is_on_sale):
    """
    서버별 떠돌이 상인 요약 텍스트 생성
    - type 1, type 2 아이템만 포함
    - grade 4 이상만 기본 포함
    - 예외 itemId "192"는 grade/type 상관없이 항상 포함
    - type 2 아이템은 "전설호감도 N개" 형식으로 개수 집계
    - type 1 아이템은 이름 그대로
    - 서버별 아이템 없으면 "없음"
    """
    from collections import defaultdict
    
    # itemId -> grade, type, name
    item_grade = {item["id"]: item["grade"] for r in LIST_MAP for item in r["items"]}
    item_type = {item["id"]: item["type"] for r in LIST_MAP for item in r["items"]}
    item_name = {item["id"]: item["name"] for r in LIST_MAP for item in r["items"]}

    server_dict_type1 = defaultdict(set)
    server_dict_type2 = defaultdict(list)

    for r in current_data:
        server = r["serverName"]
        # type 1,2 또는 예외 item만 포함, grade 4 이상
        items = [i for i in r["itemIds"]
                 if (item_type.get(i) in [1,2] and item_grade.get(i,0) >= 4) or i in EXCEPTION_ITEMS]

        for i in items:
            if i in EXCEPTION_ITEMS or item_type.get(i) == 1:
                server_dict_type1[server].add(item_name[i])
            elif item_type.get(i) == 2:
                server_dict_type2[server].append(i)

    lines = []
    for server in SERVER_MAP.values():
        # 서버 기록
        records = [r for r in current_data if r["serverName"] == server]
        
        if not records and not is_on_sale:
            lines.append(f"❙ {server}: 제보 데이터가 없음")
            continue
        
        type2_count = len(server_dict_type2.get(server, []))
        type2_items = [f"전설호감도 {type2_count}개"] if type2_count else []

        type1_items = list(server_dict_type1.get(server, []))
        all_items = type2_items + type1_items  # type2가 맨 앞

        if not all_items:
            all_items = ["없음"]

        lines.append(f"❙ {server}: {', '.join(all_items)}")
            

    return "\n".join(lines)

def get_remaining_time_text(remaining_text=""):
    """
    현재 시각(KST)에 하루 4구간 중 하나에 포함되는지 확인하고,
    포함된다면 종료시각까지 얼마나 남았는지 0시 00분 형식으로 계산
    """
    # KST 기준 현재 시각
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)

    # 하루 4구간 (start_hour, end_hour, end_minute)
    periods = [
        (22, 3, 30),  # 22:00 ~ 03:30 (다음날)
        (4, 9, 30),   # 04:00 ~ 09:30
        (10, 15, 30), # 10:00 ~ 15:30
        (16, 21, 30)  # 16:00 ~ 21:30
    ]

    for start_hour, end_hour, end_minute in periods:
        # 종료 시각 계산
        if start_hour > end_hour:  # 다음날로 넘어가는 경우
            end_time = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0) + timedelta(days=1)
            if now.hour >= start_hour or now.hour < end_hour:
                remaining = end_time - now
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                remaining_text += f"판매 마감까지 {hours}시간 {minutes:02d}분 남았습니다."
                return remaining_text
        else:
            start_time = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            if start_time <= now <= end_time:
                remaining = end_time - now
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                remaining_text += f"판매 마감까지 {hours}시간 {minutes:02d}분 남았습니다."
                return remaining_text

    # 어느 구간에도 속하지 않으면
    remaining_text += "현재 시각은 판매 구간이 아닙니다."
    return remaining_text

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
            server_data = resp.json()
            
            # 각 entry의 reports 안쪽에 server 정보 추가
            for entry in server_data:
                for report in entry.get("reports", []):
                    report["serverId"] = server_id
                    report["serverName"] = SERVER_MAP.get(server_id, server_id)
                    report["startTime"] = entry.get("startTime", "")
                    report["endTime"] = entry.get("endTime", "")
                all_data.append(entry)


        # 떠상 요약 텍스트 생성
        current_data = filter_active_reports(all_data)
        is_on_sale = get_remaining_time_text() == "현재 시각은 판매 구간이 아닙니다."
        response_text = "◕ᴗ◕🌸\n전체 서버 떠상 정보를 알려드릴게요.\n\n"
        response_text += format_reports_by_region(current_data, is_on_sale)
        response_text += f"\n\n{get_remaining_time_text()}"

        if request.method == "POST":
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [
                        {
                            "textCard": {
                                "description": summary_text,
                                "buttons": [
                                    {
                                        "label": "공유하기",
                                        "highlight": False,
                                        "action": "share"
                                    }
                                ],
                                "lock": False,
                                "forwardable": False
                            }
                        }
                    ],
                    "quickReplies": []
                }
            })
        
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
























































































































































