# -*- coding: utf-8 -*-
import json
from collections import Counter

FILES = ['chunk_4','chunk_5','chunk_6','chunk_7']
BASE = '/Users/macmini_ky/ClaudeAITeam/sourcing/review_analysis_data/shampoo_brush/'

def norm(s):
    return (s or '').replace(' ', '')

def tag_usage(t, p):
    n = norm(t); pn = norm(p)
    if any(k in n for k in ['탈모','모발','발모','머리숱','숱이','숱없','머리빠','머리가빠','두피영양','헤어로스','모근','두피건강','머리가나','발모','빠지는머리']):
        return '탈모모발케어'
    if any(k in n for k in ['각질','비듬','스케일링','딥클렌징','노폐물','피지','떡짐','떡지','기름','지루성','두피때','딱지','모공','노페물','세정','두피청결','두피가더']):
        return '각질비듬제거'
    if any(k in n for k in ['아기','애기','아이','아들','딸','자녀','유아','어린이','초등','조카','손주','아이들','아이가','아이한테','아이도','아이용']):
        return '아기어린이'
    if any(k in n for k in ['강아지','반려견','반려동물','반려묘','고양이','댕댕','멍멍','애견','펫','우리개']):
        return '반려동물'
    if any(k in n for k in ['선물','선물용','선물로','증정','드리려','드릴려','효도','부모님드','엄마드','챙겨드']):
        return '선물'
    if any(k in n for k in ['마사지','시원','개운','두피자극','지압','혈액순환','두피운동','두피케어','머리감을때','샴푸할때','두피에좋','상쾌']):
        return '두피마사지시원함'
    return '불명'

NEG_COOL = ['안시원','시원하지않','시원치않','시원하진않','시원하지도','별로시원','하나도안시원','시원함은없','시원함이없','드라마틱한시원함은없']

def tag_needs(t):
    n = norm(t); needs = []
    def add(x):
        if x not in needs: needs.append(x)
    if any(k in n for k in ['적당한강도','강도가적당','세기적당','적당히','아프지않','아프지가않','안아프','자극없이','자극이없','두피에자극없','부담없이','아프지도않','세지도약하지','적당한자극','적당한압','아플정도아니']):
        add('적당한강도')
    if any(k in n for k in ['부드러','실리콘이라','실리콘재질','말랑','유연','촉감좋','피부에순','순하','부들','두피에순']):
        if not any(b in n for b in ['부드러울줄','부드럽지않','부드럽지가않','안부드럽','부드러웠으면']):
            add('부드러움')
    if any(k in n for k in ['그립','손잡이','손에잡','손에딱','쥐기편','파지','손에쏙','잡기편','쥐기좋','손에착','손에맞']):
        if not any(b in n for b in ['그립감이별로','쥐기불편','잡기불편','한손으로쥐기불']):
            add('그립손잡이')
    if any(k in n for k in ['위생','건조가잘','잘마르','금방마','물빠짐이좋','물이잘빠','걸이','걸어놓','통풍','청결하게','씻기편','세척편','건조잘']):
        if not any(b in n for b in ['잘안마','안마르','물이고','물빠짐이안','물이안빠','물이차']):
            add('위생건조')
    if any(k in n for k in ['튼튼','내구성','오래쓸','오래써','견고','단단하게만','잘만들','마감좋','품질좋','튼실']):
        add('내구성')
    if any(k in n for k in ['휴대','여행','컴팩트','간편하게들','들고다','휴대성']):
        add('휴대성')
    if any(k in n for k in ['디자인','색상','이쁘','예뻐','예쁘','색깔','색이','귀엽','고급스','모양이좋','컬러','색감']):
        if not any(b in n for b in ['색상이별로','디자인만','디자인은']):
            add('디자인')
    if ('시원' in n or '개운' in n or '뻥뚫' in n or '상쾌' in n or '두피가풀' in n):
        if not any(b in n for b in NEG_COOL):
            add('시원함')
    return needs

def tag_pain(t):
    n = norm(t); pain = []
    def add(x):
        if x not in pain: pain.append(x)
    if any(k in n for k in ['딱딱','아파','아프','따가','찔리','이쑤시개','송곳','뾰족해서아','상처','통증','거스','벗겨질','까끌','너무세','아플것','아플까']):
        if not any(b in n for b in ['아프지않','아프지가않','안아프','아플정도아니']):
            add('너무딱딱아픔')
    if any(k in n for k in ['말랑말랑해서','흐물','힘이없','힘없','너무약','약해서','효과를모르','효과없','효과가없','효과가별','두피까지안','두피에안닿','씻기는느낌이없','제대로씻','느낌이조금도없','기능이나효과','두피까지안가','씻어주는느낌이조금']+NEG_COOL):
        add('너무약함효과없음')
    if any(k in n for k in ['엉키','엉킴','머리카락이껴','머리가껴','머리카락줘뜯','머리카락이빠지게','살끼','살이껴','머리카락더빠','줘뜯','뜯어지','머리카락이엉']):
        add('살끼임머리엉킴')
    if any(k in n for k in ['물이고','물차','물이차','안마르','잘안마','곰팡이','물빠짐이안','물이안빠','물이잘안','안에물']):
        add('잘안마름곰팡이')
    if any(k in n for k in ['찢어','부러','떨어져나','돌기가빠','부품','고장','금방망가','헐거','헐렁','송곳모양찢']):
        add('빠짐내구불량')
    if any(k in n for k in ['너무작','작아서','크기가작','사이즈가작','생각보다작','작고','너무커','크기부적','엄청작','한손으로쥐기불']):
        if ('작' in n) or ('커' in n) or ('크기' in n):
            add('크기부적합')
    if any(k in n for k in ['배송안','배송완료뜨는데','박스훼손','박스가훼손','파손','찌그','포장이엉망','배송이늦','안왔','박스훼','검품']):
        add('배송파손')
    if any(k in n for k in ['별로','실망','아쉬','비추','돈아까','돈만날','후회','기대이하','기대에못','가격대비별','쓰레기통','다시는','안쓰게','가격대비비추','돈만날림','돈날']):
        add('기대이하')
    if not pain:
        add('기대이하')
    return pain

def tag_repeat(t):
    n = norm(t)
    return any(k in n for k in ['재구매','또구매','또샀','재주문','다시구매','또사','두번째구매','재구입','또시켰','계속사','추가구매','또주문','벌써두번','세번째','두개째'])

out = []
for f in FILES:
    d = json.load(open(BASE+f+'.json'))
    for x in d:
        r = x.get('r', 5); t = x.get('t','') or ''; p = x.get('p','') or ''
        out.append({
            'id': x.get('id'), 'r': r,
            'usage': tag_usage(t, p),
            'needs': tag_needs(t),
            'pain': tag_pain(t) if r <= 3 else [],
            'repeat': tag_repeat(t),
        })

with open(BASE+'tagged_1.json','w') as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
    fh.flush()

uc = Counter(o['usage'] for o in out)
nc = Counter(n for o in out for n in o['needs'])
pc = Counter(p for o in out for p in o['pain'])
print('COUNT', len(out))
print('USAGE', dict(uc.most_common()))
print('NEEDS_TOP5', nc.most_common(5))
print('PAIN_TOP5', pc.most_common(5))
print('REPEAT', sum(1 for o in out if o['repeat']))
