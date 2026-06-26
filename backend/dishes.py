# -*- coding: utf-8 -*-
"""밥상 차리기 — 음식 카탈로그(레시피·정가·외식가). 순수 데이터, 모델 의존 없음.

기후 재료(kind="crop")는 6종 작물 중 하나로 분량(amount_kg)을 가지며
가격은 ClimateModel로 날씨에 따라 계산된다.
고정 재료(kind="fixed")는 정가(won)로 날씨와 무관하다.
eatout = 외식 기준 메뉴가(1인분, 평년). 외식 총액은 여기에 기후 상승분을 전가한다.
분량·정가·외식가·구매단위는 교육용 1인분 근사값이며 이 파일 한 곳에서 조정한다.
"""

CROPS = {"배추", "무", "사과", "쌀", "시금치", "양파"}

# 소비자 구매단위(소비자는 kg가 아니라 포기·개·망·단·포대로 산다)
UNITS = {
    "배추":  {"unit": "포기",      "kg": 2.5},
    "무":    {"unit": "개",        "kg": 1.0},
    "사과":  {"unit": "개",        "kg": 0.3},
    "쌀":    {"unit": "포대(20kg)", "kg": 20},
    "시금치": {"unit": "단",        "kg": 0.4},
    "양파":  {"unit": "망",        "kg": 1.5},
}

DISHES = [
    {"id": "rice", "name": "공기밥", "img": "rice.png", "emoji": "🍚", "eatout": 1000,
     "ingredients": [
         {"name": "쌀", "kind": "crop", "crop": "쌀", "amount_kg": 0.10},
     ]},
    {"id": "kimchi_jjigae", "name": "김치찌개", "img": "kimchi_jjigae.png", "emoji": "🥘", "eatout": 8000,
     "ingredients": [
         {"name": "배추", "kind": "crop", "crop": "배추", "amount_kg": 0.24},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.06},
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.04},
         {"name": "돼지고기", "kind": "fixed", "won": 1200},
         {"name": "두부", "kind": "fixed", "won": 600},
         {"name": "양념", "kind": "fixed", "won": 200},
     ]},
    {"id": "doenjang_jjigae", "name": "된장찌개", "img": "doenjang_jjigae.png", "emoji": "🍲", "eatout": 8000,
     "ingredients": [
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.06},
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.08},
         {"name": "시금치", "kind": "crop", "crop": "시금치", "amount_kg": 0.04},
         {"name": "두부", "kind": "fixed", "won": 600},
         {"name": "된장양념", "kind": "fixed", "won": 250},
     ]},
    {"id": "baechu_kimchi", "name": "배추김치", "img": "baechu_kimchi.png", "emoji": "🥬", "eatout": 2500,
     "ingredients": [
         {"name": "배추", "kind": "crop", "crop": "배추", "amount_kg": 0.28},
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.05},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.04},
         {"name": "사과", "kind": "crop", "crop": "사과", "amount_kg": 0.03},
         {"name": "고춧가루·젓갈", "kind": "fixed", "won": 500},
     ]},
    {"id": "mu_saengchae", "name": "무생채", "img": "mu_saengchae.png", "emoji": "🥗", "eatout": 2500,
     "ingredients": [
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.20},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.03},
         {"name": "사과", "kind": "crop", "crop": "사과", "amount_kg": 0.02},
         {"name": "양념", "kind": "fixed", "won": 200},
     ]},
    {"id": "sigeumchi_namul", "name": "시금치나물", "img": "sigeumchi_namul.png", "emoji": "🌿", "eatout": 2500,
     "ingredients": [
         {"name": "시금치", "kind": "crop", "crop": "시금치", "amount_kg": 0.12},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.01},
         {"name": "참기름·양념", "kind": "fixed", "won": 200},
     ]},
    {"id": "yangpa_jangajji", "name": "양파장아찌", "img": "yangpa_jangajji.png", "emoji": "🧅", "eatout": 2000,
     "ingredients": [
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.12},
         {"name": "간장·식초", "kind": "fixed", "won": 250},
     ]},
    {"id": "jeyuk_bokkeum", "name": "제육볶음", "img": "jeyuk_bokkeum.png", "emoji": "🍖", "eatout": 10000,
     "ingredients": [
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.12},
         {"name": "돼지고기", "kind": "fixed", "won": 1500},
         {"name": "고추장양념", "kind": "fixed", "won": 300},
     ]},
]


def all_dishes():
    return DISHES


def by_id(did):
    for d in DISHES:
        if d["id"] == did:
            return d
    return None
