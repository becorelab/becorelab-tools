import json, re

def tag_review(item):
    t = item['t'].lower()
    r = item['r']
    
    usage = set()
    needs = set()
    pain = set()

    # ── usage 태그 ──
    # 흰옷표백
    if any(k in t for k in ['흰옷','흰 옷','흰티','흰색 옷','흰 티','흰색티','흰셔츠','흰 셔츠','흰블라우스','흰 블라우스','흰와이셔츠','흰 와이셔츠','흰반팔','흰 반팔','흰남방','흰양말','흰 양말','흰빨']):
        usage.add('흰옷표백')
    if re.search(r'흰(색)?\s*\w*(티|옷|셔츠|남방|반팔|블라우스|와이셔츠|양말|빨|빨래|세탁)', t):
        usage.add('흰옷표백')
    if '표백' in t and any(k in t for k in ['흰','하얗','하야','새하']):
        usage.add('흰옷표백')
    if '하얗게' in t or '하얘' in t or '새하얗' in t or '새하얘' in t:
        usage.add('흰옷표백')
    if '누렇' in t or '누래' in t or '노래진' in t or '황변' in t:
        usage.add('흰옷표백')

    # 찌든때
    if any(k in t for k in ['찌든','찌들','찌드는','떼,']):
        usage.add('찌든때')
    if '찌든 때' in t or '찌든때' in t:
        usage.add('찌든때')
    if '묵은 때' in t or '묵은때' in t or '묵은빨' in t:
        usage.add('찌든때')

    # 얼룩제거
    if any(k in t for k in ['얼룩','자국','커피','음식물','오염','때']):
        if any(k in t for k in ['얼룩','자국','커피','음식물']):
            usage.add('얼룩제거')
        if '때' in t and not ('찌든때' in usage):
            usage.add('얼룩제거')
    if '오염' in t:
        usage.add('얼룩제거')

    # 살균소독
    if any(k in t for k in ['살균','소독','세균','항균','바이러스','위생']):
        usage.add('살균소독')

    # 걸레행주
    if any(k in t for k in ['걸레','행주','주방천','조리대','키친타올','키친']):
        usage.add('걸레행주')

    # 아기옷
    if any(k in t for k in ['아기','아가','베이비','유아','신생아','돌','아기옷','아이옷','어린이집','어린이 집']):
        usage.add('아기옷')
    if '어린이' in t and '집' in t:
        usage.add('아기옷')

    # 위생관리
    if any(k in t for k in ['위생','청결','깔끔','청소','환경']):
        usage.add('위생관리')
    if '살균' in t or '소독' in t:
        usage.add('위생관리')

    # 냄새제거
    if any(k in t for k in ['냄새','악취','퀴퀴','퀴큰','땀냄새','땀 냄새','냄새 제거','냄새제거','탈취','냄새없','냄새가 없','냄새없어']):
        usage.add('냄새제거')
    if '냄새' in t:
        usage.add('냄새제거')

    # 기타 — 위 어디에도 안 걸리면
    if not usage:
        usage.add('기타')
    # 지나치게 광범위한 "기타" 방지: 명확한 태그 있으면 기타 제거
    if len(usage) > 1 and '기타' in usage:
        usage.discard('기타')

    # ── needs 태그 ──
    # 표백력
    if any(k in t for k in ['표백','하얗','새하얗','하얘','누렇','황변','찌든','찌드','얼룩']):
        needs.add('표백력')
    if '효과' in t and any(k in t for k in ['표백','하얗','찌든','얼룩']):
        needs.add('표백력')

    # 탈취력
    if any(k in t for k in ['탈취','냄새','악취','땀냄새','퀴퀴']):
        needs.add('탈취력')

    # 안전성
    if any(k in t for k in ['안전','무해','무독','자극없','자극 없','과탄산','국내산','성분','아기','아가','유아','신생아','독성','환경']):
        needs.add('안전성')
    if '아기' in t or '아이' in t:
        needs.add('안전성')

    # 향
    if any(k in t for k in ['향','향기','향이','향도','향기롭','무향','냄새']):
        needs.add('향')

    # 가성비
    if any(k in t for k in ['가성비','가격','비싸','저렴','싸','경제','돈','재구매','또 살','또살','다시 살','계속 살']):
        needs.add('가성비')
    if '재구매' in t or '또 구매' in t or '다시 구매' in t or '반복 구매' in t:
        needs.add('가성비')

    # 사용편의
    if any(k in t for k in ['편리','편해','편하','간편','캡슐','계량','간단','쉬워','쉽게','쉬운','던지','넣기만','한알','한 알','한개','한 개']):
        needs.add('사용편의')
    if '캡슐' in t:
        needs.add('사용편의')

    if not needs:
        needs.add('사용편의')  # 텍스트 매우 짧은 경우 fallback

    # ── pain 태그 (1~3★만) ──
    if r <= 3:
        # 표백안됨
        if any(k in t for k in ['표백 안','효과 없','효과없','안됩니다','안되','별로','그냥 그래','그저그래','차이 없','기대 이하','광고와 다','광고랑 다','광고처럼 안','생각보다']):
            pain.add('표백안됨')
        if '하얗게 안' in t or '표백이 안' in t or '표백이 잘 안' in t:
            pain.add('표백안됨')

        # 옷상함
        if any(k in t for k in ['옷이 상','옷상','옷감 상','옷감상','원단','탈색','색빠','색 빠','옷이 망','옷 망','탈색됩']):
            pain.add('옷상함')

        # 향불만
        if any(k in t for k in ['향이 별','향이 없','향 없','무향','향 불만','향이 너무','냄새가 심','냄새가 강','역한','역겨','향이 너무 강','향이 독','향 독특']):
            pain.add('향불만')

        # 캡슐안녹음
        if any(k in t for k in ['녹지 않','녹지않','안 녹','잔여','남아있','덜 녹','캡슐이 남']):
            pain.add('캡슐안녹음')

        # 가격불만
        if any(k in t for k in ['비싸','가격이 좀','가격 대비','돈이 아깝','가성비 나쁨','가성비 별','아깝']):
            pain.add('가격불만')

        # 용기누액
        if any(k in t for k in ['누액','새','샜','터졌','터짐','포장','박스 상','파손','배송']):
            pain.add('용기누액')

        # 자극
        if any(k in t for k in ['자극','피부','가렵','가려움','따갑','따끔','알레르기','반응','손이 따','손따','손 따']):
            pain.add('자극')

        # 기타
        if not pain:
            pain.add('기타')
        if len(pain) > 1 and '기타' in pain:
            pain.discard('기타')

    return {
        'id': item['id'],
        'usage': sorted(usage),
        'needs': sorted(needs),
        'pain': sorted(pain) if r <= 3 else []
    }

# 로드
with open('chunk_3.json', encoding='utf-8') as f:
    data = json.load(f)

tagged = [tag_review(item) for item in data]

with open('tagged_3.json', 'w', encoding='utf-8') as f:
    json.dump(tagged, f, ensure_ascii=False, indent=2)

# 통계
usage_cnt = {}
needs_cnt = {}
pain_cnt = {}

for item in tagged:
    for u in item['usage']:
        usage_cnt[u] = usage_cnt.get(u, 0) + 1
    for n in item['needs']:
        needs_cnt[n] = needs_cnt.get(n, 0) + 1
    for p in item['pain']:
        pain_cnt[p] = pain_cnt.get(p, 0) + 1

print(f'total_read: {len(tagged)}')
print()
print('=== usage ===')
for k, v in sorted(usage_cnt.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
print()
print('=== needs ===')
for k, v in sorted(needs_cnt.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
print()
print('=== pain (1~3★ only, n=4) ===')
for k, v in sorted(pain_cnt.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
