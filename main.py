# flask_korlark.py
from flask import Flask, request, jsonify, copy_current_request_context, send_file, make_response
from flask_cors import CORS
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import requests
from datetime import datetime, timezone, timedelta
import os
import json
import time
import re
import logging
from collections import defaultdict
from wcwidth import wcswidth
import cairosvg
from io import BytesIO
from urllib.parse import unquote, quote
from PIL import Image


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 정보 출력
logger.info("여기출력2: %s", "여기출력2")

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

# 동시에 처리할 스레드 수
executor = ThreadPoolExecutor(max_workers=4)

# 🔑 발급받은 JWT 토큰
JWT_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6IktYMk40TkRDSTJ5NTA5NWpjTWk5TllqY2lyZyIsImtpZCI6IktYMk40TkRDSTJ5NTA5NWpjTWk5TllqY2lyZyJ9.eyJpc3MiOiJodHRwczovL2x1ZHkuZ2FtZS5vbnN0b3ZlLmNvbSIsImF1ZCI6Imh0dHBzOi8vbHVkeS5nYW1lLm9uc3RvdmUuY29tL3Jlc291cmNlcyIsImNsaWVudF9pZCI6IjEwMDAwMDAwMDA1ODU3OTMifQ.pGbLttyxM_QTAJxMGW2XeMYQ1TSfArJiyLv-TK4yxZJDes4nhnMfAlyJ6nSmVMHT6q2P_YqGkavwhCkfYAylI94FR74G47yeQuWLu3abw76wzBGN9pVRtCLu6OJ4RcIexr0rpQLARZhIiuNUrr3LLN_sbV7cNUQfQGVr0v9x77cbxVI5hPgSgAWAIcMX4Z7a6wj4QSnl7qi9HBZG1CH8PQ7ftGuBgFG7Htbh2ABj3xyza44vrwPN5VL-S3SUQtnJ1azOTfXvjCTJjPZv8rOmCllK9dMNoPFRjj7bsjeooYHfhK1rF9yiCJb9tdVcTa2puxs3YKQlZpN9UvaVhqquQg"

GEMINI_API_KEY = "AIzaSyBsxfr_8Mw-7fwr_PqZAcv3LyGuI0ybv08"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"

MARI_SHOP_URL = "https://m-lostark.game.onstove.com/Shop"

HEADERS = {
    "accept": "application/json",
    "authorization": f"bearer {JWT_TOKEN}"
}

# 현재 한국 시간 (naive)
KST = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST).replace(tzinfo=None)
TODAY = NOW_KST.date()

# 하루 범위: 오늘 06:00 ~ 다음날 05:59
# 06:00~23:59 조회 → 오늘 일정 기준
# 00:00~05:59 조회 → 전날 일정 기준

if NOW_KST.hour < 6:
    DAY_START = datetime.combine(NOW_KST.date() - timedelta(days=1), datetime.min.time()) + timedelta(hours=6)
else:
    DAY_START = datetime.combine(NOW_KST.date(), datetime.min.time()) + timedelta(hours=6)
DAY_END = DAY_START + timedelta(days=1) - timedelta(minutes=1)

# 요일 한글 매핑
WEEKDAY_KO = {
    'Monday':'월',
    'Tuesday':'화',
    'Wednesday':'수',
    'Thursday':'목',
    'Friday':'금',
    'Saturday':'토',
    'Sunday':'일'
}

# 로펙 랭킹 get
def fetch_lopec_ranking(nickname: str, character_class: str):
    """
    LOPEC API에서 캐릭터 랭킹 정보 가져오기
    필수: nickname, characterClass
    """
    url = "https://api.lopec.kr/api/ranking"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Flask-App/1.0",
        "Origin": "https://lopec.kr",
        "Referer": "https://lopec.kr/"
    }
    params = {
        "nickname": nickname,
        "characterClass": character_class
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=3)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        return {"error": "로펙 응답이 지연되고 있습니다."}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            return {"error": "잘못된 요청입니다. nickname과 characterClass를 확인하세요."}
        elif e.response.status_code == 503:
            return {"error": "로펙 서버가 점검 중입니다. 잠시 후 다시 시도해주세요."}
        else:
            return {"error": "랭킹 정보를 불러올 수 없습니다."}

    except requests.exceptions.RequestException as e:
        return {"error": f"로펙 서버와 통신 중 오류가 발생했습니다. ({e})"}

# -----------------------------
# SVG → PNG 변환 (카톡 친화적)
# -----------------------------
def ensure_png(icon_url, size=32, border_ratio=0.2):
    return f"https://loadora-flask.onrender.com/icon?url={quote(icon_url, safe='')}&size={size}&border={border_ratio}"

@app.route("/icon")
def icon():
    icon_url = request.args.get("url")
    if not icon_url:
        return "URL 파라미터가 없습니다", 400

    try:
        size = int(request.args.get("size", 32))
        border_ratio = float(request.args.get("border", 0.2))
        size = max(16, min(size, 64))
        border_ratio = max(0, min(border_ratio, 0.5))
    except:
        size = 32
        border_ratio = 0.2

    try:
        icon_url = unquote(icon_url)
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(icon_url, headers=headers, timeout=10)
        resp.raise_for_status()
        svg_content = resp.content

        png_bytes = cairosvg.svg2png(bytestring=svg_content)
        image = Image.open(BytesIO(png_bytes)).convert("RGBA")

        w, h = image.size
        if w != h:
            if w > h:
                left = (w - h) // 2
                image = image.crop((left, 0, left + h, h))
            else:
                top = (h - w) // 2
                image = image.crop((0, top, w, top + w))

        final_size = size
        canvas_size = int(final_size * (1 + border_ratio))
        new_image = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
        resized = image.resize((final_size, final_size), Image.ANTIALIAS)
        paste_pos = ((canvas_size - final_size) // 2, (canvas_size - final_size) // 2)
        new_image.paste(resized, paste_pos, resized)

        output = BytesIO()
        new_image.save(output, format="PNG", optimize=True)
        output.seek(0)

        return send_file(
            output,
            mimetype='image/png',
            as_attachment=False,
            download_name=None,
            conditional=False
        )

    except Exception as e:
        return f"SVG 처리 실패: {e}", 500

# 로펙 점수 post
def fetch_lopec_character(nickname: str, character_class: str):
    """
    LOPEC API에서 캐릭터 정보 가져오기
    필수: nickname, characterClass
    """
    url = "https://api.lopec.kr/api/character/stats"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Flask-App/1.0",
        "Content-Type": "application/json",
        "Origin": "https://lopec.kr",
        "Referer": "https://lopec.kr/"
    }
    payload = {
        "nickname": nickname,
        "characterClass": character_class
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=3)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        return {"error": "로펙 응답이 지연되고 있습니다."}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            return {"error": "잘못된 요청입니다. nickname과 characterClass를 확인하세요."}
        elif e.response.status_code == 503:
            return {"error": "로펙 서버가 점검 중입니다. 잠시 후 다시 시도해주세요."}
        else:
            return {"error": "로펙 정보를 불러올 수 없습니다."}

    except requests.exceptions.RequestException as e:
        return {"error": f"LOPEC 서버와 통신 중 오류가 발생했습니다. ({e})"}


def fetch_shop_html():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(MARI_SHOP_URL, headers=headers)
    return response.status_code, response.text

@app.route("/marishop")
def get_shop():
    status_code, content = fetch_shop_html()
    return jsonify({
        "status_code": status_code,
        "content": content
    })
    

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200  # 항상 200 OK를 반환

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # Render에서 지정한 포트 사용

# --- 사사게 API 호출 함수 ---
def fetch_sasage_html(keyword):
    CHAR_API_URL = "https://rloa.gg/api/inven-scrape"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/138.0.0.0 Whale/4.33.325.17 Safari/537.36",
        "Referer": "https://rloa.gg/search/inven"
    }
    params = {"keyword": keyword, "page": 1}  # page=1 고정
    response = requests.get(CHAR_API_URL, headers=headers, params=params)
    return response.status_code, response.json()  # JSON 반환

# --- 사사게 검색 API ---
@app.route("/sasage")
def get_sasage():
    keyword = request.args.get("keyword", "")
    status_code, data = fetch_sasage_html(keyword)
    return jsonify({
        "status_code": status_code,
        "data": data
    })


def parse_shop_items(html):
    """HTML을 받아 현재/이전 판매 상품 정보를 파싱"""
    
    item_pattern = re.compile(
        r'<span class="item-name">(.+?)</span>.*?class="list__price".*?<em>(\d+)</em>(?:\s*<del>(\d+)</del>)?',
        re.DOTALL
    )

    def clean_html_tags(text):
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    # --- 현재 판매 상품 ---
    current_section = html.split('<h3 class="shop-sub-title">이전 판매 상품</h3>')[0]
    current_desc_match = re.search(r'<p class="shop-dsc">\s*(.*?)\s*</p>', current_section, re.DOTALL)
    current_desc = clean_html_tags(current_desc_match.group(1)) if current_desc_match else ""

    current_items = []
    for name, price, original_price in item_pattern.findall(current_section):
        price_val = int(price.strip())
        original_val = int(original_price.strip()) if original_price and original_price.strip().isdigit() else None

        current_items.append({
            "name": name.strip(),
            "price": price_val,
            "original_price": original_val,
            "discount_rate": round((original_val - price_val) / original_val * 100, 2) if original_val else None
        })

    # --- 이전 판매 상품 ---
    previous_section = html.split('<h3 class="shop-sub-title">이전 판매 상품</h3>')[1]
    block_pattern = re.compile(
        r'<p class="shop-dsc">\s*(.*?)\s*</p>(.*?)(?=<p class="shop-dsc">|$)',
        re.DOTALL
    )

    previous_blocks = []
    for desc_html, items_html in block_pattern.findall(previous_section):
        description = clean_html_tags(desc_html)
        items = []
        for name, price, original_price in item_pattern.findall(items_html):
            price_val = int(price.strip())
            original_val = int(original_price.strip()) if original_price and original_price.strip().isdigit() else None

            items.append({
                "name": name.strip(),
                "price": price_val,
                "original_price": original_val,
                "discount_rate": round((original_val - price_val) / original_val * 100, 2) if original_val else None
            })
        previous_blocks.append({"description": description, "items": items})

    return {
        "current_items": {
            "description": current_desc,
            "items": current_items
        },
        "previous_items": previous_blocks
    }

@app.route("/marishop-items")
def get_shop_items():
    status_code, html = fetch_shop_html()
    if status_code != 200:
        return jsonify({"error": "Failed to fetch shop page", "status_code": status_code}), status_code

    shop_data = parse_shop_items(html)
    return jsonify(shop_data)




# -----------------------------
# 클로아 랭킹 조회 api
# -----------------------------
def fetch_ranking(name: str):
    """korlark API에서 캐릭터 랭킹 데이터 가져오기"""
    url = f"https://api.korlark.com/lostark/characters/{name}/rank"

    headers = {
        "Accept": "*/*",
        "User-Agent": "Flask-App/1.0",
        "Origin": "https://kloa.gg",
        "Referer": "https://kloa.gg/"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 오류 발생 시 예외 발생
        return response.json()

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 503:
            return "랭킹 서버 점검 중입니다. 잠시 후 다시 시도해주세요."
        else:
            return "랭킹 정보를 불러올 수 없습니다."

    except requests.exceptions.RequestException as e:
        raise Exception(f"랭킹 서버와 통신 중 오류가 발생했습니다. ({e})") from e

@app.route("/ranking", methods=["GET"])
def get_ranking():
    # 쿼리 파라미터에서 name 가져오기
    character_name = request.args.get('characterName', '').strip()
    
    if not character_name:
        return jsonify({"error": "Missing required query parameter: characterName"}), 400

    data = fetch_ranking(character_name)
    return jsonify(data), (200 if "error" not in data else 500)

def fetch_calendar():
    url = "https://developer-lostark.game.onstove.com/gamecontents/calendar"
    try:
        response = requests.get(url, headers=HEADERS, timeout=3.5)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 503:
            raise Exception("서비스 점검 중입니다. 잠시 후 다시 시도해주세요.") from e
        else:
            raise Exception(f"이벤트 정보를 불러올 수 없습니다. (오류 코드: {e.response.status_code})") from e
    except requests.exceptions.RequestException as e:
        # 연결 시간 초과, DNS 오류 등
        raise Exception(f"서버와 통신 중 오류가 발생했습니다. ({e})") from e


@app.route('/calendar', methods=['GET'])
def get_calendar():
    try:
        data = fetch_calendar()
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "error": True,
            "message": str(e)
        }), 500

# 거래소 마켓 옵션 조회
@app.route('/markets_option', methods=['GET'])
def get_markets_option():
    try:
        data = fetch_markets_option()
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "error": True,
            "message": str(e)
        }), 500

def fetch_markets_option():
    url = "https://developer-lostark.game.onstove.com/markets/options"
    try:
        response = requests.get(url, headers=HEADERS, timeout=3.5)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 503:
            raise Exception("서비스 점검 중입니다. 잠시 후 다시 시도해주세요.") from e
        else:
            raise Exception(f"마켓 옵션 정보를 불러올 수 없습니다. (오류 코드: {e.response.status_code})") from e
    except requests.exceptions.RequestException as e:
        # 연결 시간 초과, DNS 오류 등
        raise Exception(f"서버와 통신 중 오류가 발생했습니다. ({e})") from e

# 거래소 아이템 조회
@app.route('/markets_items', methods=['POST'])
def get_markets_items():
    try:
        request_data = request.get_json()  # 클라이언트에서 전달한 검색 옵션(JSON body)
        data = fetch_markets_items(request_data)
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "error": True,
            "message": str(e)
        }), 500



@app.route('/markets/relic_engraving', methods=['GET'])
def search_relic_engraving():
    """
    유물 각인서 검색 함수
    쿼리 파라미터:
      - item_name: 검색할 각인서 이름
      - page_no: 조회할 페이지 번호 (선택, 기본값 0)
    예시: 
      https://loadora-flask.onrender.com/markets/relic_engraving?item_name=아드&page_no=1
    """
    try:
        item_name = request.args.get("item_name", "")
        page_no = int(request.args.get("page_no", 0))  # 기본값 0
        data = fetch_relic_engraving(item_name, page_no)  # 페이지 번호 인자로 전달
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": True, "message": str(e)}), 500

# 유각 조회 함수
def fetch_relic_engraving(item_name: str, page_no: int = 0):
    """
    유물 각인서 마켓 조회
    :param item_name: 검색할 각인서 이름
    :param page_no: 조회할 페이지 번호 (기본값 0)
    :return: API 응답 데이터
    """
    
    payload = {
        "Sort": "CURRENT_MIN_PRICE",  # [GRADE, YDAY_AVG_PRICE, RECENT_PRICE, CURRENT_MIN_PRICE]
        "CategoryCode": 40000,
        "CharacterClass": "",
        "ItemTier": 0,
        "ItemGrade": "유물",
        "ItemName": item_name,
        "PageNo": page_no,
        "SortCondition": "DESC"  # [ASC, DESC]
    }

    return fetch_markets_items(payload)

def fetch_markets_items(payload: dict):
    """
    Lost Ark 경매장 아이템 조회
    :param payload: 검색 조건 (dict)
    :return: API 응답 (json)
    """
    url = "https://developer-lostark.game.onstove.com/markets/items"
    
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=3.5)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 503:
            raise Exception("서비스 점검 중입니다. 잠시 후 다시 시도해주세요.") from e
        else:
            raise Exception(f"마켓 아이템 정보를 불러올 수 없습니다. (오류 코드: {e.response.status_code})") from e
    except requests.exceptions.RequestException as e:
        # 연결 시간 초과, DNS 오류 등
        raise Exception(f"서버와 통신 중 오류가 발생했습니다. ({e})") from e



# ---------- 원정대 API 요청 함수 ----------
def fetch_expedition(character_name: str, timeout: float = 5) -> dict:
    if not character_name:
        raise ValueError("캐릭터 이름을 입력해야 합니다.")
    
    url = f"https://developer-lostark.game.onstove.com/characters/{character_name}/siblings"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 503:
            raise Exception("서비스 점검 중입니다. 잠시 후 다시 시도해주세요.") from e
        else:
            raise Exception(f"원정대 정보를 불러올 수 없습니다. (오류 코드: {e.response.status_code})") from e
    except requests.exceptions.RequestException as e:
        raise Exception(f"서버와 통신 중 오류가 발생했습니다. ({e})") from e

# ---------- Flask 라우트 (쿼리 파라미터 사용) ----------
@app.route('/account/characters', methods=['GET'])
def get_expedition_route():
    character_name = request.args.get('characterName', '').strip()
    
    if not character_name:
        return jsonify({
            "error": True,
            "message": "characterName 쿼리 파라미터를 입력해주세요."
        }), 400
    
    try:
        data = fetch_expedition(character_name)
        # 필요하면 organize_characters_by_server(data) 적용 가능
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "error": True,
            "message": str(e)
        }), 500

def organize_characters_by_server(char_list):
    organized = {}
    for c in char_list:
        server = c.get("ServerName", "Unknown")
        organized.setdefault(server, []).append(c)
    return organized


def timeout_handler(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 현재 요청 컨텍스트 복사
            @copy_current_request_context
            def run_func():
                return func(*args, **kwargs)

            future = executor.submit(run_func)
            try:
                return future.result(timeout=seconds)
            except TimeoutError:
                response_text = "⚠️ 처리 시간이 너무 길어 응답하지 못했습니다. 잠시 후 다시 시도해주세요."
                return jsonify({
                    "version": "2.0",
                    "template": {
                        "outputs": [{"simpleText": {"text": response_text}}],
                        "quickReplies": []
                    }
                })
        return wrapper
    return decorator

@app.route("/fallback", methods=["POST"])
@timeout_handler(4.5)
def fallback():
    from datetime import datetime, timezone, timedelta
    from collections import defaultdict

    # 현재 한국 시간 (naive)
    KST = timezone(timedelta(hours=9))
    NOW_KST = datetime.now(KST).replace(tzinfo=None)
    TODAY = NOW_KST.date()
    
    # 하루 범위: 오늘 06:00 ~ 다음날 05:59
    # 06:00~23:59 조회 → 오늘 일정 기준
    # 00:00~05:59 조회 → 전날 일정 기준
    if NOW_KST.hour < 6:
        DAY_START = datetime.combine(NOW_KST.date() - timedelta(days=1), datetime.min.time()) + timedelta(hours=6)
    else:
        DAY_START = datetime.combine(NOW_KST.date(), datetime.min.time()) + timedelta(hours=6)
    DAY_END = DAY_START + timedelta(days=1) - timedelta(minutes=1)
    
    # 특수문자 참고 ❘ ❙ ❚ ❛ ❜
    server_down = False  # 서버 점검 여부 플래그
    
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

        # ---------- 1. 마리샵 관련 패턴 ----------
        match_marishop = re.match(r"^(\.마리샵|마리샵|\.ㅁㄹㅅ|ㅁㄹㅅ|.ㅁㄽ|ㅁㄽ)$", user_input)
        if match_marishop:
            status_code, html = fetch_shop_html()
            if status_code != 200:
                return "마리샵 페이지를 가져오는데 실패했습니다."
        
            parse_data = parse_shop_items(html)  # dict 형태
        
            # ---------- 텍스트 정제 ----------
            response_text = "◕ᴗ◕🌸\n현재 마리샵 판매 정보를 알려드릴게요.\n\n"
            response_text += "❙ 현재 판매 상품\n"
            
            for item in parse_data["current_items"]["items"]:
                raw_name = item["name"]
                            
                # 정규식으로 [숫자개] 패턴 분리
                match = re.search(r"\[(\d+)개\]", raw_name)
                if match:
                    count_value = match.group(1)
                    name = re.sub(r"\[\d+개\]", "", raw_name).strip()  # [] 부분 제거
                    count = f"[{count_value}개]"
                else:
                    name = raw_name.strip()
                    count = f"[{item['count']}개]" if "count" in item else ""
                
                price = str(item["price"]).ljust(3)

                # 할인률이 존재할 때 소수점 1자리까지 표시
                discount_rate = item.get("discount_rate")
                discount = f" ({discount_rate:.1f}% 할인)" if discount_rate is not None else ""
    
                response_text += f"- {price}💎: {count} {name} {discount}\n"
        
            # 이전 아이템
            for prev in parse_data.get("previous_items", []):
                response_text += f"\n❙ {prev.get('description', '')}\n"
                for item in prev.get("items", []):
                    raw_name = item["name"]
                            
                    # 정규식으로 [숫자개] 패턴 분리
                    match = re.search(r"\[(\d+)개\]", raw_name)
                    if match:
                        count_value = match.group(1)
                        name = re.sub(r"\[\d+개\]", "", raw_name).strip()  # [] 부분 제거
                        count = f"[{count_value}개]"
                    else:
                        name = raw_name.strip()
                        count = f"[{item['count']}개]" if "count" in item else ""
                
                    price = str(item["price"]).ljust(3)
                    
                    # 할인률이 존재할 때 소수점 1자리까지 표시
                    discount_rate = item.get("discount_rate")
                    discount = f" ({discount_rate:.1f}% 할인)" if discount_rate is not None else ""
                    
                    response_text += f"- {price}💎: {count} {name} {discount}\n"

        
        # ---------- 1. 공지 관련 패턴 ----------
        match_notice = re.match(r"^(\.공지|공지|\.ㄱㅈ|ㄱㅈ)$", user_input)
        if match_notice:
            url = "https://developer-lostark.game.onstove.com/news/notices"
        
            notice_types = ["공지", "점검", "상점", "이벤트"]
            all_notices = []
        
            for notice_type in notice_types:
                try:
                    resp = requests.get(url, headers=HEADERS, params={"type": notice_type}, timeout=5)
                    resp.raise_for_status()
                    notices = resp.json()
                    for n in notices:
                        n["Type"] = notice_type
                        all_notices.append(n)
                except requests.exceptions.HTTPError as e:
                    if e.response is not None and e.response.status_code == 503:
                        # 서버 점검 처리
                        items = inspection_item
                        server_down = True
                    else:
                        # 그 외 HTTP 오류
                        raise
                except Exception as e:
                    # 기타 예외
                    raise
        
            if not server_down and all_notices:  # ✅ 서버 점검이 아닐 때만 공지 정리
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
                
                    # 🔥 NEW 여부 체크 (24시간 이내)
                    new_label = ""
                    if dt_obj and (NOW_KST - dt_obj) <= timedelta(hours=24):
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

        # ---------- 2. 카게 관련 패턴 ----------
        match_chaos_gate = re.match(
            r"^(\.카오스게이트|카오스게이트|\.카게|카게|\.ㅋㅇㅅㄱㅇㅌ|ㅋㅇㅅㄱㅇㅌ|\.ㅋㄱ|ㅋㄱ)(.*)$",
            user_input
        )
        
        if match_chaos_gate:
            chaos_gate_command = match_chaos_gate.group(1).strip()
        
            # 전체 캘린더 데이터
            data = fetch_calendar()
        
            # CategoryName이 "카오스게이트"인 모든 아이템
            chaos_gates = [item for item in data if item.get("CategoryName") == "카오스게이트"]
        
            # 항상 초기화
            date_hours = defaultdict(list)
            overall_day_hours = []
            overall_night_hours = []

            remaining_text = ""
            time_text = ""
            header_title = f"카오스게이트({WEEKDAY_KO[TODAY.strftime('%A')]})"
            cards = []
        
            # ---------- 입장 시간 정리 및 전체 일정 채우기 ----------
            for gate in chaos_gates:
                for t in gate.get("StartTimes", []):
                    dt = datetime.fromisoformat(t)
            
                    # DAY_START ~ DAY_END 범위 기준 날짜 계산
                    if dt < DAY_START:
                        # DAY_START 이전이면 전날 날짜로
                        date = (DAY_START - timedelta(days=1)).date()
                    else:
                        date = DAY_START.date()
            
                    date_hours[date].append(dt.hour)
            
                    # 전체 일정 채우기
                    if DAY_START <= dt <= DAY_END:
                        overall_day_hours.append(dt.hour)
                    else:
                        overall_night_hours.append(dt.hour)
        
            # ---------- 전체 조회 처리 ----------
            if match_chaos_gate.group(2):
                text_chaos_gate = match_chaos_gate.group(2).strip()
                result = "◕ᴗ◕🌸\n전체 카오스게이트 정보를 알려드릴게요.\n――――――――――――――\n\n"
        
                if text_chaos_gate in ["전체", "ㅈㅊ"]:
                    # 최소 입장 레벨
                    all_levels = set()
                    for gate in chaos_gates:
                        for ri in gate.get("RewardItems", []):
                            if isinstance(ri, dict):
                                item_level = ri.get("ItemLevel")
                                if item_level:
                                    all_levels.add(item_level)
                    if all_levels:
                        result += f"❙ 최소 입장 레벨: {', '.join(map(str, sorted(all_levels)))}\n\n"
        
                    result += "❙ 카오스게이트 입장 시간\n"
        
                    # 전체 일정용 범위 계산
                    for date_key in sorted(date_hours.keys()):
                        hours = date_hours[date_key]
                        day_hours = sorted(h for h in hours if 7 <= h <= 23)
                        night_hours = sorted(h for h in hours if 0 <= h <= 6)
        
                        day_part = f"{day_hours[0]:02d}시~{day_hours[-1]:02d}시" if day_hours else ""
                        night_part = f"다음날 {night_hours[0]:02d}시~{night_hours[-1]:02d}시" if night_hours else ""
                        display = ", ".join(part for part in [day_part, night_part] if part)
                        weekday = WEEKDAY_KO[date_key.strftime("%A")]
                        result += f"- {date_key.strftime('%Y년 %m월 %d일')}({weekday}) : {display}\n"
        
                    # 남은 시간 계산
                    remaining_time = None
                    next_hour_display = None
                    for date_key in sorted(date_hours.keys()):
                        for h in sorted(date_hours[date_key]):
                            dt_check = datetime.combine(date_key, datetime.min.time()) + timedelta(hours=h)
                            if dt_check > NOW_KST:
                                remaining_time = dt_check - NOW_KST
                                next_hour_display = h
                                break
                        if remaining_time:
                            break
        
                    items = [{"simpleText": {"text": result, "extra": {}}}]
        
                else:
                    items = [
                        {"simpleText": {"text": "◕_◕💧\n정보를 조회할 수 없어요. '.카게 전체'를 정확하게 입력해주세요.", "extra": {}}}
                    ]
        
            # ---------- 오늘 카게 정보 ----------
            else:
                if chaos_gates:
                    icon = chaos_gates[0].get("ContentsIcon", "")
                    # 최소 입장 레벨
                    all_levels = set()
                    for gate in chaos_gates:
                        for ri in gate.get("RewardItems", []):
                            if isinstance(ri, dict):
                                item_level = ri.get("ItemLevel")
                                if item_level:
                                    all_levels.add(item_level)
                    items_text = f"레벨: {', '.join(map(str, sorted(all_levels)))}\n\n" if all_levels else ""
        
                    cards.append({
                        "title": "카오스게이트",
                        "imageUrl": icon,
                        "messageText": ".카오스게이트 전체",
                        "link": {"web": ""},
                        "description": "💡상세 정보 클릭",
                        "action": "message"
                    })
        
                    # 남은 시간 계산
                    remaining_time = None
                    next_hour_display = None
                    for date_key in sorted(date_hours.keys()):
                        for h in sorted(date_hours[date_key]):
                            dt_check = datetime.combine(date_key, datetime.min.time()) + timedelta(hours=h)
                            if DAY_START <= dt_check <= DAY_END and dt_check > NOW_KST:
                                remaining_time = dt_check - NOW_KST
                                next_hour_display = h
                                break
                        if remaining_time:
                            break
        
                    if remaining_time:
                        hours_left, remainder = divmod(int(remaining_time.total_seconds()), 3600)
                        minutes_left = remainder // 60
                        remaining_text = f"{next_hour_display}시까지 {hours_left}시간 {minutes_left}분 남았습니다."
                    else:
                        remaining_text = "오늘 남은 카오스게이트가 없습니다."
        
                    # 전체 일정 표시
                    overall = []
                    if overall_day_hours:
                        overall.append(f"{min(overall_day_hours):02d}시~{max(overall_day_hours):02d}시")
                    if overall_night_hours:
                        overall.append(f"다음날 {min(overall_night_hours):02d}시~{max(overall_night_hours):02d}시")
                    time_text = ", ".join(overall) if overall else "정보 없음"
        
                    # 카드 footer
                    card_footer = {
                        "title": f"⏰ {remaining_text}",
                        "link": {"web": ""},
                        "description": f"일정: {time_text}"
                    }
                    cards.append(card_footer)
        
                    items = [
                        {"simpleText": {"text": "◕ᴗ◕🌸\n오늘의 카오스게이트 정보를 알려드릴게요.", "extra": {}}},
                        {
                            "listCard": {
                                "header": {"title": header_title},
                                "items": cards,
                                "buttons": [{"label": "공유하기", "highlight": False, "action": "share"}],
                                "lock": False,
                                "forwardable": False
                            }
                        }
                    ]
                else:
                    items = [
                        {"simpleText": {"text": "◕_◕💧\n오늘은 카오스게이트가 없어요.", "extra": {}}},
                        {
                            "listCard": {
                                "header": {"title": header_title},
                                "items": [{
                                    "title": "카오스게이트 없음",
                                    "imageUrl": "",
                                    "messageText": ".카오스게이트 전체",
                                    "link": {"web": ""},
                                    "description": "💡상세 정보 클릭",
                                    "action": "message"
                                }],
                                "buttons": [{"label": "공유하기", "highlight": False, "action": "share"}],
                                "lock": False,
                                "forwardable": False
                            }
                        }
                    ]

        # ---------- 3. 모험섬 일정 관련 패턴 ----------
        match_adventure_island = re.match(r"^(\.모험섬|모험섬|\.ㅁㅎㅅ|ㅁㅎㅅ)(.*)$", user_input)
        if match_adventure_island:
            island_content = match_adventure_island.group(1).strip()

            # 전체 캘린더 데이터
            data = fetch_calendar()
            
            if match_adventure_island.group(2):
                selected_island = match_adventure_island.group(2).strip()

                # CategoryName이 "모험 섬"이고, ContentsName이 selected_island인 모든 아이템
                selected_island_items = [
                    item for item in data
                    if item.get("CategoryName") == "모험 섬"
                    and item.get("ContentsName") == selected_island
                ]
                
                if selected_island_items:
                    result = f"◕ᴗ◕🌸\n❛{selected_island}❜ 정보를 알려드릴게요.\n"
                    result += f"――――――――――――――\n\n"
                    contents_icon = ""

                    for island in selected_island_items:
                        min_item_level = island.get("MinItemLevel", "없음")
                        start_times = island.get("StartTimes", []) or []
                        contents_icon = island.get("ContentsIcon", "")
                        
                        result += f"❚ 최소 입장 레벨: {min_item_level}\n\n"


                        # ---------- 입장 시간 처리 ----------
                        start_times_raw = island.get("StartTimes")  # None 그대로 받음
                        date_dict = defaultdict(list)
                        result += "❚ 모험섬 입장 시간\n"
                        
                        if start_times_raw is None:
                            # null 그대로 표시
                            result += "- null\n"
                        else:
                            start_times = start_times_raw or []  # 빈 리스트 방어
                            for t in start_times:
                                dt = datetime.fromisoformat(t)
                                weekday = WEEKDAY_KO[dt.strftime("%A")]  # 영어 요일 → 한글 요일
                                date_key = dt.strftime(f"%Y년 %m월 %d일") + f"({weekday})"
                                hour_str = dt.strftime("%H시")
                                date_dict[date_key].append(hour_str)
                        
                            if date_dict:
                                for date_key in sorted(date_dict.keys()):
                                    hours = sorted(set(date_dict[date_key]), key=lambda x: int(x.replace("시", "")))
                                    result += f"- {date_key} : {', '.join(hours)}\n"
                            else:
                                result += "- 없음\n"
                        result += "\n"
                        
                        # ---------- 아이템 목록 처리 ----------
                        result += f"❚ 아이템 목록\n"
                        items_set = set()
                        for reward_group in island.get("RewardItems", []):
                            for reward in reward_group.get("Items", []):
                                grade = reward.get("Grade", "")
                                name = reward.get("Name", "")
                                display_name = f"{name}[{grade}]" if grade else name
                                items_set.add(display_name)
                        
                        sorted_items = sorted(items_set)
                        if sorted_items:
                            result += "\n".join(f"- {item}" for item in sorted_items)
                        else:
                            result += "- 없음"
            
                
                    items = [
                        {"simpleImage": {"imageUrl": contents_icon, "altText": f"{selected_island}"}},
                        {"simpleText": {"text": result, "extra": {}}},
                    ]
                else:
                    items = [
                        {"simpleText": {"text": f"◕_◕💧\n❛{selected_island}❜ 정보를 조회할 수 없어요. 모험섬 이름을 정확하게 입력해주세요.", "extra": {}}},
                    ]
    
            else:
                selected_island = None  # 접두사만 입력한 경우 전체 표시
    
                today = NOW_KST.date()  # 현재 한국 시간 (naive)
                
                # 오늘 진행하는 모험섬만 필터링
                adventure_islands = [
                    item for item in data
                    if item.get("CategoryName") == "모험 섬"
                    and any(datetime.fromisoformat(t).date() == today for t in (item.get("StartTimes") or []))
                ]

                print('모험섬정보', adventure_islands)

                cards = []
                all_today_times = []
                
                # 기본값 안전 초기화
                time_text = "일정 없음"
                remaining_text = "오늘 남은 일정이 없습니다."
                header_title = f"모험섬({WEEKDAY_KO[today.strftime('%A')]})"
                            
                for island in adventure_islands:
                    name = island.get("ContentsName")
                    times = island.get("StartTimes", []) or []
                    icon = island.get("ContentsIcon")
                
                    # RewardItems 안전 처리
                    reward_items = []
                    for ri in island.get("RewardItems", []):
                        if isinstance(ri, dict):
                            items_list = ri.get("Items", [])
                            reward_items.extend([item["Name"] for item in items_list if item.get("Name")])
                
                    # ---------------- items_text 정제: 특정 키워드 그룹화 ----------------
                    if reward_items:
                        group_keywords = {
                            "카드 팩": "카드",
                            "카드": "카드",
                            "실링": "실링",
                            "섬의 마음": "섬마",
                            "비밀지도": "지도",
                            "모험물": "모험물",
                            "탈것": "탈것",
                            "크림스네일의 동전": "주화",
                            "해적 주화": "해적주화",
                            "대양의 주화": "대양주화",
                            "설치물": "설치물",
                            "변신": "변신",
                            "영혼의 잎사귀": "경카",
                            "경험치 카드": "경카",
                            "골드": "골드",
                            "선원지원서": "선원",
                            "수호석 조각": "3티재료",
                            "파괴석 조각": "3티재료",
                            "숨결": "4티재료",
                            "감정표현": "감정표현",
                            "돛문양": "돛문양",
                            "물약": "물약",
                            "모코콩 아일랜드 주화": "모코콩주화",
                            "버즐링 아일랜드 레이스 코인": "버즐링코인",
                            "명예의 파편": "3티파편",
                            "운명의 파편": "4티파편",
                            "각인서": "각인서",
                            "보석": "보석",
                            "미술품": "미술품",
                            "젬": "젬"
                        }
                
                        grouped = defaultdict(int)
                        other_items = []
                
                        for item in reward_items:
                            matched = False
                            item_clean = item.replace(" ", "")  # 공백 제거
                            for keyword, group_name in group_keywords.items():
                                keyword_clean = keyword.replace(" ", "")
                                if keyword_clean in item_clean:
                                    grouped[group_name] += 1
                                    matched = True
                                    break
                            if not matched:
                                other_items.append(item)
                
                        # 그룹화된 아이템 + 나머지 합쳐서 문자열 생성
                        items_text = "/".join([f"{name}" for name, cnt in grouped.items()] + other_items)
                    else:
                        items_text = "없음"
                        
                    # 오늘 일정만 ISO 문자열로 수집
                    today_times = [t for t in times if datetime.fromisoformat(t).date() == today]
                    
                    for t in today_times:
                        if t not in all_today_times:
                            all_today_times.append(t)
                        
                    cards.append({
                        "title": name,
                        "imageUrl": icon,
                        "messageText": f".모험섬 {name}",
                        "link": {"web": island.get("Link", "")},
                        "description": f"{items_text}",
                        "action": "message"
                    })

                # adventure_islands 있을 때만 footer 추가
                if adventure_islands:
                    all_today_times = sorted(all_today_times)
                    time_strings = [f"{datetime.fromisoformat(t).hour}시" for t in all_today_times]
                    time_text = ", ".join(time_strings) if time_strings else "일정 없음"
                    
                    future_times = [datetime.fromisoformat(t) for t in all_today_times if datetime.fromisoformat(t) > NOW_KST]
                    if future_times:
                        next_time = min(future_times)
                        remaining = next_time - NOW_KST
                        total_seconds = int(remaining.total_seconds())
                        hours, remainder = divmod(total_seconds, 3600)
                        minutes = remainder // 60
                        remaining_text = f"{next_time.hour:02d}시까지 {hours}시간 {minutes}분 남았습니다."
                    else:
                        remaining_text = "오늘 남은 일정이 없습니다."
                    
                    card_footer = {
                        "title": f"⏰ {remaining_text}",
                        "link": {"web": ""},
                        "description": f"일정: {time_text}"
                    }
                    cards.append(card_footer)
                
                if adventure_islands:
                    # 모험섬 데이터가 있을 때만
                    items = [
                        {"simpleText": {"text": "◕ᴗ◕🌸\n오늘의 모험섬 정보를 알려드릴게요.\n💡섬의 상세 정보를 보려면 클릭하세요.", "extra": {}}},
                        {
                            "listCard": {
                                "header": {"title": header_title},
                                "items": cards,
                                "buttons": [{"label": "공유하기", "highlight": False, "action": "share"}],
                                "lock": False,
                                "forwardable": False
                            }
                        }
                    ]
                else:
                    # 데이터 없으면 텍스트 카드만
                    items = [
                        {"simpleText": {"text": "◕_◕💧\n오늘은 모험섬이 없어요.", "extra": {}}}
                    ]

        # ---------- 3. 캘린더 or 일정 관련 패턴 ----------
        match_calendar = re.match(r"^(\.캘린더|캘린더|\.ㅋㄹㄷ|ㅋㄹㄷ|\.일정|일정|\.ㅇㅈ|ㅇㅈ|\.컨텐츠|컨텐츠|\.ㅋㅌㅊ|ㅋㅌㅊ)$", user_input)
        if match_calendar:
            calendar_command = match_calendar.group(1).strip()
            
            # 공식 api에서 데이터 받아오기
            data = fetch_calendar()
        
            # 카테고리별 분류
            adventure_island_its = [item for item in data if item.get("CategoryName") == "모험 섬"]
            chaos_gate_its      = [item for item in data if item.get("CategoryName") == "카오스게이트"]
            field_boss_its      = [item for item in data if item.get("CategoryName") == "필드보스"]
            voyage_its          = [item for item in data if item.get("CategoryName") == "항해"]
            rowen_its           = [item for item in data if item.get("CategoryName") == "로웬"]
        
            # 카테고리별로 오늘 일정 출력
            categories = [
                ("카오스게이트", chaos_gate_its),
                ("필드보스", field_boss_its),
                ("모험섬", adventure_island_its),
                ("항해협동", voyage_its),
                # ("로웬", rowen_its)
            ]
            
            # ---------- 오늘 일정 필터링 ----------
            def filter_today_times(it):
                print('it 값이 뭘까요: ', it)
            
                if not it or not isinstance(it, dict):
                    return []
            
                times = []
                start_times = it.get("StartTimes") or []   # None 방지
                for t in start_times:
                    try:
                        dt = datetime.fromisoformat(t)
                        if dt.tzinfo:
                            dt = dt.astimezone(KST).replace(tzinfo=None)
                        if DAY_START <= dt <= DAY_END:
                            times.append(dt)
                    except Exception as e:
                        print("시간 파싱 오류:", t, e)
            
                return sorted(times)

        
            # ---------- 반복 일정 요약 ----------
            def summarize_times(times):
                if not times:
                    return ": 없음"

                def format_time(dt):
                    hour = dt.hour
                    minute = dt.minute
                
                    # 분이 50일 때만 다음 시간으로 올림
                    if minute == 50:
                        hour += 1
                        if hour == 24:
                            hour = 0
                        minute = 0  # 반올림 후 분은 0으로 처리
                
                    if minute == 0:
                        return f"{hour:02d}시"
                    else:
                        return f"{hour:02d}시 {minute:02d}분"
                
                if len(times) == 1:
                    return format_time(times[0])
                
                # 일정 간격 확인
                intervals = [(times[i + 1] - times[i]).seconds // 60 for i in range(len(times) - 1)]
                if all(interval == intervals[0] for interval in intervals):
                    start, end = times[0], times[-1]
                    end_text = f"다음날 {format_time(end)}" if end.date() != start.date() else format_time(end)
                    return f"{format_time(start)} ~ {end_text} ({intervals[0]}분 간격)"
                
                # 불규칙 일정은 나열
                time_texts = []
                for dt in times:
                    day_prefix = "다음날 " if dt.date() != DAY_START.date() else ""
                    time_texts.append(f"{day_prefix}{format_time(dt)}")
                return ", ".join(time_texts)
        
            # ---------- 이름 그룹화 (공통 접두어만 밖으로) ----------
            def group_names(names):
                if len(names) == 1:
                    return f"❛{names[0]}❜"
            
                # 공통 접두어 추출
                prefix = names[0]
                for n in names[1:]:
                    min_len = min(len(prefix), len(n))
                    i = 0
                    while i < min_len and prefix[i] == n[i]:
                        i += 1
                    prefix = prefix[:i]
            
                prefix = prefix.rstrip(" (")
            
                # 접두어 제거 후 나머지
                suffixes = [n.replace(prefix, "").strip(" ()") for n in names]
                suffixes = [s for s in suffixes if s]
                
                if not prefix:
                    # 접두어 없으면 그냥 나열
                    formatted_names = []
                
                    for n in names:
                        its = next((x for x in adventure_island_its if x["ContentsName"] == n), None)
                        tags = []
                        if its:
                            for reward in its["RewardItems"]:
                                for item in reward["Items"]:
                                    if item["Name"] == "골드":
                                        tags.append("골드")
                        
                        tags = list(dict.fromkeys(tags))
                        tag_str = f"({', '.join(tags)})" if tags else ""
                        formatted_names.append(f"❛{n}{tag_str}❜")
                
                    return ", ".join(formatted_names)
            
                if len(suffixes) >= 8:
                    # 접두어 + 첫 번째 suffix, 나머지 외N
                    return f"{suffixes[0]} 외{len(suffixes)-1}"
            
                if suffixes:
                    return f"{', '.join(suffixes)}"
            
                return f"❛{prefix}❜"

        
            # ---------- 일정 요약 텍스트 생성 ----------
            response_text = "◕ᴗ◕🌸\n오늘의 컨텐츠 일정을 알려드릴게요.\n"
        
            for cat_name, its in categories:
                pattern_groups = defaultdict(list)  # key: 시간 요약, value: 이름
                for it in its:
                    today_times = filter_today_times(it)
                    summary = summarize_times(today_times)
                    if summary != ": 없음":
                        pattern_groups[summary].append(it["ContentsName"])
            
                response_text += f"\n❙ {cat_name}"
                if not pattern_groups:
                    response_text += ": 없음\n"
                else:
                    response_text += " ⭐\n"
                    for summary, names in pattern_groups.items():
                        response_text += f"- {group_names(names)}: {summary}\n"
                        
            
                # ---------- 남은 시간 계산 ----------
                # 오늘 일정 중 가장 빠른 시간이 현재보다 이후인 것 찾기
                upcoming_times = []
                for it in its:
                    for dt in filter_today_times(it):
                        if dt > NOW_KST:
                            upcoming_times.append(dt)
                if upcoming_times:
                    next_time = min(upcoming_times)
                    remaining = next_time - NOW_KST
                    
                    # 남은 시간 계산
                    total_minutes = remaining.seconds // 60
                    remaining_hours = total_minutes // 60
                    remaining_minutes = total_minutes % 60
                    
                    # next_time의 분
                    minutes = next_time.minute
                    
                    # 분에 따른 표시 방식 결정
                    if minutes == 0:
                        # 정시인 경우 그대로 표시
                        response_text += f"⏰ {next_time.strftime('%H시')}까지 {remaining_hours}시간 {remaining_minutes:02d}분 남았습니다.\n"
                    elif minutes == 50:
                        # 50분이면 next_time 표시만 반올림
                        rounded_time = next_time.replace(minute=0) + timedelta(hours=1)
                        # 반올림된 시간 기준으로 남은 시간 재계산
                        remaining_rounded = rounded_time - NOW_KST
                        total_minutes_rounded = remaining_rounded.seconds // 60
                        hours_rounded = total_minutes_rounded // 60
                        minutes_rounded = total_minutes_rounded % 60
                        response_text += f"⏰ {rounded_time.strftime('%H시')}까지 {hours_rounded}시간 {minutes_rounded:02d}분 남았습니다.\n"
                    elif remaining_hours > 0:
                        response_text += f"⏰ {next_time.strftime('%H시 %M분')}까지 {remaining_hours}시간 {remaining_minutes}분 남았습니다.\n"
                    else:
                        response_text += f"⏰ {next_time.strftime('%H시 %M분')}까지 {remaining_minutes}분 남았습니다.\n"
                else:
                    if pattern_groups:
                        response_text += "✅ 오늘 일정이 모두 종료되었습니다.\n"

        
            if len(response_text) < 400:
                use_share_button = True


        # ---------- 4. 원정대 관련 패턴 ----------
        match_expedition = re.match(r"^(\.원정대|원정대|\.ㅇㅈㄷ|ㅇㅈㄷ)\s*(.*)$", user_input)
        if match_expedition:
            expedition_char_name = match_expedition.group(2).strip()

            # 캐릭터 클래스명 축약 매핑
            CLASS_MAP = {
                "디스트로이어": "[디   트]",
                "워로드": "[워로드]",
                "버서커": "[버서커]",
                "홀리나이트": "[홀   나]",
                "슬레이어": "[슬   레]",
                "발키리": "[발키리]",
                "스트라이커": "[스   커]",
                "브레이커": "[브   커]",
                "배틀마스터": "[배   마]",
                "인파이터": "[인   파]",
                "기공사": "[기공사]",
                "창술사": "[창술사]",
                "데빌헌터": "[데   헌]",
                "블래스터": "[블   래]",
                "호크아이": "[호   크]",
                "스카우터": "[스   카]",
                "건슬링어": "[건   슬]",
                "바드": "[바   드]",
                "서머너": "[서머너]",
                "아르카나": "[알   카]",
                "소서리스": "[소   서]",
                "블레이드": "[블   레]",
                "데모닉": "[데모닉]",
                "리퍼": "[리   퍼]",
                "소울이터": "[소   울]",
                "도화가": "[도화가]",
                "기상술사": "[기   상]",
                "환수사": "[환수사]",
            }

            if not expedition_char_name:
                response_text = "◕_◕💧\n캐릭터 이름을 입력해주세요.\nex) .원정대 캐릭터명"
            else:
                try:
                    # 원정대 정보 받아오기
                    data = fetch_expedition(expedition_char_name)
                    
                    # 캐릭터 리스트를 서버별로 그룹화
                    organized_chars = organize_characters_by_server(data)
                    
                    if organized_chars:
                        expedition_text = f"◕ᴗ◕🌸\n❛{expedition_char_name}❜ 님의 원정대 정보를 알려드릴게요.\n\n"
                        for server, chars in organized_chars.items():
                            # ItemAvgLevel 숫자로 변환 후 높은 순으로 정렬
                            chars.sort(key=lambda x: float(str(x['ItemAvgLevel']).replace(',', '')), reverse=True)
                            
                            expedition_text += f"❙ {server} ({len(chars)}개)\n"
                            for c in chars:
                                class_display = CLASS_MAP.get(c['CharacterClassName'], f"[{c['CharacterClassName']}]")
                                item_avg = float(str(c['ItemAvgLevel']).replace(',', ''))  # 콤마 제거 후 float 변환
                                expedition_text += f"- {class_display} Lv.{c['CharacterLevel']} {c['CharacterName']} ({item_avg:,.2f})\n"
                            
                            expedition_text += "\n"
                        
                        response_text = expedition_text.strip()

                except requests.exceptions.HTTPError as e:
                    if e.response is not None and e.response.status_code == 503:
                        # 서버 점검 처리
                        items = inspection_item
                        server_down = True
                    else:
                        # 그 외 HTTP 오류
                        raise
                except Exception as e:
                    # 기타 예외
                    raise
    


        # ---------- 5. 이벤트 정보 관련 패턴 ----------
        match_event = re.match(r"^(\.이벤트|이벤트|\.ㅇㅂㅌ|ㅇㅂㅌ)$", user_input)
        if match_event:
            url = "https://developer-lostark.game.onstove.com/news/events"
        
            try:
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
                        
                        formatted_time = f"{start_date}~{end_date}"
                    
                        try:
                            start_obj = datetime.fromisoformat(start_date)
                            end_obj = datetime.fromisoformat(end_date)
                            formatted_time = f"{start_obj.strftime('%Y-%m-%d %H:%M')}~{end_obj.strftime('%Y-%m-%d %H:%M')}"

                            # D-day 계산
                            delta = (end_obj.date() - NOW_KST.date()).days
                            if delta > 8:
                                dday_str = f"D-{delta}"
                            elif delta > 0:
                                dday_str = f"D-{delta} ⏰임박"
                            elif delta == 0:
                                dday_str = "D-Day"
                            else:
                                dday_str = f"D+{abs(delta)}"
                        except Exception as e:
                            logging.error("날짜 변환 중 오류 발생: %s", e)
                            dday_str = "기간 확인 불가"

                    
                        # 🔥 NEW 여부 체크 (24시간 이내)
                        new_label = ""
                        if start_obj and timedelta(0) <= (NOW_KST - start_obj) <= timedelta(hours=24):
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
                if e.response is not None and e.response.status_code == 503:
                    # 서버 점검 처리
                    items = inspection_item
                    server_down = True
                else:
                    # 그 외 HTTP 오류
                    raise
            except Exception as e:
                # 기타 예외
                raise

        # ---------- 6. 메뉴 선택 관련 패턴 ----------
        match_command_list = re.match(r"^(\.명령어|명령어|\.도움말|도움말|\.ㅁㄹㅇ|ㅁㄹㅇ|\.ㄷㅇㅁ|ㄷㅇㅁ)$", user_input)
        if match_command_list:
            items = []

            로아_icon = "https://search.pstatic.net/sunny?src=https%3A%2F%2Fcdn-lostark.game.onstove.com%2F2018%2Fobt%2Fassets%2Fimages%2Fcommon%2Ficon%2Ffavicon.ico%3Fv%3D20251001074529&type=f30_30_png_expire24"
            골드_icon = "https://cdn-lostark.game.onstove.com/efui_iconatlas/money/money_4.png"
            크리스탈_icon = "https://cdn-lostark.game.onstove.com/uploadfiles/shop/11ef8e95ad2349e1af58728fc7bbfb44.png"
            레이드_icon = "https://cdn-lostark.game.onstove.com/uploadfiles/notice/fd6945f9ffa24b029bd44fd19245e695.png"
            유각_icon = "https://cdn-lostark.game.onstove.com/efui_iconatlas/use/use_9_25.png"
            카게_icon = "https://cdn-lostark.game.onstove.com/efui_iconatlas/island_icon/island_icon_147.png"

            # 부트스트랩 아이콘
            # -----------------------------
            공지_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/megaphone-fill.svg")
            일정_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/clipboard2-check-fill.svg")
            이벤트_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/gift-fill.svg")
            코인_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/coin.svg")
            카트_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/cart-fill.svg")
            크리스탈_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/gem.svg")
            위치_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/geo-alt-fill.svg")
            망원경_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/binoculars-fill.svg")
            위험꼬깔_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/cone-striped.svg")
            사람들_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/people-fill.svg")
            정보_icon = ensure_png("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/icons/person-lines-fill.svg")

            
            # 명령어 목록 (가나다 순)
            menu_list = [
                {"title": ".공지", "desc": "공식 홈페이지 공지 조회", "msg": ".공지", "img": 공지_icon},
                {"title": ".떠상", "desc": "떠돌이 상인 정보 조회", "msg": ".떠상", "img": 위치_icon},
                {"title": ".마리샵", "desc": "마리샵 아이템 조회", "msg": ".마리샵", "img": 카트_icon},
                {"title": ".모험섬", "desc": "오늘의 모험섬 정보 조회", "msg": ".모험섬", "img": 망원경_icon},
                {"title": ".사사게 [단어]", "desc": "인벤 사건사고게시판 검색", "msg": ".사사게", "img": 위험꼬깔_icon},
                {"title": ".시너지", "desc": "시너지 정보 조회", "msg": ".시너지", "img": 사람들_icon},
                {"title": ".유각", "desc": "유물 각인서 거래소 시세 조회", "msg": ".유각", "img": 유각_icon},
                {"title": ".이벤트", "desc": "진행중인 이벤트 조회", "msg": ".이벤트", "img": 이벤트_icon},
                {"title": ".일정", "desc": "오늘의 컨텐츠 일정 확인", "msg": ".일정", "img": 일정_icon},
                {"title": ".원정대 [단어]", "desc": "원정대 캐릭터 정보 조회", "msg": ".원정대", "img": 로아_icon},
                {"title": ".주급", "desc": "원정대 주급 조회", "msg": ".주급", "img": 코인_icon},
                {"title": ".정보 [단어]", "desc": "캐릭터 정보 조회", "msg": ".정보", "img": 정보_icon},
                {"title": ".카게", "desc": "카오스게이트 일정 조회", "msg": ".카게", "img": 카게_icon},
                {"title": ".클골", "desc": "레이드 클리어 골드 조회", "msg": ".클골", "img": 골드_icon},
            ]
        
            # 안내 문구
            items.append({
                "simpleText": {
                    "text": "◕ᴗ◕🌸\n전체 명령어를 알려드릴게요.\n💡원하는 메뉴를 클릭하세요."
                }
            })
        
            list_cards = []
            cards_per_page = 4  # 최대 4개로 제한
        
            # 4개씩 끊어서 listCard 구성
            for i in range(0, len(menu_list), cards_per_page):
                chunk = menu_list[i:i + cards_per_page]
                if not chunk:
                    continue
        
                list_items = []
                for menu in chunk:
                    list_items.append({
                        "title": menu["title"],
                        "description": menu["desc"],
                        "imageUrl": menu["img"],
                        "action": "message",
                        "messageText": menu["msg"],
                        "link": {"web": ""}
                    })
        
                page_no = (i // cards_per_page) + 1
        
                list_card = {
                    "header": {
                        "title": f"명령어 목록 {page_no}",
                        "link": {"web": ""}
                    },
                    "items": list_items,
                    "buttons": [],
                    "lock": False,
                    "forwardable": True
                }
        
                list_cards.append(list_card)
        
            # 비었을 때 예외 처리
            if not list_cards:
                list_cards.append({
                    "header": {"title": "명령어가 없습니다", "link": {"web": ""}},
                    "items": [{"title": "현재 표시할 명령어가 없습니다.", "link": {"web": ""}}],
                    "buttons": [],
                    "lock": False,
                    "forwardable": True
                })
        
            # 캐러셀 구성 (listCard 직접 삽입)
            carousel = {
                "carousel": {
                    "type": "listCard",
                    "items": list_cards
                }
            }
        
            items.append(carousel)
        
        # ---------- 6. 전체 서버 떠상 관련 패턴 ----------
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
            
                except requests.exceptions.HTTPError as e:
                    if e.response is not None and e.response.status_code == 503:
                        # 서버 점검 처리
                        items = inspection_item
                        server_down = True
                    else:
                        # 그 외 HTTP 오류
                        raise
                except Exception as e:
                    # 기타 예외
                    raise
            
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
        
            if len(response_text) < 400:
                use_share_button = True
                
        # ---------- 7. 주급 관련 패턴 ----------
        match_weekly = re.match(r"^(\.주급|주급|\.ㅈㄱ|ㅈㄱ)\s*(.*)$", user_input)
        if match_weekly:
            weekly_text = match_weekly.group(2).strip()
            if not weekly_text:
                response_text = "◕_◕💧\n캐릭터 이름을 입력해주세요.\nex) .주급 캐릭터명"
            else:
                response_text = f"◕ᴗ◕🌸\n❛{weekly_text}❜ 님의 주급 정보를 알려드릴게요.\n\n"
                response_text += f"[주급 명령어]\n내용: {weekly_text}"


        # ---------- 8. 클리어골드 관련 패턴 ----------
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

        # ---------- 9. 사사게 검색 관련 패턴 ----------
        sasage_match = re.match(r"^(\.사사게|사사게|\.ㅅㅅㄱ|ㅅㅅㄱㄱ)\s*(.*)$", user_input)
        if sasage_match:
            search_keyword = sasage_match.group(2).strip()
            
            if not search_keyword:
                response_text = "◕_◕💧\n검색어를 입력해주세요.\nex) .사사게 검색어"
            else:
                # 사사게 API 호출
                status_code, data = fetch_sasage_html(search_keyword)
        
                if status_code != 200 or not data.get("posts"):
                    response_text = f"◕ᴗ◕👍\n❛{search_keyword}❜의 사사게 검색 결과가 없습니다"
                else:
                    posts = data["posts"]
                    output_lines = [f"◕_◕❗\n❛{search_keyword}❜의 사사게 검색 결과가 {len(posts)}건 있습니다"]

                    for idx, post in enumerate(posts, start=1):
                        short_link = post.get("link").split('?')[0]  # ? 이후 제거
                        line = (
                            f"{idx}. [{post.get('category')}] {post.get('title')} ({short_link})\n"
                            f"   - 댓글: {post.get('commentCount',0)} | 추천: {post.get('recommendations',0)} | 시간: {post.get('timestamp')}"
                        )
                        output_lines.append(line)
                    
                    response_text = "\n\n".join(output_lines)

        # ---------- 9. 시너지 정보 관련 패턴 ----------
        synergy_match = re.match(r"^(\.시너지|시너지|\.ㅅㄴㅈ|ㅅㄴㅈ|.ㅅㄵ|ㅅㄵ)\s*(.*)$", user_input)
        if synergy_match:
            job_input = synergy_match.group(2).strip()

            # 직업 데이터 딕셔너리 (클래스 그룹 포함)
            job_data = {
                "전사 (슈샤이어)": {
                    "워로드(사멸H/비사멸)": {"codes": ["워로드", "ㅇㄹㄷ"], "synergy_info": "방감 12, 받피증4, 백헤드5"},
                    "디트(사멸H)": {"codes": ["디스트로이어", "ㄷㅅㅌㄹㅇㅇ", "디트", "ㄷㅌ"], "synergy_info": "방감 12"},
                    "버서커(사멸)": {"codes": ["버서커", "ㅂㅅㅋ"], "synergy_info": "받피증 6"},
                    "슬레이어(사멸)": {"codes": ["슬레이어", "ㅅㄹㅇㅇ", "슬레", "ㅅㄹ"], "synergy_info": "받피증 6"},
                    "홀리나이트(딜러)": {"codes": ["홀리나이트", "ㅎㄹㄴㅇㅌ", "홀나", "ㅎㄴ"], "synergy_info": "치명타 시 받피증 8"},
                    "홀리나이트(서폿)": {"codes": ["홀리나이트", "ㅎㄹㄴㅇㅌ", "홀나", "ㅎㄴ"], "synergy_info": "서포터 업데이트 필요"},
                    "발키리(딜러)": {"codes": ["발키리", "ㅂㅋㄹ"], "synergy_info": "치명타 시 받피증 8"},
                    "발키리(서폿)": {"codes": ["발키리", "ㅂㅋㄹ"], "synergy_info": "서포터 업데이트 필요"},
                },
                "무도가 (애니츠)": {
                    "창술사(사멸)": {"codes": ["창술사", "ㅊㅅㅅ", "창술", "ㅊㅅ"], "synergy_info": "치명타 시 받피증 8"},
                    "배틀마스터(사멸/비사멸)": {"codes": ["배틀마스터", "ㅂㅌㅁㅅㅌ", "배마", "ㅂㅁ"], "synergy_info": "치적 10, 공속 8, 이속 16"},
                    "스트라이커(사멸)": {"codes": ["스트라이커", "ㅅㅌㄹㅇㅋ", "스커", "ㅅㅋ"], "synergy_info": "치적 10, 공속 8"},
                    "인파이터(사멸)": {"codes": ["인파이터", "ㅇㅍㅇㅌ", "인파", "ㅇㅍ"], "synergy_info": "받피증 6"},
                    "브레이커(사멸H)": {"codes": ["브레이커", "ㅂㄹㅇㅋ", "브커", "ㅂㅋ"], "synergy_info": "받피증 6"},
                    "기공사(타대)": {"codes": ["기공사", "ㄱㄳ", "ㄱㄱㅅ", "기공", "ㄱㄱ"], "synergy_info": "공증 6"},
                },
                "헌터 (아르데타인)": {
                    "데빌헌터(사멸/타대)": {"codes": ["데빌헌터", "ㄷㅂㅎㅌ", "데헌", "ㄷㅎ"], "synergy_info": "치적 10"},
                    "건슬링어(타대)": {"codes": ["건슬링어", "ㄳㄹㅇ", "ㄱㅅㄹㅇ", "건슬", "ㄱㅅ"], "synergy_info": "치적 10"},
                    "호크아이(타대)": {"codes": ["호크아이", "ㅎㅋㅇㅇ", "호크", "ㅎㅋ"], "synergy_info": "받피증 6, 이속 4(두동)"},
                    "블래스터(타대)": {"codes": ["블래스터", "ㅂㄽㅌ", "ㅂㄹㅅㅌ", "블래", "ㅂㄹ"], "synergy_info": "방감 12"},
                    "스카우터(비사멸)": {"codes": ["스카우터", "ㅅㅋㅇㅌ", "스카", "ㅅㅋ"], "synergy_info": "공증 6"},
                },
                "마법사 (실린)": {
                    "서머너(타대)": {"codes": ["서머너", "ㅅㅁㄴ"], "synergy_info": "방감 12, 마나회복 40 (트포 선택)"},
                    "아르카나(타대)": {"codes": ["아르카나", "ㅇㄹㅋㄴ", "알카", "ㅇㅋ"], "synergy_info": "치적 10"},
                    "소서리스(타대)": {"codes": ["소서리스", "ㅅㅅㄹㅅ", "소서", "ㅅㅅ"], "synergy_info": "받피증 6"},
                    "바드(딜러)": {"codes": ["바드", "ㅂㄷ"], "synergy_info": "딜러 업데이트 필요"},
                    "바드(서폿)": {"codes": ["바드", "ㅂㄷ"], "synergy_info": "서포터 업데이트 필요"},
                },
                "암살자 (데런)": {
                    "리퍼(사멸B)": {"codes": ["리퍼", "ㄹㅍ"], "synergy_info": "방감12"},
                    "데모닉(사멸/타대)": {"codes": ["데모닉", "ㄷㅁㄴ"], "synergy_info": "받피증 6 (비사멸-충동, 사멸-억제)"},
                    "소울이터(타대)": {"codes": ["소울이터", "ㅅㅇㅇㅌ", "소울", "ㅅㅇ"], "synergy_info": "받피증 6 "},
                    "블레이드(사멸B)": {"codes": ["블레이드", "ㅂㄹㅇㄷ", "블레", "ㅂㄹ"], "synergy_info": "받피증 4, 백헤드 5, 공속 25, 이속 20"},
                },
                "스페셜리스트 (요즈)": {
                    "기상술사(타대)": {"codes": ["기상", "ㄱㅅ"], "synergy_info": "치적 10, 공속 12(질풍), 이속 12(질풍), 공감 10(이슬비)"},
                    "환수사(타대)": {"codes": ["환수사", "ㅎㅅㅅ", "환수", "ㅎㅅ"], "synergy_info": "방감 12"},
                    "도화가(딜러)": {"codes": ["도화가", "ㄷㅎㄱ"], "synergy_info": "서포터 업데이트 필요"},
                    "도화가(서폿)": {"codes": ["도화가", "ㄷㅎㄱ"], "synergy_info": "서포터 업데이트 필요"},
                },
            }

            # 전체 시너지 정보 함수 (클래스별로 출력)
            def get_full_synergy_info():
                result = "◕ᴗ◕🌸\n전체 시너지 정보를 알려드릴게요\n\n"
                class_items = list(job_data.items())
                for idx, (class_name, jobs) in enumerate(class_items):
                    result += f"✤ {class_name}\n"
                    for job_name, info in jobs.items():
                        result += f"{job_name}: {info['synergy_info']}\n"
                    if idx != len(class_items) - 1:
                        result += "\n"  # 마지막 클래스 뒤에는 공백 줄 추가하지 않음
                return result
        
            # 직업 매칭
            matched_job = None
            matched_class = None
            for class_name, jobs in job_data.items():
                for job_name, info in jobs.items():
                    if job_input in info["codes"]:
                        matched_job = job_name
                        matched_class = class_name
                        break
                if matched_job:
                    break
        
            # 출력
            if not job_input or not matched_job:
                # 입력 없거나 매칭 실패 → 전체 시너지 정보
                response_text = get_full_synergy_info()
            else:
                # 매칭 성공 → 해당 직업 시너지 정보
                response_text = f"◕ᴗ◕🌸\n'{matched_job}' 직업의 시너지 정보를 알려드릴게요\n\n✤ {matched_class}\n{matched_job}: {job_data[matched_class][matched_job]['synergy_info']}"

        # ---------- 9. 유각 거래소 조회 관련 패턴 ----------
        relic_match = re.match(r"^(\.유각|유각|\.ㅇㄱ|ㅇㄱ|\.유물각인서|유물각인서|\.ㅇㅁㄱㅇㅅ|ㅇㅁㄱㅇㅅ)\s*(.*)$", user_input)
        if relic_match:
            raw_input = relic_match.group(2).strip()  # 예: "유각10" 또는 "유각 10"
        
            # 숫자 추출: 예를 들어 "유각10"이면 max_count=10
            num_match = re.search(r"(\d+)", raw_input)
            max_count = int(num_match.group(1)) if num_match else None
        
            # 모든 숫자 제거 후 item_name 사용
            item_name = re.sub(r"\d+", "", raw_input).strip()  # "유각10" -> "유각"
        
            all_items = []
            page_no = 1
            while True:
                data = fetch_relic_engraving(item_name, page_no)
                data_items = data.get("Items", [])
                if not data_items:
                    break
        
                all_items.extend(data_items)
        
                # 최대 조회 개수 지정 시 체크
                if max_count and len(all_items) >= max_count:
                    all_items = all_items[:max_count]
                    break
        
                # 전체 데이터 개수보다 더 가져오지 않도록
                if len(all_items) >= data.get("TotalCount", 0):
                    break
        
                page_no += 1
        
            data_cnt = len(all_items)
            lines = [f"◕ᴗ◕🌸\n유물 각인서 가격을 알려드릴게요 ({data_cnt}개)\n"]
        
            if all_items:
                up_count = down_count = 0
                for entry in all_items:
                    name = entry.get('Name', '').replace('유물 ', '').replace(' 각인서', '')
                    current = entry.get('CurrentMinPrice', 0)
                    avg = entry.get('YDayAvgPrice', 0)
        
                    # 전일 대비 변화
                    if avg:
                        change_percent = (current - avg) / avg * 100
                        if change_percent > 0:
                            arrow = "🔺"
                            up_count += 1
                        elif change_percent < 0:
                            arrow = "📉"
                            down_count += 1
                        else:
                            arrow = "➖"
                        change_text = f"{change_percent:+.1f}%{arrow}"
                    else:
                        change_text = "N/A"
        
                    lines.append(f"❙ {current:,}💰 : {name} ({change_text})")
        
                # 상승/하락 메시지
                if up_count > down_count:
                    lines.insert(1, "📢 전체적으로 상승했어요")
                elif down_count > up_count:
                    lines.insert(1, "📢 전체적으로 하락했어요")
                else:
                    lines.insert(1, "📢 변동 개수가 비슷해요")
            else:
                lines.append(f"'{item_name}' 조회된 유물 각인서가 없습니다.\n이름을 다시 확인해주세요.")
        
            response_text = "\n".join(lines)
    
            if len(response_text) < 400:
                use_share_button = True
            
            print(response_text)
            


        
        # ---------- 9. 특정 캐릭터 정보 관련 패턴 ----------
        match_info = re.match(r"^(\.정보|정보|\.ㅈㅂ|ㅈㅂ)\s*(.*)$", user_input)
        if match_info:
            info_char_name = match_info.group(2).strip()
            
            if not info_char_name:
                response_text = "◕_◕💧\n캐릭터 이름을 입력해주세요.\nex) .정보 캐릭터명"
            else:
                # 공식 api에서 데이터 받아오기
                data = fetch_armory(info_char_name, "summary")

                # 로펙 기준 클래스 이름 변환
                passive_title = (data or {}).get("ArkPassive", {}).get("Title", "")
                class_name = (data or {}).get("ArmoryProfile", {}).get("CharacterClassName", "")
                initial_title = get_initial(passive_title) 
                character_class = f"{initial_title} {class_name}" if initial_title else class_name

                # 로펙 점수 POST
                lopec_score = fetch_lopec_character(info_char_name, character_class)
                
                if "error" in lopec_score:
                    lopec_total_sum_text = lopec_score["error"]  # 에러 메시지 직접 출력
                else:
                    lopec_total_sum = lopec_score.get("totalSum")
                    lopec_total_sum_text = f"{lopec_total_sum:,.2f}" if lopec_total_sum is not None else "정보 없음"

                # 로펙 랭킹 GET
                lopec_ranking = fetch_lopec_ranking(info_char_name, character_class)
                lopec_ranking_text = ""

                if "error" in lopec_ranking:
                    lopec_ranking_text = lopec_ranking["error"]
                
                elif "totalRank" in lopec_ranking and "classRank" in lopec_ranking:
                    total_rank = lopec_ranking["totalRank"]["rank"]
                    total_count = lopec_ranking["totalRank"]["total"]
                    total_percentage = lopec_ranking["totalRank"]["percentage"]
                
                    class_rank = lopec_ranking["classRank"]["rank"]
                    class_count = lopec_ranking["classRank"]["total"]
                    class_percentage = lopec_ranking["classRank"]["percentage"]
                
                    lopec_ranking_text = (
                        f"전체: {total_rank:,}위/{total_count:,} ({total_percentage:.2f}%)\n"
                        f"직업: {class_rank:,}위/{class_count:,} ({class_percentage:.2f}%)"
                    )
                else:
                    lopec_ranking_text = "랭킹 정보를 불러오지 못했습니다."
                

                # 전투정보실 바로가기 URL
                armory_url = f"https://lostark.game.onstove.com/Profile/Character/{info_char_name}"
                
                # 로펙(LOPEC) 바로가기 URL
                lopec_url = f"https://legacy.lopec.kr/mobile/search/search.html?headerCharacterName={info_char_name}"
                # 캐릭터 프로필 정보 ArmoryProfile
                armory = (data or {}).get("ArmoryProfile", {})
                
                character_image = armory.get("CharacterImage") or "정보 없음"
                server_name = armory.get("ServerName") or "정보 없음"
                item_avg_level = armory.get("ItemAvgLevel") or "정보 없음"
                combat_power = armory.get("CombatPower") or "정보 없음"
                combat_power_text = f"{combat_power}" if combat_power is not None else "정보 없음"
                guild_name = armory.get("GuildName") or "정보 없음"
                guild_member_grade = armory.get("GuildMemberGrade") or "정보 없음"
                character_level = armory.get("CharacterLevel") or "정보 없음"
                town_level = armory.get("TownLevel") or "정보 없음"
                town_name = "이름 없는 영지" if armory.get("TownName") == "컨텐츠 개방 필요" else armory.get("TownName", "정보 없음")
                expedition_level = armory.get("ExpeditionLevel") or "정보 없음"
                title = armory.get("Title") or "정보 없음"
                honor_point = f"{armory.get('HonorPoint')}점" if armory.get("HonorPoint") else "정보 없음"
                pvp_grade_name = armory.get("PvpGradeName") or "정보 없음"
                
                card_text = f"""# {character_class}

❙ 정보
원정대: Lv.{expedition_level}
영지: Lv.{town_level} {town_name}
PVP: {pvp_grade_name}
명예: {honor_point}
칭호: {title}
길드: {guild_name} ({guild_member_grade})
템렙: {item_avg_level}

❙ 점수
투력: {combat_power_text}
로펙: {lopec_total_sum_text}

❙ 로펙 랭킹
{lopec_ranking_text}

💡캐선창 이동 후 재시도 시 최신 데이터 확인 가능
"""

                logger.info("card_text정보: %s", card_text)
                
                # -----------------------------
                # 캐릭터 장비 정보
                # -----------------------------
                armory_equipment = (data or {}).get("ArmoryEquipment", [])
                # Weapon = armory_equipment
                # Helmet = 
                # Top = 
                # Bottom = 
                # Gloves = 
                # Shoulder = 
                
                # -----------------------------
                # 캐릭터 시너지 정보
                # -----------------------------
                
                # 시너지 패턴 및 키워드 정의
                patterns = ["자신 및 파티원", "파티원에게", "파티원은", "적중된 적의 모든", "적중된 적들의 모든", "아군의", "파티원의", "헤드 어택 및 백 어택"]
                without_patterns = [""]
                synergy_skills = []

                synergy_patterns_ordered = [
                    ("백헤드 받피증", ["백 어택", "헤드 어택", "받는", "피해", "증가"]),
                    ("치명타 시 받피증", ["치명타", "받는", "피해", "증가"]),
                    ("낙인력", ["낙인력"]),
                    ("낙인 받피증", ["낙인", "받는", "피해", "증가"]),
                    ("낙인 적주피", ["흔적", "적", "주는", "피해", "증가"]),
                    ("낙인 적주피", ["낙인", "적", "주는", "피해", "증가"]),
                    ("낙인 방감", ["낙인", "방어력", "감소"]),
                    ("생명력회복", ["생명력", "회복"]),
                    ("적주피", ["적", "주는", "피해", "증가"]),
                    ("받피증", ["받는", "피해", "증가"]),
                    ("받피감", ["받는", "피해", "감소"]),
                    ("진피증", ["진화형","피해","증가"]),
                    ("보호막생성", ["보호막", "부여"]),
                    ("보호막생성", ["보호막", "생성"]),
                    ("정화", ["해로운", "효과", "제거"]),
                    ("정화", ["해로운", "효과", "해제"]),
                    ("방감", ["방어력", "감소"]),
                    ("치적", ["치명타", "적중"]),
                    ("이속", ["이동", "속도"]),
                    ("공속", ["공격", "속도"]),
                    ("공증", ["공격력", "증가"]),
                    ("공감", ["공격력", "감소"]),
                    ("마나회복", ["마나", "회복"]),
                ]

                # 3️⃣ 문장 단위로 분리 후 요약
                def split_into_sentences(text):
                    """
                    한글 바로 뒤에 오는 문장종결(.!?)만 기준으로 분리한다.
                    이렇게 하면 6.0, 12.8 같은 소수점은 분리되지 않음.
                    """
                    text = re.sub(r'\s+', ' ', text).strip()
                    # 한글(가-힣) 바로 뒤에 나오는 . ! ? 로만 분리 (뒤에 공백 또는 문자열 끝)
                    parts = re.split(r'(?<=[가-힣])[.!?]+(?=\s|$)', text)
                    return [p.strip() for p in parts if p.strip()]

                def summarize_synergy_full(text):
                    sentences = split_into_sentences(text)
                    logger.info("여기출력sentences: %s", sentences)
                
                    results = []
                    for sentence in sentences:
                        if not any(pat in sentence for pat in patterns):
                            continue
                
                        context = re.sub(r'\s+', ' ', sentence)
                        logger.info("문장 처리 context: %s", context)
                
                        remaining_context = context  # 매칭 후 제거용


                        for key, words in synergy_patterns_ordered:
                            while all(re.search(r'\s+'.join(word.split()), remaining_context) for word in words):
                                keyword_match = re.search(r'\s+'.join(words[0].split()), remaining_context)
                                if not keyword_match:
                                    break
                                keyword_pos = (keyword_match.start(), keyword_match.end())
                        
                                percents = [(m.group(1), m.start()) for m in re.finditer(r'(\d+(?:\.\d+)?)\s*%', remaining_context)]
                        
                                if percents:
                                    # % 값이 있으면 기존 로직
                                    val, val_pos = min(percents, key=lambda x: abs((keyword_pos[0]+keyword_pos[1])//2 - x[1]))
                                    results.append(f"{key} {val}%")
                        
                                    # 매칭된 범위 제거
                                    start_remove = min(keyword_pos[0], val_pos)
                                    end_remove = max(keyword_pos[1], val_pos + len(val) + 1)
                                    remaining_context = remaining_context[:start_remove] + remaining_context[end_remove:]
                                else:
                                    # % 값이 없는 경우도 매칭 허용
                                    results.append(f"{key}")  
                                    logger.info("퍼센트 없는 시너지 매칭: %s", key)
                        
                                    # 키워드만 제거해서 중복 방지
                                    remaining_context = remaining_context[:keyword_pos[0]] + remaining_context[keyword_pos[1]:]

                
                    # 중복 제거(등장 순서 유지)
                    results = list(dict.fromkeys(results))
                    logger.info("최종 results: %s", results)
                
                    return " / ".join(results) if results else None





                def clean_html_tooltip(tooltip_text: str) -> str:
                    """
                    HTML 태그 제거 후 연속 공백을 정리하고 양쪽 공백을 제거합니다.
                    
                    Args:
                        tooltip_text (str): HTML 태그가 포함된 스킬/트리포드 툴팁 문자열.
                    
                    Returns:
                        str: HTML 태그가 제거되고 공백이 정리된 문자열.
                    """
                    # HTML 태그 제거
                    clean_text = re.sub(r"<.*?>", "", tooltip_text)
                    # 연속 공백 정리 및 양쪽 공백 제거
                    clean_text = re.sub(r"\s+", " ", clean_text).strip()
                    return clean_text
                    
                # -----------------------------
                # 스킬
                armory_skills = (data or {}).get("ArmorySkills", [])
                
                # -----------------------------
                # 1️⃣ ArmorySkills에서 시너지 필터링
                # -----------------------------
                for skill in armory_skills:
                    
                    skill_name = skill.get("Name", "")
                    skill_tooltip = skill.get("Tooltip", "")
                    skill_tripods = skill.get("Tripods", [])
                    skill_level = skill.get("Level", 0)

                    # -----------------------------
                    # (A) 스킬 자체 툴팁에서 시너지 찾기
                    # -----------------------------
                    if skill_tooltip and skill_level >= 2:
                        try:
                            tooltip_json = json.loads(skill_tooltip)
                
                            def search_values(obj):
                                if isinstance(obj, dict):
                                    for v in obj.values():
                                        search_values(v)
                                elif isinstance(obj, list):
                                    for v in obj:
                                        search_values(v)
                                elif isinstance(obj, str):
                                    logger.info("스킬스결과%s", obj)
                                    clean_text = clean_html_tooltip(obj)
                                    if any(pattern in clean_text for pattern in patterns):
                                        summary_text = summarize_synergy_full(clean_text)
                                        synergy_skills.append({
                                            "Name": skill_name,
                                            "Tooltip": clean_text,
                                            "Summary": summary_text,
                                            "Level": skill_level
                                        })
                
                            search_values(tooltip_json)
                
                        except Exception as e:
                            logger.warning("Tooltip JSON 파싱 실패: %s", e)
                
                # -----------------------------
                # 2️⃣ 아크패시브 Effects에서 시너지 필터링
                # -----------------------------

                # 아크패시브 및 Effects 가져오기
                armory_arkpassive = (data or {}).get("ArkPassive", [])
                effects = armory_arkpassive.get("Effects", [])
                
                for effect in effects:
                    skill_name = effect.get("Description", "")
                    skill_tooltip = effect.get("ToolTip", "")
                    
                    clean_name = clean_html_tooltip(skill_name)
                    skill_tooltip_json = json.loads(skill_tooltip)
                    
                    
                    for element in skill_tooltip_json.values():
                        value = element.get("value", "")
                        if isinstance(value, str):
                            clean_tooltip = clean_html_tooltip(value)
                            if any(pattern in clean_tooltip for pattern in patterns):
                                summary_text = summarize_synergy_full(clean_tooltip)
                                
                                synergy_skills.append({
                                    "Name": clean_name,
                                    "Tooltip": clean_tooltip,
                                    "Summary": summary_text
                                })
                    
                
                # -----------------------------
                # 3️⃣ preview_text 생성
                # -----------------------------
                lines = [f"❙ {character_class} 시너지 정보\n"]
                if synergy_skills:
                    for s in synergy_skills:
                        lines.append(f"• {s['Name']} : {s['Summary']}")
                        lines.append(f"  {s['Tooltip']}\n")
                else:
                    lines.append("• 시너지 관련 스킬 없음")
                
                preview_text = "\n".join(lines)



                
                if data:
                    
                    items = [
                        {
                            "simpleText": {
                                "text": f"◕ᴗ◕🌸\n❛{info_char_name}❜ 님의 캐릭터 정보를 알려드릴게요",
                                "extra": {}
                            }
                        },
                        {
                            "basicCard": {
                                "title": f"{server_name} 서버 | Lv.{character_level} {info_char_name}",
                                "description": card_text,
                                "thumbnail": {
                                    "imageUrl": character_image,
                                    "link": {
                                        "web": ""
                                    },
                                    "fixedRatio": True,
                                    "altText": f"{info_char_name} 캐릭터 이미지"
                                },
                                "buttons": [
                                    # {"label": "전투정보실", "action": "webLink", "webLinkUrl": armory_url, "highlight": True},
                                    {"label": "로펙", "action": "webLink", "webLinkUrl": lopec_url, "highlight": True},
                                    {"label": "공유하기", "highlight": False, "action": "share"}
                                ]
                            }
                        },
                        {
                            "simpleText": {
                                "text": preview_text,
                                "extra": {}
                            }
                        },
                    ]
                else:
                    # 데이터 없으면 텍스트 카드만
                    items = [
                        {
                            "textCard": {
                                "description": f"◕_◕💧\n❛{info_char_name}❜ 님의 최신화된 캐릭터 정보가 존재하지 않습니다. \n💡원정대 정보를 조회하려면 버튼을 클릭하세요.",
                                "buttons": [
                                    {
                                        "label": "원정대 정보",
                                        "highlight": False,
                                        "action": "message",
                                        "extra": {},
                                        "messageText": f".원정대 {info_char_name}"
                                    }
                                ],
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
    except TimeoutError:
        # 타임아웃 전용 응답
        response_text = "⚠️ \n처리 시간이 너무 길어 응답하지 못했습니다. 잠시 후 다시 시도해주세요."
        response = {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": response_text}}],
                "quickReplies": []
            }
        }
        return jsonify(response)
    except Exception as e:
        # 1️⃣ 로그 기록 (stack trace 포함)
        logger.exception("예외 발생: %s", e)
        
        # 2️⃣ 챗봇용 메시지 생성
        if server_down:
            response_text = f"⚠️ \n서비스 점검 중입니다. 잠시 후 다시 시도해주세요."
        else: 
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


# name → initial 변환 함수
def get_initial(name: str) -> str:
    for item in arkFilter:
        if item["name"] == name:
            return item["initial"]
    return name  # 없으면 원래 이름 반환

arkFilter = [
    {"name": "창술 수련", "initial": "고기"},
    {"name": "철옹성", "initial": "전태"},
    {"name": "강인한 육체", "initial": "비기"},
    {"name": "광기", "initial": "광기"},
    {"name": "중력 갑옷", "initial": "분망"},
    {"name": "중력 충격", "initial": "중수"},
    {"name": "빛의 기사", "initial": "빛의 기사"},
    {"name": "해방자", "initial": "서폿"},
    {"name": "신성한 의무", "initial": "심판자"},
    {"name": "신성 보호", "initial": "서폿"},
    {"name": "지치지 않는 힘", "initial": "처단"},
    {"name": "끝나지 않는 분노", "initial": "포식"},
    {"name": "기력 회복", "initial": "체술"},
    {"name": "속도 강화", "initial": "충단"},
    {"name": "강력한 체술", "initial": "초심"},
    {"name": "강력한 오의", "initial": "오의"},
    {"name": "세맥타통", "initial": "세맥"},
    {"name": "역천지체", "initial": "역천"},
    {"name": "절제", "initial": "절제"},
    {"name": "절정", "initial": "절정"},
    {"name": "일격필살", "initial": "일격"},
    {"name": "오의난무", "initial": "난무"},
    {"name": "권왕파천무", "initial": "권왕"},
    {"name": "수라의 길", "initial": "수라"},
    {"name": "전술 탄환", "initial": "전탄"},
    {"name": "핸드 거너", "initial": "핸건"},
    {"name": "죽음의 습격", "initial": "죽습"},
    {"name": "두 번째 동료", "initial": "두동"},
    {"name": "포격 강화", "initial": "포강"},
    {"name": "화력 강화", "initial": "화강"},
    {"name": "진화의 유산", "initial": "유산"},
    {"name": "아르데타인의 기술", "initial": "기술"},
    {"name": "피스메이커", "initial": "피메"},
    {"name": "사냥의 시간", "initial": "사시"},
    {"name": "황후의 은총", "initial": "황후"},
    {"name": "황제의 칙령", "initial": "황제"},
    {"name": "넘치는 교감", "initial": "교감"},
    {"name": "상급 소환사", "initial": "상소"},
    {"name": "구원의 선물", "initial": "서폿"},
    {"name": "진실된 용맹", "initial": "진실된 용맹"},
    {"name": "점화", "initial": "점화"},
    {"name": "환류", "initial": "환류"},
    {"name": "버스트 강화", "initial": "버스트"},
    {"name": "신속한 일격", "initial": "잔재"},
    {"name": "멈출 수 없는 충동", "initial": "충동"},
    {"name": "완벽한 억제", "initial": "억제"},
    {"name": "달의 소리", "initial": "달소"},
    {"name": "피냄새", "initial": "갈증"},
    {"name": "영혼친화력", "initial": "만월"},
    {"name": "그믐의 경계", "initial": "그믐"},
    {"name": "해의 조화", "initial": "서폿"},
    {"name": "회귀", "initial": "회귀"},
    {"name": "질풍노도", "initial": "질풍"},
    {"name": "이슬비", "initial": "이슬비"},
    {"name": "야성", "initial": "야성"},
    {"name": "환수 각성", "initial": "환각"},

    {"name": "핸드거너", "initial": "핸건"},
    {"name": "강화 무기", "initial": "전탄"},
    {"name": "고독한 기사", "initial": "고기"},
    {"name": "전투 태세", "initial": "전태"},
    {"name": "광전사의 비기", "initial": "비기"},
    {"name": "분노의 망치", "initial": "분망"},
    {"name": "중력 수련", "initial": "중수"},
    {"name": "심판자", "initial": "심판자"},
    {"name": "축복의 오라", "initial": "서폿"},
    {"name": "처단자", "initial": "처단"},
    {"name": "포식자", "initial": "포식"},
    {"name": "극의: 체술", "initial": "체술"},
    {"name": "충격 단련", "initial": "충단"},
    {"name": "초심", "initial": "초심"},
    {"name": "오의 강화", "initial": "오의"},
    {"name": "절실한 구원", "initial": "서폿"},
    {"name": "버스트", "initial": "버스트"},
    {"name": "잔재된 기운", "initial": "잔재"},
    {"name": "깔쯩", "initial": "갈증"},
    {"name": "만월의 집행자", "initial": "만월"},
    {"name": "만개", "initial": "서폿"},
]

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
        if start_hour > end_hour:  # 자정 넘어가는 구간
            # 종료 시각을 오늘 또는 내일로 조정
            end_time = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            if now.hour >= start_hour:  # 예: 23시~24시
                end_time += timedelta(days=1)
            if now.hour >= start_hour or now.hour < end_hour:
                remaining = end_time - now
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                remaining_text += f"⏰ 판매 마감까지 {hours}시간 {minutes:02d}분 남았습니다."
                return remaining_text
        else:
            start_time = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            if start_time <= now <= end_time:
                remaining = end_time - now
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                remaining_text += f"⏰ 판매 마감까지 {hours}시간 {minutes:02d}분 남았습니다."
                return remaining_text

    return remaining_text + "현재 시각은 판매 구간이 아닙니다."

# ------------------ Flask endpoints ------------------
@app.route("/")
def home():
    return "LoaDora API Flask 서버 실행 중"

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











































































































































































































































































































































































































































































































































































































































