import json, glob, re, requests, sys
from collections import defaultdict
kw, sid = sys.argv[1], sys.argv[2]
prods=requests.get(f'http://localhost:8090/api/scan/{sid}',timeout=15).json().get('products',[])
def pid(u):
    m=re.search(r'/products/(\d+)',u or'');return m.group(1) if m else None
src={pid(p.get('product_url','')):p for p in prods if pid(p.get('product_url',''))}
def bundle(o):
    if not o:return 1
    m=re.findall(r'(\d+)\s*세트',o) or re.findall(r'[xX]\s*(\d+)',o)
    if m:return min(int(m[-1]),9)
    sm=[int(x) for x in re.findall(r'(\d+)\s*개(?!입)',o) if int(x)<10]
    return sm[-1] if sm else 1
base=f'/Users/macmini_ky/ClaudeAITeam/sourcing/review_output/{kw}'
rb=defaultdict(float); brev=defaultdict(float); bcfg=defaultdict(lambda:defaultdict(list)); tot=0; mt=0
for f in glob.glob(base+'/*.json'):
    if '/_' in f: continue
    d=json.load(open(f,encoding='utf-8')); s=src.get(str(d.get('product_id')))
    if not s: continue
    mt+=1; rm=s.get('revenue_monthly') or 0
    bc=defaultdict(int); t=0
    for r in d.get('reviews',[]):
        c=bundle(r.get('option','')); bc[c]+=1; t+=1; tot+=1
    if t:
        ws=sum(bc[c]*c for c in bc)
        for c in bc: rb[c]+=rm*(bc[c]*c/ws) if ws else 0
        rep=max(bc,key=bc.get)
        if s.get('price'): bcfg[s.get('brand') or '무명'][rep].append(s['price'])
    brev[s.get('brand') or '무명']+=rm
nm={1:'1개입',2:'2개',3:'3개',4:'4개+'}
def label(c): return nm.get(c, str(c)+'개')
print(f'=== {kw} | {mt}상품 / {tot:,}리뷰 ===')
tb=sum(rb.values()) or 1
print('[묶음 구성별 매출]')
for c in sorted(rb,key=lambda x:-rb[x])[:4]:
    print('  %-8s %4.1f%%' % (label(c), rb[c]/tb*100))
print('[상위 브랜드 (구성별 가격)]')
for b,v in sorted(brev.items(),key=lambda x:-x[1])[:5]:
    cfgs=bcfg.get(b,{})
    cs=' / '.join('%s %s원'%(label(c), format(int(sum(p)/len(p)),',')) for c,p in sorted(cfgs.items()))
    print('  %-12s 월%.2f억 | %s' % (b[:12], v/1e8, cs))
