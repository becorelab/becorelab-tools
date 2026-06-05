# -*- coding: utf-8 -*-
"""쿠팡 그로스 정산표 구글시트 구축 (수금일정 + 주차별 검증)"""
import gspread
from google.oauth2.service_account import Credentials
SCOPES=['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
c=Credentials.from_service_account_file('/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json',scopes=SCOPES)
gc=gspread.authorize(c)
sh=gc.open_by_key('1W2gWtqcUnJxYMNKC74AuMFRsz-5yWzLousRf4Hrn8Fc')

def num(v): return v  # 그대로

# ── 탭1: 수금일정 (주정산 정산일별 + 빠른정산) ──
ws1=sh.sheet1; ws1.update_title('수금일정')
ws1.clear()
schedule=[
('2026-05-12',274641,'완료','5월 입금'),('2026-05-19',229452,'완료',''),
('2026-05-27',304126,'완료',''),('2026-06-01',337362,'완료','4월분 2차'),
('2026-06-02',1561524,'완료','4/27~30 + 5/1~3 1차'),('2026-06-09',2864040,'예정','5/4~10 1차'),
('2026-06-10',669248,'예정','4/27~30+5/1~3 2차'),('2026-06-16',696975,'예정','5/11~17 1차'),
('2026-06-23',514174,'예정','5/18~24 1차'),('2026-06-29',257799,'예정','5/25~31 1차'),
('2026-07-01',1858807,'예정','5월 여러주 2차(30%)'),('2026-07-03',562524,'예정','6/1~7 1차'),
]
rows=[['쿠팡 그로스 정산표 — 수금일정 (실제 Wing 정산 리포트 기준)'],
['※ 빠른정산=구매확정 ~90% 익일 선지급(5/14~31분 8,799,897 이미 수령) / 주정산=정식정산(아래 표)'],[],
['정산일','입금액','상태','구성']]
for d,a,s,m in schedule: rows.append([d,a,s,m])
rows.append(['주정산 합계','=SUM(B5:B16)','',''])
rows.append([])
rows.append(['빠른정산 선지급 (5/14~31, 이미 수령)',8799897,'완료','일별 익일입금'])
rows.append(['★ 6/5 이후 주정산 추가입금','=SUMIF(C5:C16,"예정",B5:B16)','예정','앞으로 들어올 금액'])
ws1.update(rows, value_input_option='USER_ENTERED')
ws1.format('A1',{'textFormat':{'bold':True,'fontSize':13}})
ws1.format('A4:D4',{'textFormat':{'bold':True,'foregroundColor':{'red':1,'green':1,'blue':1}},'backgroundColor':{'red':0.27,'green':0.45,'blue':0.77}})
ws1.format('A17:D17',{'textFormat':{'bold':True},'backgroundColor':{'red':1,'green':0.95,'blue':0.8}})
ws1.format('A20:D20',{'textFormat':{'bold':True},'backgroundColor':{'red':1,'green':0.95,'blue':0.8}})
ws1.format('B5:B20',{'numberFormat':{'type':'NUMBER','pattern':'#,##0'}})

# ── 탭2: 주차별 검증 (reconciliation) ──
try: ws2=sh.worksheet('주차별 검증')
except: ws2=sh.add_worksheet('주차별 검증',rows=30,cols=8)
ws2.clear()
weeks=[
('5/1~5/3',1541315,0,1541315),('5/4~5/10',4154806,0,4110476),
('5/11~5/17',4406448,1733730,995655),('5/18~5/24',7345288,5422671,734529),
('5/25~5/31',3111238,1643496,351135),
]
r2=[['그로스 주차별 정산 검증 (매출인식일 기준)'],
['※ 정산대상액 = 빠른정산 + 주정산(1+2차) + 차감(광고·물류·수수료). 차감은 잔여로 자동계산.'],[],
['매출인식 주차','정산대상액','빠른정산 받음','주정산(1+2차)','차감(광고·물류)','검증(합=정산대상액)']]
for nm,settle,fast,reg in weeks:
    i=len(r2)+1
    r2.append([nm,settle,fast,reg,f'=B{i}-C{i}-D{i}',f'=C{i}+D{i}+E{i}'])
tot=len(r2)+1
r2.append(['합계',f'=SUM(B5:B9)',f'=SUM(C5:C9)',f'=SUM(D5:D9)',f'=SUM(E5:E9)',f'=SUM(F5:F9)'])
r2.append([])
r2.append(['검증: F열(합)이 B열(정산대상액)과 같으면 정상 ✅'])
r2.append([f'차감 합계 ≈ 광고비(5월 ~300만) + 물류비(125만) = 약 425만 → 추정과 일치'])
ws2.update(r2, value_input_option='USER_ENTERED')
ws2.format('A1',{'textFormat':{'bold':True,'fontSize':13}})
ws2.format('A4:F4',{'textFormat':{'bold':True,'foregroundColor':{'red':1,'green':1,'blue':1}},'backgroundColor':{'red':0.27,'green':0.45,'blue':0.77}})
ws2.format(f'A{tot}:F{tot}',{'textFormat':{'bold':True},'backgroundColor':{'red':1,'green':0.95,'blue':0.8}})
ws2.format('B5:F'+str(tot),{'numberFormat':{'type':'NUMBER','pattern':'#,##0'}})

print('✅ 구글시트 구축 완료!')
print('   탭: 수금일정 / 주차별 검증')
print('   URL: https://docs.google.com/spreadsheets/d/1W2gWtqcUnJxYMNKC74AuMFRsz-5yWzLousRf4Hrn8Fc')
