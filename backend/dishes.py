# -*- coding: utf-8 -*-
"""밥상 차리기 — 음식 카탈로그(레시피·정가). 순수 데이터, 모델 의존 없음.

기후 재료(kind="crop")는 6종 작물 중 하나로 분량(amount_kg)을 가지며
가격은 ClimateModel로 날씨에 따라 계산된다.
고정 재료(kind="fixed")는 정가(won)로 날씨와 무관하다.
분량·정가는 교육용 1인분 근사값이며 이 파일 한 곳에서 조정한다.
"""

CROPS = {"배추", "무", "사과", "쌀", "시금치", "양파"}

DISHES = [
    {"id": "rice", "name": "공기밥", "img": "rice.png", "emoji": "🍚",
     "ingredients": [
         {"name": "쌀", "kind": "crop", "crop": "쌀", "amount_kg": 0.10},
     ]},
    {"id": "kimchi_jjigae", "name": "김치찌개", "img": "kimchi_jjigae.png", "emoji": "🥘",
     "ingredients": [
         {"name": "배추", "kind": "crop", "crop": "배추", "amount_kg": 0.12},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.05},
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.03},
         {"name": "돼지고기", "kind": "fixed", "won": 2500},
         {"name": "두부", "kind": "fixed", "won": 900},
         {"name": "양념", "kind": "fixed", "won": 400},
     ]},
    {"id": "doenjang_jjigae", "name": "된장찌개", "img": "doenjang_jjigae.png", "emoji": "🍲",
     "ingredients": [
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.05},
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.05},
         {"name": "시금치", "kind": "crop", "crop": "시금치", "amount_kg": 0.02},
         {"name": "두부", "kind": "fixed", "won": 900},
         {"name": "된장양념", "kind": "fixed", "won": 500},
     ]},
    {"id": "baechu_kimchi", "name": "배추김치", "img": "baechu_kimchi.png", "emoji": "🥬",
     "ingredients": [
         {"name": "배추", "kind": "crop", "crop": "배추", "amount_kg": 0.18},
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.04},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.03},
         {"name": "사과", "kind": "crop", "crop": "사과", "amount_kg": 0.02},
         {"name": "고춧가루·젓갈", "kind": "fixed", "won": 800},
     ]},
    {"id": "mu_saengchae", "name": "무생채", "img": "mu_saengchae.png", "emoji": "🥗",
     "ingredients": [
         {"name": "무", "kind": "crop", "crop": "무", "amount_kg": 0.12},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.02},
         {"name": "사과", "kind": "crop", "crop": "사과", "amount_kg": 0.02},
         {"name": "양념", "kind": "fixed", "won": 300},
     ]},
    {"id": "sigeumchi_namul", "name": "시금치나물", "img": "sigeumchi_namul.png", "emoji": "🌿",
     "ingredients": [
         {"name": "시금치", "kind": "crop", "crop": "시금치", "amount_kg": 0.08},
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.01},
         {"name": "참기름·양념", "kind": "fixed", "won": 300},
     ]},
    {"id": "yangpa_jangajji", "name": "양파장아찌", "img": "yangpa_jangajji.png", "emoji": "🧅",
     "ingredients": [
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.10},
         {"name": "간장·식초", "kind": "fixed", "won": 400},
     ]},
    {"id": "jeyuk_bokkeum", "name": "제육볶음", "img": "jeyuk_bokkeum.png", "emoji": "🍖",
     "ingredients": [
         {"name": "양파", "kind": "crop", "crop": "양파", "amount_kg": 0.06},
         {"name": "돼지고기", "kind": "fixed", "won": 3000},
         {"name": "고추장양념", "kind": "fixed", "won": 600},
     ]},
]


def all_dishes():
    return DISHES


def by_id(did):
    for d in DISHES:
        if d["id"] == did:
            return d
    return None
