# -*- coding: utf-8 -*-
"""그로스 정산표 구글시트 — 월별 손익(물류비 상세) + 제품별 정산 탭 추가"""
import gspread, json
from google.oauth2.service_account import Credentials
SCOPES=['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
c=Credentials.from_service_account_file('/Users/macmini_ky/ClaudeAITeam/sourcing/analyzer/becorelab-tools-firebase-adminsdk-fbsvc-4af6f0c5ac.json',scopes=SCOPES)
gc=gspread.authorize(c)
sh=gc.open_by_key('1W2gWtqcUnJxYMNKC74AuMFRsz-5yWzLousRf4Hrn8Fc')
d=json.load(open('/tmp/gross_excel.json'))
HDR={'textFormat':{'bold':True,'foregroundColor':{'red':1,'green':1,'blue':1}},'backgroundColor':{'red':0.27,'green':0.45,'blue':0.77}}
TOT={'textFormat':{'bold':True},'backgroundColor':{'red':1,'green':0.95,'blue':0.8}}
SUB={'textFormat':{'bold':True},'backgroundColor':{'red':0.85,'green':0.92,'blue':0.83}}
def N(v):
    try: return float(v)
    except: return v

# ── 월별 손익 (물류비 상세 포함) ──
try: ws=sh.worksheet('월별 손익')
except: ws=sh.add_worksheet('월별 손익',rows=40,cols=10)
ws.clear()
rows=[['로켓그로스 월별 손익 (3~5월)'],[],
['월','판매액','정산대상액','원가','물류비','광고비','이익','이익률']]
data={'3월':(121050,86684,37400,0,0),'4월':(3046360,2446898,862260,0,370780),'5월':(23375860,20559095,8472726,1255172,3007623)}
ri=4
for m in ['3월','4월','5월']:
    s=data[m]; r=ri
    rows.append([m,s[0],s[1],s[2],s[3],s[4],f'=C{r}-D{r}-E{r}-F{r}',f'=G{r}/B{r}']); ri+=1
rows.append(['합계','=SUM(B4:B6)','=SUM(C4:C6)','=SUM(D4:D6)','=SUM(E4:E6)','=SUM(F4:F6)','=SUM(G4:G6)','=G7/B7'])
rows.append([])
rows.append(['[ 5월 물류비 상세 ]'])
rows.append(['항목','금액','비고'])
rows.append(['입출고비',679819,'CFS 입출고 (VAT포함)'])
rows.append(['배송비',575353,'CFS 배송 (VAT포함)'])
rows.append(['보관비',0,'세이버 혜택 면제'])
rows.append(['물류비 계','=SUM(B12:B14)','= 월별손익 5월 물류비'])
rows.append(['※ 비용제로(입고 90일)로 5/17주차까지 물류비 0원, 5/24주차부터 부과 시작'])
rows.append(['※ 이익 = 정산대상액 − 원가 − 물류비 − 광고비 (영업이익, 본사 간접비 제외)'])
ws.update(rows, value_input_option='USER_ENTERED')
ws.format('A1',{'textFormat':{'bold':True,'fontSize':13}})
ws.format('A3:H3',HDR); ws.format('A7:H7',TOT)
ws.format('A10:C10',SUB); ws.format('A15:C15',TOT)
ws.format('A9',{'textFormat':{'bold':True,'fontSize':11}})
ws.format('B4:F7',{'numberFormat':{'type':'NUMBER','pattern':'#,##0'}})
ws.format('G4:G7',{'numberFormat':{'type':'NUMBER','pattern':'#,##0'}})
ws.format('H4:H7',{'numberFormat':{'type':'PERCENT','pattern':'0.0%'}})
ws.format('B11:B15',{'numberFormat':{'type':'NUMBER','pattern':'#,##0'}})

# ── 제품별 정산 (5월) ──
try: ws2=sh.worksheet('제품별 정산')
except: ws2=sh.add_worksheet('제품별 정산',rows=30,cols=6)
ws2.clear()
prows=[['로켓그로스 5월 제품별 정산'],[],['품명','수량','정산금액','원가','이익']]
prod=[r for r in d['product'] if r[0] not in ('품명','합계')]
prod=[r for r in prod if not str(r[0]).startswith('※')]
for r in prod:
    if r[0]=='합계' or str(r[0]).startswith('※'): continue
    prows.append([r[0],N(r[1]),N(r[2]),N(r[3]),N(r[4])])
n=len(prows)
prows.append(['합계',f'=SUM(B4:B{n})',f'=SUM(C4:C{n})',f'=SUM(D4:D{n})',f'=SUM(E4:E{n})'])
prows.append([])
prows.append(['※ 정산금액=정산대상액(수수료 차감후), 이익=정산금액−원가. 물류비·광고비는 [월별 손익] 참조'])
ws2.update(prows, value_input_option='USER_ENTERED')
ws2.format('A1',{'textFormat':{'bold':True,'fontSize':13}})
ws2.format('A3:E3',HDR); ws2.format(f'A{n+1}:E{n+1}',TOT)
ws2.format(f'B4:E{n+1}',{'numberFormat':{'type':'NUMBER','pattern':'#,##0'}})

# 탭 순서 정리
order=['제품별 정산','월별 손익','수금일정','주차별 검증']
sh.reorder_worksheets([sh.worksheet(t) for t in order if t in [w.title for w in sh.worksheets()]])
print('✅ 탭 추가 완료: 제품별 정산 / 월별 손익(물류비 상세 포함)')
print('탭 순서:', [w.title for w in sh.worksheets()])
