#!/usr/bin/env python3
"""리뷰 전수 분석 파이프라인 — 추출(chunk분할) + 집계(유형별/세분).

전수 정독 태깅은 하치(메인)가 Agent로 chunk별 서브에이전트를 띄워 수행.
이 스크립트는 그 전후처리(추출·분할·집계)를 담당. 방법론: REVIEW_ANALYSIS.md

사용 예:
  # 1) 추출: 깔창 3스캔 → 텍스트 15자+ → 7개 chunk
  python review_pipeline.py extract --scans 6011,6019,6020 --minlen 15 --chunks 7 --out /tmp/ins

  # 2) (하치가 chunk_0~6.json을 서브에이전트로 전수 태깅 → tagged_N.json 저장)

  # 3) 집계: tagged 결과를 축별·상품유형별 카운트
  python review_pipeline.py aggregate --tagged "/tmp/ins/tagged_*.json" --axis usage --by-type
"""
import json, sys, os, math, glob, argparse
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# ── 상품 유형 분류 (제품군마다 룰 추가) ──────────────────────────
def product_type(name, domain='insole'):
    n = name or ''
    if domain == 'insole':
        if '키높이' in n: return '키높이형'
        if any(k in n for k in ['족저근', '아치', '평발', '오다리', '아킬레스', '발교정']):
            return '족저근막/아치형'
        if any(k in n for k in ['메모리', '구름', '쿠션', '라텍스', '소가죽', '푹신', '폭신',
                                '인체공학', '루파', '젤리', '밀릭스']):
            return '쿠션/메모리폼형'
        return '기타'
    if domain == 'keyring':
        if any(k in n for k in ['LED', 'led', '발광', '야광', '디스코', '레인보우', '무지개', '불빛', '빛나']):
            return 'LED발광형'
        if any(k in n for k in ['구', '버튼', '세트', '클리커', '다구']):
            return '다구성세트형'
        if any(k in n for k in ['식빵', '오리', '거북이', '과일', '고양이', '개구리', '곰', '동물',
                                '캐릭터', '계란', '초콜릿', '오징어', '강아지']):
            return '캐릭터모양형'
        return '기본딸깍형'
    return '미분류'  # 다른 제품군은 여기에 룰 추가


def extract(category, scans, minlen, chunks, out):
    from review_query import resolve
    revs, src = resolve(category, [int(x) for x in scans.split(',')] if scans else [])
    data = []
    for i, r in enumerate(revs):
        c = (r.get('content') or '').strip()
        if len(c) >= minlen:
            data.append({'id': i, 'r': r.get('rating'), 't': c[:250],
                         'p': r.get('_product') or r.get('productName') or ''})
    os.makedirs(out, exist_ok=True)
    # 전체 reviews도 저장 (집계 시 id→상품명 매핑용)
    json.dump([{'p': r.get('_product') or r.get('productName') or '', 'r': r.get('rating')}
               for r in revs], open(f'{out}/_revs.json', 'w'), ensure_ascii=False)
    k = math.ceil(len(data) / chunks)
    for j in range(chunks):
        json.dump(data[j*k:(j+1)*k], open(f'{out}/chunk_{j}.json', 'w'), ensure_ascii=False)
    print(f"[{src}] 리뷰 {len(revs):,}건 / 텍스트({minlen}자+) {len(data):,}건 → chunk 0~{chunks-1} ({out})")
    neg = sum(1 for d in data if (d['r'] or 0) <= 3)
    print(f"  부정(1~3★) 텍스트 {neg:,}건  ※페인포인트 모수. 적으면 윙 추가수집 권장")


def aggregate(tagged_glob, axis, by_type, out, domain):
    tags = []
    for f in sorted(glob.glob(tagged_glob)):
        tags += json.load(open(f))
    revs = json.load(open(f'{out}/_revs.json')) if os.path.exists(f'{out}/_revs.json') else []
    N = len(tags)
    overall = Counter()
    bytype = defaultdict(Counter); typecnt = Counter()
    for t in tags:
        vals = t.get(axis) or []
        if isinstance(vals, str): vals = [vals]
        pt = product_type(revs[t['id']]['p'], domain) if t.get('id') is not None and t['id'] < len(revs) else '미상'
        typecnt[pt] += 1
        for v in vals:
            overall[v] += 1
            bytype[pt][v] += 1
    print(f"■ '{axis}' 집계 (전수 {N:,}건)\n")
    for k, v in overall.most_common():
        print(f"  {v/N*100:5.1f}%  {k}  ({v:,})")
    if by_type:
        print()
        for pt in typecnt:
            base = typecnt[pt]
            print(f"▶ {pt} ({base:,}건)")
            for k, v in bytype[pt].most_common(5):
                print(f"     {v/base*100:5.1f}%  {k}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    e = sub.add_parser('extract')
    e.add_argument('--category', default=''); e.add_argument('--scans', default='')
    e.add_argument('--minlen', type=int, default=15); e.add_argument('--chunks', type=int, default=7)
    e.add_argument('--out', default='/tmp/rev')
    a = sub.add_parser('aggregate')
    a.add_argument('--tagged', required=True); a.add_argument('--axis', default='usage')
    a.add_argument('--by-type', action='store_true'); a.add_argument('--out', default='/tmp/rev')
    a.add_argument('--domain', default='insole')
    args = ap.parse_args()
    if args.cmd == 'extract':
        extract(args.category, args.scans, args.minlen, args.chunks, args.out)
    elif args.cmd == 'aggregate':
        aggregate(args.tagged, args.axis, args.by_type, args.out, args.domain)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
