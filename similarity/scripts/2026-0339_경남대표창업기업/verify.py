import pandas as pd, numpy as np, re, sys, json
from decimal import Decimal, ROUND_HALF_UP
def q(x,n=2): return str(Decimal(repr(float(x))).quantize(Decimal('1.'+'0'*n), rounding=ROUND_HALF_UP))
XLSX='유사도_산출결과_경남대표창업기업.xlsx'; MD='유사중복_검토_경남대표창업기업.md'
C='종합유사도(0~100)'; AX=['사업목적','지원내용','지원대상','전달체계']
xl=pd.ExcelFile(XLSX); md=open(MD,encoding='utf-8').read(); fail=[]
d=xl.parse('전체')
def name_of(r):
    s='「'+str(r['세부사업명'])+' > '+str(r['내역사업명'])
    if str(r['내내역명']) not in ('','nan','None') and pd.notna(r['내내역명']): s+=' > '+str(r['내내역명'])
    return s+'」('+str(r['부처'])+')'
def chk(c,m):
    if not c: fail.append('[주장] '+m)
# 1) 표
tables,cur=[],[]
for line in md.split('\n'):
    if line.startswith('|'): cur.append(line)
    else:
        if cur: tables.append(cur); cur=[]
if cur: tables.append(cur)
res=[t for t in tables if '기존사업 단위(부처)' in t[0]]
assert len(res)==1, f'결과표 {len(res)}개'
rows=res[0][2:]; chk(len(rows)==20, f'표 행수 {len(rows)}')
for l in rows:
    c=[x.strip() for x in l.strip().strip('|').split('|')]
    rk=int(c[0]); r=d[d['순위']==rk].iloc[0]
    exp=[str(rk),name_of(r),str(r['단위']),q(r[C],1)]+[q(r[a+'_유사도']) for a in AX]+[q(r['참고2지표점수(0~100)'],1)]
    for i,(g,e) in enumerate(zip(c,exp)):
        if g!=e: fail.append(f'{rk}위 열{i+1}: 보고서 "{g}" ≠ 산출 "{e}"')
# 2) 분포
m,s=d[C].mean(),d[C].std(ddof=0); p=np.percentile(d[C],99)
print(f'n {len(d)} 평균 {q(m,1)} σ {q(s,1)} 최대 {q(d[C].max(),1)} 최소 {q(d[C].min(),1)} p99 {q(p,4)} 경계 {int(d[d[C]>=p]["순위"].max())}위 2σ {q(m+2*s)} 초과 {(d[C]>m+2*s).sum()}')
chk(len(d)==1233,f'1,233단위 (실제 {len(d)})')
chk(q(m,1)=='51.1' and q(s,1)=='3.9' and q(d[C].max(),1)=='63.6' and q(d[C].min(),1)=='41.1','분포')
chk(q(m+2*s)=='58.97' and (d[C]>m+2*s).sum()==45,'2σ 58.97 / 45개')
chk(q(p,4)=='61.7036' and int(d[d[C]>=p]['순위'].max())==13,'p99 / 13위')
chk(q(d[d['순위']==13].iloc[0][C])=='61.71' and q(d[d['순위']==14].iloc[0][C])=='61.69','13·14위')
v=d[C].head(22).tolist(); g=[float(q(v[i]-v[i+1])) for i in range(20)]
chk(max(g)==0.63 and g[2]==0.63, f'최대 간격 0.63이고 3→4 (실제 max {max(g)}, 3→4 {g[2]})')
chk(max(g[:2]+g[3:])<=0.20, f'그 외 구간 0.20 이하 (실제 {max(g[:2]+g[3:])})')
chk(q(v[19],2)==q(v[20],2)=='61.48', f'20·21위 동점 61.48 (실제 {q(v[19],2)} {q(v[20],2)})')
t=d.head(20)
chk(dict(t['부처'].value_counts())=={'중소벤처기업부':13,'경남':4,'과학기술정보통신부':2,'고용노동부':1}, f"부처 {dict(t['부처'].value_counts())}")
chk(dict(t['단위'].value_counts())=={'내내역사업':11,'내역사업':9},'단위 구성')
chk(int((t['연도']==2025).sum())==1,'2025년 1건')
for a,lo,hi in [('사업목적','0.56','0.73'),('지원내용','0.61','0.76'),('지원대상','0.43','0.67'),('전달체계','0.53','0.67')]:
    chk(q(t[a+'_유사도'].min())==lo and q(t[a+'_유사도'].max())==hi, f'{a} 범위 {lo}~{hi}')
gn=d[d['부처']=='경남']; ce=d[d['부처']!='경남']
chk(len(gn)==181 and q(gn[C].mean(),1)=='53.0' and len(ce)==1052 and q(ce[C].mean(),1)=='50.7','경남/중앙 평균')
chk(q(gn[C].mean()-ce[C].mean(),1)=='2.3','격차 2.3점')
chk(q(gn['지원대상_유사도'].mean(),4)=='0.4530' and q(ce['지원대상_유사도'].mean(),4)=='0.4861','지원대상축 평균')
core=gn['지원대상_텍스트'].astype(str).str.replace(r'\s*\(대상유형.*$','',regex=True).str.strip()
nf=int(core.str.match(r'^(<)?\s*(시비|도비|국비|지방비|자체사업|자체)').sum())
chk(nf==127 and q(nf/len(gn)*100,1)=='70.2', f'경남 재원기재 127건 70.2% (실제 {nf})')
pm={a:d.loc[d[a+'_유사도'].idxmax()] for a in AX}
chk(q(pm['사업목적']['사업목적_유사도'],4)=='0.7586' and pm['사업목적']['순위']==26,'사업목적 pool max 26위 0.7586')
chk(q(pm['지원내용']['지원내용_유사도'],4)=='0.7584' and pm['지원내용']['순위']==32,'지원내용 pool max 32위 0.7584')
chk(q(pm['지원대상']['지원대상_유사도'],4)=='0.6706' and pm['지원대상']['순위']==4,'지원대상 pool max 4위 0.6706')
chk(q(pm['전달체계']['전달체계_유사도'],4)=='0.6847' and pm['전달체계']['순위']==44,'전달체계 pool max 44위 0.6847')
chk(q(t['지원내용_유사도'].max(),4)=='0.7559' and int(t.loc[t['지원내용_유사도'].idxmax()]['순위'])==2,'후보 지원내용 최고 2위 0.7559')
chk(q(t['전달체계_유사도'].max())=='0.67' and set(int(x) for x in t[t['전달체계_유사도'].round(2)==0.67]['순위'])=={2,3,7},'후보 전달체계 최고 0.67 = 2·3·7위')
chk(t['세부사업명'].nunique()==14, f"세부사업 14 (실제 {t['세부사업명'].nunique()})")
vc=dict(t['세부사업명'].value_counts())
chk(vc.get('장애인기업육성')==4 and vc.get('글로벌창업생태계촉진')==2 and vc.get('ICT창의기업육성')==2 and vc.get('창업성장기술개발(R&D)')==2, f'묶음 {vc}')
chk(sorted(int(x) for x in t[t['세부사업명']=='장애인기업육성']['순위'])==[6,12,16,20],'장애인기업육성 4건 순위')
# 센터 11건
cc=gn[gn['기관'].astype(str).str.contains('경남창조경제혁신센터')]
chk(len(cc)==11, f'센터 수행 11건 (실제 {len(cc)})')
chk(sorted(int(x) for x in cc['순위'])==[2,3,7,33,43,44,45,60,102,121,129], f"센터 순위 {sorted(int(x) for x in cc['순위'])}")
ccore=cc['지원대상_텍스트'].astype(str).str.replace(r'\s*\(대상유형.*$','',regex=True).str.strip()
chk(int(ccore.str.match(r'^(시비|도비|국비|지방비)').sum())==11,'센터 11건 전부 재원 기재')
for n,nm,sc,bd in [(2,'경남형팁스','63.4','내역예산 210백만원'),(3,'경남창조경제혁신센터운영지원(국가직접지원)','63.3','내역예산 2,000백만원'),
                   (7,'경남형스타트업액셀러레이팅','62.3','내역예산 500백만원'),(32,'초기창업패키지지원사업(국가직접지원)','60.9','내역예산 100백만원'),
                   (33,'예비창업패키지지원사업(국가직접지원)','60.6','내역예산 100백만원'),(45,'창업도약패키지지원사업(국가직접지원)','59.0','내역예산 200백만원'),
                   (44,'동부권창업거점운영','59.1','내역예산 420백만원'),(26,'경남소재부품성장잠재기업육성사업','61.2','내역예산 100백만원')]:
    r=d[d['순위']==n].iloc[0]
    chk(str(r['세부사업명'])==nm and q(r[C],1)==sc and str(r['규모'])==bd, f'{n}위 {nm} {sc} {bd} (실제 {str(r["세부사업명"])} {q(r[C],1)} {r["규모"]})')
chk(str(d[d['순위']==32].iloc[0]['기관'])=='영산대학교 산학협력단','32위 영산대 산학협력단')
for n in (33,45,44): chk('경남창조경제혁신센터' in str(d[d['순위']==n].iloc[0]['기관']), f'{n}위 센터 수행')
chk(str(d[d['순위']==1].iloc[0]['규모'])=='지원규모 461,838백만원','1위 규모')
chk(q(d[d['순위']==1].iloc[0]['참고2지표점수(0~100)'],1)=='77.9' and q(t['참고2지표점수(0~100)'].max(),1)=='77.9','1위 환산점수 77.9 최고')
chk('사업화자금(평균 1.7억원 내외, 최대 3억원)' in str(d[d['순위']==1].iloc[0]['지원내용_텍스트']),'1위 공고 금액 문구')
chk('중소기업창업 지원법 제10조' in str(d[d['순위']==2].iloc[0]['지원내용_텍스트']),'2위 근거법령')
chk('도내 우수 창업기업' in str(d[d['순위']==7].iloc[0]['사업목적_텍스트']),'7위 도내 우수 창업기업 문구')
chk(str(d[d['순위']==4].iloc[0]['규모'])=='내역예산 300,000백만원','4위 규모')
chk(str(d[d['순위']==8].iloc[0]['규모'])=='지원규모 239,856백만원','8위 규모')
chk(str(d[d['순위']==18].iloc[0]['기관'])=='(재)경상남도투자경제진흥원' and str(d[d['순위']==18].iloc[0]['규모'])=='내역예산 50백만원','18위 기관·규모')
# 키워드
alltxt=d[[a+'_텍스트' for a in AX]].astype(str).agg(' '.join,axis=1)
for kw,n in [('창업',242),('사업화자금',31),('액셀러레이',36),('스케일업',38),('대표기업',5),('현판',8),('성과관리',9)]:
    got=int(alltxt.str.contains(kw,regex=False).sum()); chk(got==n, f"'{kw}' {n}건 (실제 {got})")
chk(int(alltxt[d['부처']=='경남'].str.contains('창업',regex=False).sum())==28, "경남 '창업' 28건")
chk(len(xl.parse('공고매핑'))==733,'공고매핑 733행')
chk(150000+30000==180000 and q(30000/180000*100,1)=='16.7','잔여 30,000천원 16.7%')
# 그림
spec=json.load(open('figspec.json',encoding='utf-8')); fig=json.dumps(spec,ensure_ascii=False)
chk(list(spec['행주석'].keys())==[str(x) for x in d.head(8)['공고이름']],'그림 행주석 키')
chk('0.7584' in fig and '70.2' in fig and '61.7036' in fig,'그림 핵심 수치')
pool=set()
for a in AX: pool|={q(x,4) for x in d[a+'_유사도']}|{q(x,2) for x in d[a+'_유사도']}
pool|={q(x,1) for x in d[C]}|{q(x,2) for x in d[C]}|{q(x,4) for x in d[C]}|{q(x,1) for x in d['참고2지표점수(0~100)']}
pool|={q(gn[a+'_유사도'].mean(),4) for a in AX}|{q(ce[a+'_유사도'].mean(),4) for a in AX}   # 보고서가 인용하는 축 평균
for src,tag in [(md,'수치'),(fig,'그림')]:
    for tok in sorted(set(re.findall(r'(?<![\d.])0\.\d{4}',src))):
        if tok not in pool: fail.append(f'[{tag}] {tok} 가 산출결과에 없음')
print('\n'.join(fail) if fail else '검증 통과: 불일치 0건'); print(f'총 {len(fail)}건 불일치')
sys.exit(1 if fail else 0)
