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

# [
#   {
#     "createdAt": "2025-08-18T07:00:28.177084Z",
#     "id": "746346665298894835",
#     "itemIds": [
#       "1",
#       "2",
#       "6",
#       "7"
#     ],
#     "regionId": "1",
#     "status": 2,
#     "upVoteCount": 0,
#     "user": {
#       "characterName": "생크림당근케이크",
#       "id": "357693218846277670",
#       "karmaRank": 6
#     },
#     "vote": null
#   },

  #   "serverId": "1",
  #   "serverName": "루페온",
  #   "startTime": "2025-08-18T07:00:00Z"
  # },


def format_reports_by_region(current_data):
    """
    서버별 떠돌이 상인 요약 텍스트 생성
    """
    server_entries = {}


    # 모든 데이터의 itemIds 순환
    for i in range(len(current_data)):
        print(f"data[{i}] 아이템들:")
    
        region_id = current_data[i]["regionId"]
    
        # LIST_MAP에서 해당 region 찾기
        region = next((r for r in LIST_MAP if r["regionId"] == region_id), None)
        if not region:
            continue
    
        for item_id in current_data[i]["itemIds"]:
            # region 안에서 itemId 찾기
            item = next((it for it in region["items"] if it["id"] == item_id), None)
            if item:
                result = {
                    "regionId": region["regionId"],
                    "regionName": region["name"],
                    "npcName": region["npcName"],
                    "group": region["group"],
                    "itemId": item["id"],
                    "itemName": item["name"],
                    "grade": item["grade"]
                }
                print("  -", result)
    
    for report in current_data:
        region_id = report.get("regionId")
        server_name = report.get("serverName", SERVER_MAP.get(str(report.get("serverId")), "알 수 없음"))
        npc_name = region_map.get(region_id, {}).get("npcName", "??")
        items_info = []

        for item_id in report.get("itemIds", []):
            # LIST_MAP에서 item 찾기
            found_item = None
            for r in LIST_MAP:
                if r["regionId"] == region_id:
                    for item in r["items"]:
                        if item["id"] == item_id:
                            found_item = item["name"]
                            break
            items_info.append(found_item if found_item else f"(아이템ID:{item_id})")

        if server_name not in server_entries:
            server_entries[server_name] = []
        server_entries[server_name].append(
            f"[{npc_name}] " + ", ".join(items_info)
        )

    # 최종 출력 정리
    lines = []
    for server in SERVER_ORDER:
        if server in server_entries:
            lines.append(f"◆ {server}")
            lines.extend(server_entries[server])

    return "\n".join(lines) if lines else "현재 출현 중인 떠돌이 상인 정보가 없습니다."



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
                all_data.append(entry)
        
        current_data = filter_active_reports(all_data)
        summary_text = format_reports_by_region(current_data)

        if request.method=="POST":
            return jsonify({"version":"2.0","template":{"outputs":[{"simpleText":{"text":summary_text}}]}})
        return all_data
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
























