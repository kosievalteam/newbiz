import pandas as pd, numpy as np, re, sys, json
from decimal import Decimal, ROUND_HALF_UP
def q(x,n=2): return str(Decimal(repr(float(x))).quantize(Decimal('1.'+'0'*n), rounding=ROUND_HALF_UP))
XLSX='유사도_산출결과_부산북극항로연관산업.xlsx'; MD='유사중복_검토_부산북극항로연관산업.md'
C='종합유사도(0~100)'; AX=['사업목적','지원내용','지원대상','전달체계']
xl=pd.ExcelFile(XLSX); md=open(MD,encoding='utf-8').read(); fail=[]
SHEETS=['전체','기능1 기업육성·R&D','기능2 국제협력 네트워크']
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
assert len(res)==3, f'결과표 {len(res)}개'
for sh,tb in zip(SHEETS,res):
    dd=xl.parse(sh); rows=tb[2:]
    if len(rows)!=20: fail.append(f'[{sh}] 표 행수 {len(rows)}')
    for l in rows:
        c=[x.strip() for x in l.strip().strip('|').split('|')]
        rk=int(c[0]); r=dd[dd['순위']==rk].iloc[0]
        exp=[str(rk),name_of(r),str(r['단위']),q(r[C],1)]+[q(r[a+'_유사도']) for a in AX]+[q(r['참고2지표점수(0~100)'],1)]
        for i,(g,e) in enumerate(zip(c,exp)):
            if g!=e: fail.append(f'[{sh}] {rk}위 열{i+1}: 보고서 "{g}" ≠ 산출 "{e}"')

# 2) 분포
m,s=d[C].mean(),d[C].std(ddof=0); p=np.percentile(d[C],99)
for sh in SHEETS:
    dd=xl.parse(sh); mm,ss=dd[C].mean(),dd[C].std(ddof=0); pp=np.percentile(dd[C],99)
    lr=int(dd[dd[C]>=pp]['순위'].max())
    print(f'{sh}: 평균 {q(mm,1)} σ {q(ss,1)} 최대 {q(dd[C].max(),1)} p99 {q(pp,4)} 경계 {lr}위({q(dd[dd["순위"]==lr].iloc[0][C])}) 다음 {q(dd[dd["순위"]==lr+1].iloc[0][C])} 2σ {q(mm+2*ss)} 초과 {(dd[C]>mm+2*ss).sum()}')
chk(len(d)==1222, f'1,222단위 (실제 {len(d)})')
chk(q(m,1)=='53.1' and q(s,1)=='2.9' and q(d[C].max(),1)=='61.7' and q(d[C].min(),1)=='43.8','전체 분포')
chk(q(m+2*s)=='58.93' and (d[C]>m+2*s).sum()==24,'전체 2σ 58.93 / 24개')
chk(q(p,4)=='59.8838' and int(d[d[C]>=p]['순위'].max())==13,'전체 p99 / 13위')
chk(q(d[d['순위']==13].iloc[0][C])=='59.93' and q(d[d['순위']==14].iloc[0][C])=='59.71','13·14위')
v=d[C].head(21).tolist(); g=[float(q(v[i]-v[i+1])) for i in range(20)]
chk(max(g)==0.54 and g[1]==0.54, f'최대 간격 0.54이고 2→3 (실제 max {max(g)}, 2→3 {g[1]})')
chk(g[2]==0.06 and g[3]==0.02, f'3→4 0.06, 4→5 0.02 (실제 {g[2]}, {g[3]})')
for n,val in [(3,'61.04'),(4,'60.98'),(5,'60.96')]:
    chk(q(d[d['순위']==n].iloc[0][C])==val, f'{n}위 {val}')
t=d.head(20)
chk(dict(t['부처'].value_counts())=={'해양수산부':7,'산업통상부':6,'중소벤처기업부':3,'과학기술정보통신부':2,'문화체육관광부':1,'부산':1}, f"전체 부처 {dict(t['부처'].value_counts())}")
chk(dict(t['단위'].value_counts())=={'내역사업':19,'내내역사업':1},'전체 단위 구성')
chk(int((t['연도']==2025).sum())==1 and int(t[t['연도']==2025].iloc[0]['순위'])==3,'2025년 1건 = 3위')
for a,lo,hi in [('사업목적','0.55','0.62'),('지원내용','0.62','0.70'),('지원대상','0.52','0.63'),('전달체계','0.51','0.68')]:
    chk(q(t[a+'_유사도'].min())==lo and q(t[a+'_유사도'].max())==hi, f'전체 {a} 범위 {lo}~{hi}')
bs=d[d['부처']=='부산']; ce=d[d['부처']!='부산']
chk(len(bs)==170 and q(bs[C].mean(),1)=='53.3' and len(ce)==1052 and q(ce[C].mean(),1)=='53.1','부산/중앙 평균')
pm={a:d.loc[d[a+'_유사도'].idxmax()] for a in AX}
chk(q(pm['사업목적']['사업목적_유사도'],4)=='0.6277' and pm['사업목적']['순위']==129,'사업목적 pool max 129위 0.6277')
chk(q(pm['지원내용']['지원내용_유사도'],4)=='0.7200' and pm['지원내용']['순위']==95,'지원내용 pool max 95위 0.7200')
chk(q(pm['지원대상']['지원대상_유사도'],4)=='0.6284' and pm['지원대상']['순위']==6,'지원대상 pool max 6위 0.6284')
chk(q(pm['전달체계']['전달체계_유사도'],4)=='0.7012' and pm['전달체계']['순위']==383,'전달체계 pool max 383위 0.7012')
chk((d['사업목적_유사도']>=0.63).sum()==0,'사업목적 0.63 이상 0건')
chk(t['세부사업명'].nunique()==15, f"전체 세부사업 15 (실제 {t['세부사업명'].nunique()})")
chk(sorted(int(x) for x in t[t['세부사업명']=='해양수산신산업육성및기업투자유치지원']['순위'])==[1,2,3,7],'해수부 4건 순위')
chk(str(d[d['순위']==1].iloc[0]['규모'])=='지원규모 9,248백만원','1위 규모')
chk('부산시' in str(d[d['순위']==1].iloc[0]['기관']),'1위 수행기관에 부산시')
chk('시제품 제작, 실증, 해외인증, 홍보 등 지원' in str(d[d['순위']==1].iloc[0]['사업목적_텍스트']),'1위 시제품 문구')
chk('해양수산 중소·중견기업 등' in str(d[d['순위']==1].iloc[0]['지원대상_텍스트']),'1위 지원대상')
chk(str(d[d['순위']==4].iloc[0]['규모'])=='지원규모 104,474백만원','4위 규모')
chk('기업당 1~2억원' in str(d[d['순위']==4].iloc[0]['지원내용_텍스트']),'4위 공고 금액')
chk(str(d[d['순위']==6].iloc[0]['규모'])=='지원규모 8,020백만원','6위 규모')
chk(str(d[d['순위']==10].iloc[0]['기관'])=='부산광역시((재)부산기술창업투자원)' and str(d[d['순위']==10].iloc[0]['규모'])=='내역예산 200백만원','10위 기관·규모')
chk(q(d[d['순위']==129].iloc[0][C],1)=='56.9' and str(d[d['순위']==129].iloc[0]['세부사업명'])=='국제수산교류협력','129위')
chk(int(t['참고2지표점수(0~100)'].idxmax())>=0 and q(t['참고2지표점수(0~100)'].max(),1)=='62.1','최고 환산점수 62.1')
chk(set(int(x) for x in t[t['참고2지표점수(0~100)'].round(1)==62.1]['순위'])=={6,8},'환산점수 62.1 = 6·8위')
chk(q(d[d['순위']==1].iloc[0]['참고2지표점수(0~100)'],1)=='60.0','1위 환산점수 60.0')
tp=bs[bs['기관'].astype(str).str.contains('부산테크노파크')]
alltp=d[d['기관'].astype(str).str.contains('부산테크노파크')]
chk(len(alltp)==28, f'부산테크노파크 수행 28건 (실제 {len(alltp)})')
chk(int(alltp['순위'].min())==29 and q(alltp[alltp['순위']==29].iloc[0][C],1)=='58.8','테크노파크 최고 29위 58.8')
chk((t['기관'].astype(str).str.contains('부산테크노파크')).sum()==0,'후보 20개에 테크노파크 0건')
# 기능별
f={sh.split()[0]:xl.parse(sh) for sh in SHEETS[1:]}
for k,(mm,ss,mx,p99,lr,nxt,sg,cnt) in {
  '기능1':('54.5','3.1','63.3','61.3627',13,'61.26','60.78',22),
  '기능2':('50.1','2.4','57.5','55.5590',13,'55.48','54.95',25)}.items():
    d2=f[k]; m2,s2=d2[C].mean(),d2[C].std(ddof=0); p2=np.percentile(d2[C],99)
    chk(q(m2,1)==mm and q(s2,1)==ss and q(d2[C].max(),1)==mx, f'{k} 평균/σ/최대')
    chk(q(p2,4)==p99 and int(d2[d2[C]>=p2]['순위'].max())==lr, f'{k} p99 경계')
    chk(q(d2[d2['순위']==lr+1].iloc[0][C])==nxt, f'{k} {lr+1}위 {nxt}')
    chk(q(m2+2*s2)==sg and (d2[C]>m2+2*s2).sum()==cnt, f'{k} 2σ {sg} 초과 {cnt}')
f1=f['기능1']; v1=f1[C].head(21).tolist(); g1=[float(q(v1[i]-v1[i+1])) for i in range(20)]
chk(g1[0]==0.72 and max(g1[1:])<=0.31, f'기능1 1→2 0.72, 이후 0.31 이하 (실제 {g1[0]}, {max(g1[1:])})')
chk(dict(f1.head(20)['부처'].value_counts())=={'중소벤처기업부':10,'과학기술정보통신부':5,'부산':2,'해양수산부':2,'기후에너지환경부':1}, f"기능1 부처 {dict(f1.head(20)['부처'].value_counts())}")
chk(f1.head(20)['세부사업명'].nunique()==17, f"기능1 세부사업 17 (실제 {f1.head(20)['세부사업명'].nunique()})")
for a,lo,hi in [('사업목적','0.60','0.67'),('지원내용','0.62','0.74'),('지원대상','0.51','0.61'),('전달체계','0.53','0.67')]:
    chk(q(f1.head(20)[a+'_유사도'].min())==lo and q(f1.head(20)[a+'_유사도'].max())==hi, f'기능1 {a} 범위 {lo}~{hi}')
for a,val,rk in [('지원내용','0.7541',56),('지원대상','0.6098',11),('사업목적','0.6801',84),('전달체계','0.7075',399)]:
    r=f1.loc[f1[a+'_유사도'].idxmax()]
    chk(q(r[a+'_유사도'],4)==val and int(r['순위'])==rk, f'기능1 {a} pool max {rk}위 {val} (실제 {int(r["순위"])}위 {q(r[a+"_유사도"],4)})')
chk(str(f1[f1['순위']==2].iloc[0]['규모'])=='내역예산 3,050백만원','기능1 2위 규모')
f2=f['기능2']; v2=f2[C].head(21).tolist(); g2=[float(q(v2[i]-v2[i+1])) for i in range(20)]
chk(g2[0]==0.02 and g2[1]==0.00 and g2[2]==0.82, f'기능2 간격 0.02/0.00/0.82 (실제 {g2[:3]})')
chk(max(g2)==0.82,'기능2 최대 간격 0.82')
chk(dict(f2.head(20)['부처'].value_counts())=={'산업통상부':10,'중소벤처기업부':5,'과학기술정보통신부':2,'기후에너지환경부':2,'국토교통부':1}, f"기능2 부처 {dict(f2.head(20)['부처'].value_counts())}")
chk(f2.head(20)['세부사업명'].nunique()==15, f"기능2 세부사업 15 (실제 {f2.head(20)['세부사업명'].nunique()})")
for a,lo,hi in [('사업목적','0.54','0.65'),('지원내용','0.55','0.63'),('지원대상','0.44','0.56'),('전달체계','0.51','0.56')]:
    chk(q(f2.head(20)[a+'_유사도'].min())==lo and q(f2.head(20)[a+'_유사도'].max())==hi, f'기능2 {a} 범위 {lo}~{hi}')
for a,val,rk in [('사업목적','0.6521',54),('지원내용','0.6313',19),('지원대상','0.5638',12),('전달체계','0.6951',169)]:
    r=f2.loc[f2[a+'_유사도'].idxmax()]
    chk(q(r[a+'_유사도'],4)==val and int(r['순위'])==rk, f'기능2 {a} pool max {rk}위 {val}')
chk(all('거점기관 개방형혁신' in str(f2[f2['순위']==n].iloc[0]['내역사업명']) for n in (1,2,3)),'기능2 1~3위 거점기관 개방형혁신')
# 키워드
alltxt=d[[a+'_텍스트' for a in AX]].astype(str).agg(' '.join,axis=1)
for kw,n in [('북극항로',0),('북극',1),('극지',1),('조선기자재',0),('해양ICT',0),('해운',5),('항만',8),('국제협력',21),('네트워크',80),('시제품',96)]:
    got=int(alltxt.str.contains(kw,regex=False).sum()); chk(got==n, f"'{kw}' {n}건 (실제 {got})")
chk(int(d[alltxt.str.contains('북극',regex=False)]['순위'].iloc[0])==5,"'북극' 1건 = 5위")
chk(int(d[alltxt.str.contains('극지',regex=False)]['순위'].iloc[0])==493,"'극지' 1건 = 493위")
chk(len(xl.parse('공고매핑'))==733,'공고매핑 733행')
chk(250000+140000+80000+30000==500000,'산출내역 합 500,000천원')
chk(q(250000/500000*100,0)=='50' and q(140000/500000*100,0)=='28' and q((80000+30000)/500000*100,0)=='22','비목 비율 50/28/22')
chk(q(250000/20,0)=='12500','기업당 평균 12,500천원')
chk(q(140000/2,0)=='70000','협력사업 건당 70,000천원')
# 그림
spec=json.load(open('figspec.json',encoding='utf-8')); fig=json.dumps(spec,ensure_ascii=False)
chk(list(spec['행주석'].keys())==[str(x) for x in d.head(8)['공고이름']],'그림 행주석 키')
chk('0.6277' in fig and '59.8838' in fig,'그림 핵심 수치')
pool=set()
for sh in SHEETS:
    dd=xl.parse(sh)
    for a in AX: pool|={q(x,4) for x in dd[a+'_유사도']}|{q(x,2) for x in dd[a+'_유사도']}
    pool|={q(x,1) for x in dd[C]}|{q(x,2) for x in dd[C]}|{q(x,4) for x in dd[C]}|{q(x,1) for x in dd['참고2지표점수(0~100)']}
for src,tag in [(md,'수치'),(fig,'그림')]:
    for tok in sorted(set(re.findall(r'(?<![\d.])0\.\d{4}',src))):
        if tok not in pool: fail.append(f'[{tag}] {tok} 가 산출결과에 없음')
print('\n'.join(fail) if fail else '검증 통과: 불일치 0건'); print(f'총 {len(fail)}건 불일치')
sys.exit(1 if fail else 0)
