#!/usr/bin/env python3
"""리뷰 질의 도구 — 쌓인 쿠팡 리뷰 33만건+을 키워드·별점·카테고리로 즉시 검색·집계.

데이터 소스 2곳을 통합 질의:
  • 파일(review_output/{카테고리}/): 자사·경쟁사 카테고리 31만건+ (고체탈취제·섬유탈취제·건조기시트 등)
  • Firestore(collected_reviews): 소싱 스캔 리뷰 (깔창·입테이프 등)

사용 예:
  python review_query.py --list                              # 질의 가능한 카테고리 목록
  python review_query.py --category 고체탈취제 --keyword 향 --top
  python review_query.py --category 섬유탈취제 --keyword "지속|오래" --rating 4-5
  python review_query.py --category 깔창 --keyword 냄새        # 깔창=Firestore
  python review_query.py --category 캡슐세제 --rating 1-2 --top  # 경쟁사 불만 TOP

하치가 대표님 자연어 질문 → 적절한 카테고리/키워드/필터로 변환해 즉답하는 용도.
"""
import sys, os, re, glob, argparse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RO = os.path.join(HERE, 'review_output')
sys.path.insert(0, HERE)

# Firestore 전용 카테고리 별칭 → scan_id (파일 폴더에 없는 소싱 스캔)
CATEGORY = {
    '족저근막염': [6011], '쿠션': [6019], '푹신': [6019], '기능성': [6020],
    '남자깔창': [6068, 245], '깔창': [6011, 6019, 6020, 6068, 245],
    '입테이프': [298], '입벌림': [298], '심리스팬티': [255], '심리스': [255],
    '배수구트랩': [2411], '배수구': [2411], '유치원파우치': [258], '파우치': [258],
    '수면브라': [139], '초시계': [219],
}

STOP = set('그냥 진짜 너무 정말 구매 사용 제품 이거 근데 조금 구입 했는데 샀는데 같아요 있어요 '
           '없어요 그리고 하지만 약간 다른 때문 사용감 이건 경우 정도 느낌 생각 이렇게 저는 제가 하나 '
           '우리 해서 보고 거의 계속 인데 으로 에서 한데 네요 어요 구요 아요 많이 이제 완전 그래도 '
           '이런 저런 아주 정말로 사용했 좋아요 좋고 좋은 잘 안 더 또 수 것 거 게 도 는 은 이 가 를'.split())


def _fdb():
    from analyzer import firestore_db as fdb
    return fdb


def load_file_reviews(folder):
    revs = []
    for f in glob.glob(os.path.join(RO, folder, '*.json')):
        if os.path.basename(f).startswith('_'):
            continue
        try:
            import json
            d = json.load(open(f))
            title = (d.get('product_title', '') or '')[:18]
            for r in (d.get('reviews', []) or []):
                r['productName'] = title
                revs.append(r)
        except Exception:
            pass
    return revs


def parse_rating(s):
    if not s:
        return None
    if '-' in s:
        a, b = s.split('-')
        return set(range(int(a), int(b) + 1))
    return {int(x) for x in s.split(',')}


def do_list():
    import json
    print("=== 📁 파일 리뷰 (review_output) ===")
    rows = []
    for c in os.listdir(RO):
        cd = os.path.join(RO, c)
        if not os.path.isdir(cd):
            continue
        n = 0
        for f in glob.glob(os.path.join(cd, '*.json')):
            if os.path.basename(f).startswith('_'):
                continue
            try:
                n += len(json.load(open(f)).get('reviews', []))
            except Exception:
                pass
        if n:
            rows.append((c, n))
    for c, n in sorted(rows, key=lambda x: -x[1]):
        print(f"  --category {c:<22} {n:>8,}건")
    filetot = sum(n for _, n in rows)
    print(f"\n=== ☁️ Firestore 스캔 ===")
    fdb = _fdb()
    cnt = Counter()
    for d in fdb.db().collection('collected_reviews').stream():
        cnt[d.to_dict().get('scan_id')] += 1
    for sid, n in cnt.most_common():
        s = fdb.get_scan(sid)
        print(f"  --scans {sid:<6} {n:>8,}건  {s.get('keyword','?') if s else ''}")
    fstot = sum(cnt.values())
    print(f"\n총 {filetot + fstot:,}건 (파일 {filetot:,} + Firestore {fstot:,})")
    print("Firestore 별칭:", ', '.join(sorted(set(CATEGORY))))


def resolve(category, scans):
    """(reviews, 소스라벨) 반환"""
    if scans:
        fdb = _fdb()
        revs = []
        for sid in scans:
            revs += fdb.get_reviews(sid)
        return revs, f"Firestore scan {scans}"
    # 1) review_output 폴더 부분매칭 (예: '탈취제' → 섬유/고체탈취제)
    folders = [c for c in os.listdir(RO)
               if os.path.isdir(os.path.join(RO, c)) and category in c]
    if folders:
        revs = []
        for c in folders:
            revs += load_file_reviews(c)
        return revs, f"파일: {', '.join(folders)}"
    # 2) Firestore 별칭
    if category in CATEGORY:
        fdb = _fdb()
        revs = []
        for sid in CATEGORY[category]:
            revs += fdb.get_reviews(sid)
        return revs, f"Firestore {category}"
    return [], None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scans', default='')
    ap.add_argument('--category', default='')
    ap.add_argument('--keyword', default='', help='OR 검색: "냄새|향"')
    ap.add_argument('--rating', default='', help='"1-3" / "5" / "1,2"')
    ap.add_argument('--samples', type=int, default=10)
    ap.add_argument('--top', action='store_true')
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()

    if args.list:
        do_list()
        return

    scans = [int(x) for x in args.scans.split(',')] if args.scans else []
    revs, src = resolve(args.category, scans)
    if src is None:
        print(f"'{args.category}' 카테고리를 못 찾음. --list로 목록 확인"); return
    total_all = len(revs)

    rset = parse_rating(args.rating)
    if rset:
        revs = [r for r in revs if (r.get('rating') or 0) in rset]
    kws = [k.strip() for k in args.keyword.split('|') if k.strip()] if args.keyword else []
    if kws:
        revs = [r for r in revs if any(k in (r.get('content', '') or '') for k in kws)]

    print(f"\n■ [{src}] 전체 {total_all:,}건 중 매칭 {len(revs):,}건", end='')
    if kws:
        print(f"  | 키워드 {' | '.join(kws)}", end='')
    if rset:
        print(f"  | 별점 {sorted(rset)}", end='')
    print()
    if not revs:
        return

    dist = Counter(r.get('rating') for r in revs)
    avg = sum((r.get('rating') or 0) for r in revs) / len(revs)
    print(f"  별점분포: {dict(sorted(dist.items()))} | 평균 {avg:.2f}")
    if kws and total_all:
        print(f"  → 전체의 {len(revs)/total_all*100:.1f}%가 이 키워드 언급")

    if args.top:
        text = ' '.join((r.get('content', '') or '') for r in revs)
        words = [w for w in re.findall(r'[가-힣]{2,}', text) if w not in STOP]
        print(f"  키워드 TOP20: {Counter(words).most_common(20)}")

    shown = [r for r in revs if len((r.get('content', '') or '')) > 25]
    print(f"  [대표 샘플 {min(args.samples, len(shown))}개]")
    for r in shown[:args.samples]:
        c = (r.get('content', '') or '').replace('\n', ' ').strip()
        print(f"   [{r.get('rating')}★|{(r.get('productName') or '')[:14]}] {c[:130]}")


if __name__ == '__main__':
    main()
