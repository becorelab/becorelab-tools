# -*- coding: utf-8 -*-
"""쿠팡 그로스 정산표 구글시트 — 2026년 6월(1~14일) 반영"""
import openpyxl, glob, os, json
from collections import defaultdict
import gspread
from google.oauth2.service_account import Credentials

KEY="/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json"
SID="1W2gWtqcUnJxYMNKC74AuMFRsz-5yWzLousRf4Hrn8Fc"
SRC="/Users/macmini_ky/Library/CloudStorage/GoogleDrive-cky2833@gmail.com/내 드라이브/앱/매출 정산/26.05/그로스"

NAME={'95304424363':'바이올렛 머스크 1개','95363500368':'바이올렛 머스크 2개','95363500367':'바이올렛 머스크 3개',
 '95377476928':'베이비크림 1개','95304888338':'얼룩제거제 350ml','95304888360':'얼룩제거제 2개','95304888356':'얼룩제거제 3개',
 '95060453340':'입테이프 1개','95060453345':'입테이프 2개','95060453346':'입테이프 3개',
 '95060453344':'입테이프 4개','95060453347':'입테이프 5개','95060453343':'입테이프 6개'}
COST={'95304424363':3932,'95363500368':7864,'95363500367':11796,'95377476928':3932,
 '95304888338':3199,'95304888360':6398,'95304888356':9597,
 '95060453340':2200,'95060453345':4400,'95060453346':6600,'95060453344':8800,'95060453347':11000,'95060453343':13200}

# 6월 제품별 집계
os.chdir(SRC)
prod=defaultdict(lambda:{'수량':0,'정산':0})
for f in glob.glob('*CATEGORY_TR*'):
    wb=openpyxl.load_workbook(f,read_only=True,data_only=True);ws=wb.active
    for r in ws.iter_rows(min_row=2,values_only=True):
        if not r or r[0] is None: continue
        rec=str(r[4])[:10]
        if not ('2026-06-01'<=rec<='2026-06-14'): continue
        oid=str(r[11]).split('.')[0]
        try: q=float(r[16] or 0); st=float(r[23] or 0)
        except: continue
        prod[oid]['수량']+=q; prod[oid]['정산']+=st
    wb.close()
def cm(n): return f"{int(round(n)):,}"

# 6월 월별 손익 상수 (정산표 빌드와 동일)
J={'판매액':11403920,'정산대상액':10035610,'원가':4025109,'물류':2376926,'광고':1370103}
J['이익']=J['정산대상액']-J['원가']-J['물류']-J['광고']
J_io,J_sp,J_st=1273350,1103576,0   # 입출고/배송/보관 (VAT포함 최종비용)

cr=Credentials.from_service_account_file(KEY,scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])
gc=gspread.authorize(cr); sh=gc.open_by_key(SID)

# ===== 1) 6월 제품별 정산 탭 =====
title6='6월 제품별 정산'
try: ws6=sh.worksheet(title6); ws6.clear()
except gspread.WorksheetNotFound: ws6=sh.add_worksheet(title=title6,rows=30,cols=6)
rows=[['로켓그로스 6월(1~14일) 제품별 정산'],[],['품명','수량','정산금액','원가','이익']]
tot={'수량':0,'정산':0,'원가':0,'이익':0}
for oid in sorted(prod,key=lambda x:-prod[x]['정산']):
    nm=NAME.get(oid,oid); q=prod[oid]['수량']; st=prod[oid]['정산']; cc=COST.get(oid,0)*q; pf=st-cc
    rows.append([nm,cm(q),cm(st),cm(cc),cm(pf)])
    tot['수량']+=q; tot['정산']+=st; tot['원가']+=cc; tot['이익']+=pf
rows.append(['합계',cm(tot['수량']),cm(tot['정산']),cm(tot['원가']),cm(tot['이익'])])
ws6.update(rows,'A1')

# ===== 2) 월별 손익 탭 재작성 (6월 추가 + #REF 수정) =====
wl=sh.worksheet('월별 손익')
M3=['3월','121,050','86,684','37,400','0','0','49,284','40.7%']
M4=['4월','3,046,360','2,446,898','862,260','0','370,780','1,213,858','39.8%']
M5=['5월','23,375,860','20,559,095','8,472,726','1,255,172','3,007,623','7,823,574','33.5%']
M6=['6월(1~14일)',cm(J['판매액']),cm(J['정산대상액']),cm(J['원가']),cm(J['물류']),cm(J['광고']),cm(J['이익']),f"{J['이익']/J['판매액']*100:.1f}%"]
def col(i,*ms): return sum(int(m[i].replace(',','')) for m in ms)
S=[col(1,M3,M4,M5,M6),col(2,M3,M4,M5,M6),col(3,M3,M4,M5,M6),col(4,M3,M4,M5,M6),col(5,M3,M4,M5,M6),col(6,M3,M4,M5,M6)]
SUM=['합계',cm(S[0]),cm(S[1]),cm(S[2]),cm(S[3]),cm(S[4]),cm(S[5]),f"{S[5]/S[0]*100:.1f}%"]
data=[['로켓그로스 월별 손익 (3~6월, 정산주기 기준)'],[],
 ['월','판매액','정산대상액','원가','물류비','광고비','이익','이익률'],
 M3,M4,M5,M6,SUM,[],
 ['[ 5월 물류비 상세 ]'],['항목','금액','비고'],
 ['입출고비','679,819','CFS 입출고 (VAT포함)'],['배송비','575,353','CFS 배송 (VAT포함)'],
 ['보관비','0','세이버 혜택 면제'],['물류비 계','1,255,172','입출고+배송+보관'],[],
 ['[ 6월(1~14일) 물류비 상세 ]'],['항목','금액','비고'],
 ['입출고비',cm(J_io),'CFS 입출고 (VAT포함)'],['배송비',cm(J_sp),'CFS 배송 (VAT포함)'],
 ['보관비','0','세이버 혜택 면제'],['물류비 계',cm(J_io+J_sp+J_st),'입출고+배송+보관'],
 ['※ 비용제로(입고90일) 만료로 6월 물류비 급증. 요율은 동일(극소형 입출고1,650/배송2,200).','',''],
 ['※ 발생비용(할인前) 372만 중 218만 실부과, 41% 면제(저가상품 할인, 2027.1.31 종료 예정).','','']]
wl.clear(); wl.update(data,'A1')

# ===== 3) 수금일정 탭 — 6월 주정산 append =====
wd=sh.worksheet('수금일정')
vals=wd.get_all_values()
last=len(vals)
add=[['2026-07-03','390,047','예정','6/1~7 1차 70%'],['2026-07-10','305,791','예정','6/8~14 1차 70%']]
wd.update(add, f'A{last+1}')

print('완료!')
print(' 6월 제품별 정산 탭:', len(rows)-3,'품목 / 정산합', cm(tot['정산']),'/ 이익', cm(tot['이익']))
print(' 월별 손익: 6월 추가 + 5월 #REF 수정 / 합계 이익', cm(S[5]))
print(' 수금일정: 7/3·7/10 주정산 추가')
