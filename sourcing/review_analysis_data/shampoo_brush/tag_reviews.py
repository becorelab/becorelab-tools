# -*- coding: utf-8 -*-
import json

def has(t, *subs):
    return any(s in t for s in subs)

def tag_usage(t):
    # priority top->down
    # 탈모모발케어
    if has(t, '탈모', '모발', '발모', '두피케어', '두피 케어', '탈락모', '머리숱', '머리 나', '머리가 나', '두피건강', '두피 건강', '헤어로스', '모근', '빠지는', '머리빠', '머리 빠', '숱이 없', '숱없'):
        return '탈모모발케어'
    # 각질비듬제거
    if has(t, '각질', '비듬', '스케일링', '딥클렌징', '딥 클렌징', '노폐물', '피지', '떡짐', '떡지', '기름', '지성두피', '지성 두피', '세정', '깨끗하게 감', '개운하게 씻', '두피 청결', '클렌징'):
        return '각질비듬제거'
    # 두피마사지시원함
    if has(t, '마사지', '시원', '개운', '두피자극', '두피 자극', '지압', '혈액순환', '두피운동', '스트레스', '두피 지압'):
        return '두피마사지시원함'
    # 아기어린이
    if has(t, '아기', '아이', '애기', '아들', '딸', '어린이', '유아', '초등', '자녀', '아이들', '아이가', '아이한테', '아이용', '조카', '손주'):
        return '아기어린이'
    # 반려동물
    if has(t, '강아지', '반려', '고양이', '댕댕', '멍멍', '애견', '반려견', '반려묘', '펫'):
        return '반려동물'
    # 선물
    if has(t, '선물', '증정', '드리려', '드릴려', '선물용', '선물로'):
        return '선물'
    return None

NEG_COOL = ['안시원', '안 시원', '시원하지 않', '시원하지않', '시원찬', '시원치 않', '시원하진 않', '시원하지도', '별로 시원', '하나도 안 시원', '하나도안시원']
def tag_needs(t):
    n = []
    cool_negated = any(s in t for s in NEG_COOL)
    soft_negated = has(t, '딱딱해', '너무 딱딱', '빳빳', '단단하지', '딱딱하고')
    # 적당한강도
    if has(t, '적당한 강도', '적당히 딱딱', '적당한 세기', '강도가 적당', '세기가 적당', '너무 세지도', '아프지도 않고', '아프지 않고', '아프지않고', '아프지도않', '자극적이지 않', '아프지 않아', '아프지않아', '두피 자극 없', '자극없이', '자극 없이', '안아프', '안 아프'):
        n.append('적당한강도')
    # 부드러움
    if not soft_negated and has(t, '부드럽', '부들부들', '말랑', '폭신', '소프트', '실리콘이 부드', '유연', '보들'):
        n.append('부드러움')
    # 그립손잡이
    if has(t, '그립', '손잡이', '손에 잡', '손에잡', '잡기 편', '잡기편', '쥐기 편', '파지', '인체공학', '손에 딱', '손에딱', '핸들'):
        n.append('그립손잡이')
    # 위생건조
    if has(t, '위생', '건조가 잘', '잘 마르', '잘마르', '빨리 마르', '빨리마르', '물기', '세척', '세척이 편', '씻기 편', '헹구기', '걸이', '걸어', '고리', '걸수', '걸 수', '건조 잘', '건조가잘'):
        n.append('위생건조')
    # 내구성
    if has(t, '내구', '튼튼', '견고', '단단하게 만', '잘 부러지지', '오래 쓸', '오래쓸', '튼실', '견고한', '안 부러', '내구성'):
        n.append('내구성')
    # 휴대성
    if has(t, '휴대', '여행', '가지고 다니', '들고 다니', '컴팩트', '작아서 좋', '작고 가벼', '간편하게 휴대'):
        n.append('휴대성')
    # 디자인
    if has(t, '디자인', '예쁘', '이쁘', '색상', '컬러', '색깔', '깔끔', '색조합', '컬러 조합', '색 조합', '고급스', '심플'):
        n.append('디자인')
    # 시원함
    if not cool_negated and has(t, '시원', '개운', '두피가 뻥', '뻥 뚫', '뚫리는', '상쾌', '두르가즘', '두피 자극이 좋', '지압'):
        n.append('시원함')
    return list(dict.fromkeys(n))

def tag_pain(t):
    p = []
    # 너무딱딱아픔
    if has(t, '너무 딱딱', '너무딱딱', '딱딱해서', '딱딱하고 아', '두피가 아', '두피 아', '아파', '아픔', '아팠', '아프네', '뜯어질', '자극이 심', '자극 심', '따가', '너무 세', '아프고', '따갑'):
        # only pain-side deux: exclude "안아프" already positive; but pain reviews mention pain
        if not has(t, '아프지', '안아프', '안 아프'):
            p.append('너무딱딱아픔')
    # 너무약함효과없음
    if has(t, '안시원', '안 시원', '시원하지 않', '시원하지않', '시원찬', '시원치 않', '하나도 안', '효과 없', '효과없', '효과가 없', '흐물흐물', '힘이 없', '힘이없', '물렁', '약해서', '강성이 약', '탄력이 없', '별로 시원', '시원하진 않', '시원하지도', '마사지가 안', '마사지 안', '느낌이 없', '아무 느낌', '아무느낌', '손으로 하는게', '손으로가', '손이 더', '손보다', '너무 부드러워', '넘 부드러워', '넘 부드럽', '너무 약'):
        p.append('너무약함효과없음')
    # 살끼임머리엉킴
    if has(t, '머리카락이 끼', '머리카락 끼', '머리 끼', '살이 끼', '살 끼', '살끼', '엉킴', '엉켜', '머리 엉', '당겨', '당기', '끼이', '걸려서', '머리카락이 걸', '뜯겨', '머리카락 걸', '머리카락에 걸', '팅겨'):
        p.append('살끼임머리엉킴')
    # 잘안마름곰팡이
    if has(t, '안 마르', '안마르', '잘 안마', '곰팡이', '물때', '건조가 안', '마르지 않', '냄새', '고무냄새', '역해', '눅눅'):
        p.append('잘안마름곰팡이')
    # 빠짐내구불량
    if has(t, '부러', '떨어져 나', '떨어져나', '잘라져', '빠져 나', '돌기가 빠', '솔이 빠', '내구', '금방 망가', '고장', '갈라', '찢어진 제품', '하나가 잘'):
        p.append('빠짐내구불량')
    # 크기부적합
    if has(t, '너무 작', '너무작', '사이즈가 작', '작아서', '크기가 작', '미니미', '생각보다 작', '너무 커', '크기가 애매', '솔이 짧', '빗길이가 짧', '길이가 짧', '짧아서'):
        p.append('크기부적합')
    # 배송파손
    if has(t, '찌그러', '파손', '박스가', '상자가', '중고', '누가 쓰던', '먼지', '스크래치', '지문', '뜯겨서', '포장이', '깨져', '쪼그라', '가루가', '머리카락 나', '머리카락이 붙', '머리카락 붙', '오배송', '빈 박스', '빈박스', '반품한거', '먼지가', '먼지도', '먼지 묻', '먼지묻') and not has(t, '브랜드먼지'):
        p.append('배송파손')
    # 기대이하 (fallback / disappointment)
    if has(t, '기대 이하', '기대이하', '실망', '아쉽', '아쉬움', '별로', '그냥 그래', '쏘쏘', '돈 아깝', '돈아깝', '돈만', '후회', '추천 안', '추천안', '비추', '가성비', '기대했', '생각보다', '왜 이렇게 리뷰', '왜케 리뷰', '리뷰 알바', '리뷰가 많은지'):
        p.append('기대이하')
    return list(dict.fromkeys(p))

def tag_repeat(t):
    return has(t, '재구매', '재 구매', '또 샀', '또 구매', '또 주문', '다시 샀', '다시 주문', '다시 구매', '추가 주문', '추가주문', '두 번째 구매', '두번째 구매', '재주문', '재 주문', '또 시켰', '또 시킴', '벌써 두', '또 삽', '계속 살', '계속 사', '또 살', '리필', '몇 번째', '몇번째', '여러 번 샀', '재구입', '또 사려')

allr = []
for i in range(4):
    allr += json.load(open(f'/Users/macmini_ky/ClaudeAITeam/sourcing/review_analysis_data/shampoo_brush/chunk_{i}.json'))

out = []
for r in allr:
    t = r.get('t', '') or ''
    rating = r['r']
    usage = tag_usage(t)
    needs = tag_needs(t) if rating >= 4 else tag_needs(t)  # needs allowed both, but keep positive-lean
    pain = tag_pain(t) if rating <= 3 else []
    # for r>=4 needs stays; but drop '시원함' if review says not cool? high rating trust text
    rep = tag_repeat(t)
    rec = {"id": r['id'], "r": rating, "usage": usage, "needs": needs, "pain": pain, "repeat": rep}
    out.append(rec)

json.dump(out, open('/Users/macmini_ky/ClaudeAITeam/sourcing/review_analysis_data/shampoo_brush/tagged_0.json', 'w'), ensure_ascii=False, indent=0)

from collections import Counter
uc = Counter(r['usage'] or '불명' for r in out)
nc = Counter(n for r in out for n in r['needs'])
pc = Counter(p for r in out for p in r['pain'])
print('count', len(out))
print('usage', uc.most_common())
print('needs', nc.most_common())
print('pain', pc.most_common())
print('repeat', sum(1 for r in out if r['repeat']))
