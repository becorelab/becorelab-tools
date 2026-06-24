import json, re

def tag_review(item):
    raw = item['t']
    t = raw.lower()
    r = item['r']

    usage = set()
    needs = set()
    pain = set()

    # ─── usage ───

    # 흰옷표백
    white_kw = ['흰옷','흰 옷','흰티','흰색','흰 색','흰빨','흰빨래','흰 빨','흰셔츠','흰 셔츠','흰남방','흰 남방',
                '흰블라우스','흰 블라우스','흰양말','흰 양말','흰반팔','흰 반팔','흰이불','흰 이불','흰 바지','흰바지',
                '하얗게','하얘','새하얗','새하얘','하얀 옷','하얀옷','누렇','누래','누런','황변','교복',
                '흰 소재','흰소재','셔츠','와이셔츠','남방','반팔티','뽀글이']
    if any(k in t for k in white_kw):
        usage.add('흰옷표백')
    if re.search(r'흰\s*\w*(티|옷|셔츠|남방|반팔|블라우스|와이셔츠|양말|빨|빨래|세탁|이불|바지|원피스)', t):
        usage.add('흰옷표백')
    if '표백' in t and any(k in t for k in ['흰','하얗','하야','새하','하얀']):
        usage.add('흰옷표백')

    # 찌든때
    if any(k in t for k in ['찌든','찌들','찌드','묵은때','묵은 때','묵은빨','묵은 빨','때가','때를','누렁물','누렇','때빠','때 빠']):
        usage.add('찌든때')

    # 얼룩제거
    if any(k in t for k in ['얼룩','자국','커피','음식물','기름','잉크','음식','오염','묻','오점',
                              '잘지워','잘 지워','지워지','지워졌','빠졌','쏙 빠','쏙빠','지운']):
        usage.add('얼룩제거')

    # 살균소독
    if any(k in t for k in ['살균','소독','세균','항균','바이러스']):
        usage.add('살균소독')

    # 걸레행주
    if any(k in t for k in ['걸레','행주','주방천','키친','수건빨','수건 빨']):
        usage.add('걸레행주')

    # 아기옷
    if any(k in t for k in ['아기','아가','베이비','유아','신생아','돌','어린이','어린이집','어린이 집','아이 옷','아이옷']):
        usage.add('아기옷')

    # 위생관리
    if any(k in t for k in ['위생','청결','청소','깔끔','깨끗','청결','소독','살균']):
        usage.add('위생관리')

    # 냄새제거
    if any(k in t for k in ['냄새','악취','퀴퀴','퀴큰','땀냄새','땀 냄새','탈취']):
        usage.add('냄새제거')

    # ─ 아직 usage 없으면 맥락에서 추론 ─
    if not usage:
        # 세정/표백 일반: 세탁, 표백, 세척, 빨래 관련 리뷰는 흰옷표백으로 대분류
        if any(k in t for k in ['표백','세탁','빨래','세제','세정','세척','담가','담궈','불리','담구']):
            usage.add('흰옷표백')
        elif any(k in t for k in ['편리','편해','편하','간편','캡슐','쉽','쉬워','한알','소분','투입','넣으면']):
            # 편의성 위주 리뷰 → 일반 세탁 대분류 없이 기타
            usage.add('기타')
        elif any(k in t for k in ['효과','광고','구매','재구매','지워','빠지','세정','때','사용']):
            usage.add('흰옷표백')  # 맥락상 캡슐표백제 기본 사용 = 흰옷표백
        else:
            usage.add('기타')

    # 기타 정리
    if len(usage) > 1:
        usage.discard('기타')

    # ─── needs ───
    if any(k in t for k in ['표백','하얗','새하얗','하얘','누렇','황변','얼룩','찌든','찌드','오염','세척','세정','때','누렁','지워','빠졌','빠지']):
        needs.add('표백력')
    if '효과' in t:
        needs.add('표백력')

    if any(k in t for k in ['탈취','냄새','악취','땀냄새','퀴퀴']):
        needs.add('탈취력')

    if any(k in t for k in ['안전','무해','무독','자극없','자극 없','과탄산','국내산','성분','독성','환경','무자극']):
        needs.add('안전성')
    if any(k in t for k in ['아기','아가','유아','신생아']):
        needs.add('안전성')

    if '향' in t:
        needs.add('향')

    if any(k in t for k in ['가성비','가격','비싸','저렴','싸','경제','돈아','재구매','또 살','또살','다시 살','계속 살','또 구매','다시 구매']):
        needs.add('가성비')
    if '재구매' in t or '두번째' in t or '세번째' in t or '쭉 써' in t or '쭉쓰' in t:
        needs.add('가성비')

    if any(k in t for k in ['편리','편해','편하','간편','캡슐','계량','간단','쉬워','쉽게','쉬운','던지','넣기만','한알','한 알','한개','한 개',
                             '소분','투입','넣으면','넣으니','넣고 세','적당량','양조절','가루날림','가루 날림']):
        needs.add('사용편의')

    if not needs:
        needs.add('사용편의')  # fallback

    # ─── pain (1~3★) ───
    if r <= 3:
        if any(k in t for k in ['효과 없','효과없','차이 없','차이없','차이 안','별로','그냥 그래','기대 이하','광고와 다','광고랑 다',
                                  '광고처럼 안','생각보다','드라마틱','안됩니','안되','모르겠','효과 못','못봤','별차이',
                                  '잘 안','잘안','안 빠','안빠','안지','안 지워','안지워']):
            pain.add('표백안됨')
        if re.search(r'(하얗게|표백이?|세척이?|때가?)\s*(안|못|잘 안)', t):
            pain.add('표백안됨')

        if any(k in t for k in ['옷이 상','옷상','옷감 상','탈색','색빠','색 빠','옷이 망','옷 망','망했','망가']):
            pain.add('옷상함')

        if any(k in t for k in ['향이 별','향이 없','향 없','냄새가 심','냄새가 강','역한','역겨','향이 너무 강','향이 독','향이 싫']):
            pain.add('향불만')

        if any(k in t for k in ['녹지 않','녹지않','안 녹','잔여','잔여물','덜 녹','캡슐이 남','캡슐 남']):
            pain.add('캡슐안녹음')

        if any(k in t for k in ['비싸','가격이 좀','가격 대비','돈이 아깝','아깝','가격 부담','부담']):
            pain.add('가격불만')

        if any(k in t for k in ['누액','터졌','터짐','파손','찢','뚫','가루 떨어','가루가 터','포장이 찢','포장 터','가루 쏟','가루쏟']):
            pain.add('용기누액')

        if any(k in t for k in ['자극','피부','가렵','가려움','따갑','따끔','알레르기','반응']):
            pain.add('자극')

        if not pain:
            pain.add('기타')
        if len(pain) > 1:
            pain.discard('기타')

    return {
        'id': item['id'],
        'usage': sorted(usage),
        'needs': sorted(needs),
        'pain': sorted(pain) if r <= 3 else []
    }

# 실행
with open('chunk_3.json', encoding='utf-8') as f:
    data = json.load(f)

tagged = [tag_review(item) for item in data]

with open('tagged_3.json', 'w', encoding='utf-8') as f:
    json.dump(tagged, f, ensure_ascii=False, indent=2)

# 통계
usage_cnt, needs_cnt, pain_cnt = {}, {}, {}
for item in tagged:
    for u in item['usage']:
        usage_cnt[u] = usage_cnt.get(u, 0) + 1
    for n in item['needs']:
        needs_cnt[n] = needs_cnt.get(n, 0) + 1
    for p in item['pain']:
        pain_cnt[p] = pain_cnt.get(p, 0) + 1

low_r = [x for x in data if x['r'] <= 3]
print(f'total_read: {len(tagged)}')
print(f'1~3★ 대상: {len(low_r)}건 (pain 태깅 대상)')
print()
print('=== usage ===')
for k, v in sorted(usage_cnt.items(), key=lambda x: -x[1]):
    pct = round(v/len(tagged)*100, 1)
    print(f'  {k}: {v} ({pct}%)')
print()
print('=== needs ===')
for k, v in sorted(needs_cnt.items(), key=lambda x: -x[1]):
    pct = round(v/len(tagged)*100, 1)
    print(f'  {k}: {v} ({pct}%)')
print()
print(f'=== pain (1~3★ {len(low_r)}건) ===')
for k, v in sorted(pain_cnt.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')

# 샘플 검증
print()
print('=== 기타 남은 것 상위 10개 ===')
gita_items = [(item, tagged[i]) for i, item in enumerate(data) if '기타' in tagged[i]['usage']]
for raw, tag in gita_items[:10]:
    r_val = raw['r']
    t_val = raw['t'][:80]
    print(f'R:{r_val} | {t_val}')
