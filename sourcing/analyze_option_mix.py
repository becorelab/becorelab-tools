"""수집된 리뷰의 옵션 구성 분포 분석 (1개입 vs 다구성)
사용: python3 analyze_option_mix.py 섬유탈취제
리뷰 수 ∝ 판매량 → 옵션별 리뷰 수로 인기 구성 판단
"""
import json, glob, os, re, sys
from collections import defaultdict

kw = sys.argv[1] if len(sys.argv)>1 else "섬유탈취제"
base = f"/Users/macmini_ky/ClaudeAITeam/sourcing/review_output/{kw}"

def pack_count(opt):
    """옵션명에서 묶음 수량 추출 → 1 / 2 / 3+ 분류"""
    if not opt: return "미표기"
    # "N개입", "N개", "N팩", "Nea" 등에서 묶음수 (용량 ml/g 제외)
    # 끝쪽 "N개" 우선 (구성 수량)
    m = re.findall(r'(\d+)\s*개(?!입)', opt)  # "1개","2개"(개입 아님)
    if m:
        n = int(m[-1])
    else:
        m2 = re.findall(r'(\d+)\s*(?:팩|set|세트|ea|병|입니다)', opt, re.I)
        n = int(m2[-1]) if m2 else 1
    if n <= 1: return "1개입(단품)"
    elif n == 2: return "2개 구성"
    elif n == 3: return "3개 구성"
    else: return f"{n}개+ 대용량"

total_reviews = 0
prod_count = 0
mix = defaultdict(int)
mix_by_product = []
for f in glob.glob(f"{base}/*.json"):
    if os.path.basename(f).startswith("_"): continue
    try: d = json.load(open(f, encoding='utf-8'))
    except: continue
    prod_count += 1
    title = d.get('product_title','')[:30]
    pm = defaultdict(int)
    for r in d.get('reviews', []):
        opt = r.get('option','')
        cat = pack_count(opt)
        mix[cat] += 1; pm[cat] += 1; total_reviews += 1
    top = max(pm.items(), key=lambda x:x[1])[0] if pm else '-'
    mix_by_product.append((title, sum(pm.values()), top))

print(f"=== {kw} 옵션 구성 분포 ===")
print(f"분석 상품 {prod_count}개 / 총 리뷰 {total_reviews:,}개\n")
print("[전체 옵션 구성별 리뷰 수 (= 판매 인기)]")
for cat, cnt in sorted(mix.items(), key=lambda x:-x[1]):
    pct = cnt/total_reviews*100 if total_reviews else 0
    bar = '█'*int(pct/3)
    print(f"  {cat:14} {cnt:>6,}개 ({pct:4.1f}%) {bar}")
print(f"\n[상품별 1등 구성 (상위 8개)]")
for t,c,top in sorted(mix_by_product, key=lambda x:-x[1])[:8]:
    print(f"  {t:32} 리뷰{c:>5,} → {top}")
