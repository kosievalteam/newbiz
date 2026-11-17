# -*- coding: utf-8 -*-
"""보고서(md)·그림 spec/rows·산출 xlsx의 모든 수치를 direct_compare 원산출값과 대조한다. 반올림은 사사오입."""
import json, re, sys, hashlib
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
AX=['사업목적','지원내용','지원대상','전달체계']
RAW_W={"사업목적":20,"지원내용":30,"지원대상":30,"전달체계":15}
W={k:v/sum(RAW_W.values())*100 for k,v in RAW_W.items()}
PAIRS=[("276","277"),("276","278"),("276","0279"),("277","278"),("277","0279"),("278","0279")]
SH={"276":"2026-276","277":"2026-277","278":"2026-278","0279":"2026-0279"}
def q(x,n): return float(Decimal(repr(float(x))).quantize(Decimal('1.'+'0'*n),rounding=ROUND_HALF_UP))
R={(a,b):{(r["A단위"],r["B단위"]):r for r in json.load(open(f"직접비교_2026-{a}_2026-{b}.json",encoding="utf-8"))["rows"]} for a,b in PAIRS}
MD=open('경상북도_신규사업4건_유사중복_직접비교_검토보고서.md',encoding='utf-8').read()
spec=json.load(open('figspec.json',encoding='utf-8')); frows=json.load(open('figrows.json',encoding='utf-8'))
xl=pd.ExcelFile('경상북도_신규사업4건_유사도_직접비교.xlsx')
ok=fail=0
def chk(n,c,g=''):
    global ok,fail
    if c: ok+=1
    else: fail+=1; print(f'  FAIL {n} :: {g}')

# 1) 원산출 무결성
chk('6쌍 로드',len(R)==6)
for (a,b),d in R.items(): chk(f'{a}x{b} 9조합',len(d)==9,len(d))
chk('총 54조합',sum(len(d) for d in R.values())==54)
for (a,b) in PAIRS:
    c=json.load(open(f"직접비교_2026-{a}_2026-{b}.json",encoding="utf-8"))
    chk(f'{a}x{b} 가중치',c['raw_weights']==RAW_W,c['raw_weights'])
    chk(f'{a}x{b} 모델',c['model']=='BAAI/bge-m3')
    chk(f'{a}x{b} 정규화가중치',{k:round(v,2) for k,v in W.items()}==c['weights'],c['weights'])
    for k,r in R[(a,b)].items():
        tot=sum(r[ax+'_유사도']*W[ax] for ax in AX)
        chk(f'{a}x{b} {k} 산식재현',abs(tot-r['종합유사도(0~100)'])<0.011,f'{tot} vs {r["종합유사도(0~100)"]}')  # 축 4dp·종합 2dp 저장 반올림 허용폭

# 2) 대칭성
fwd=R[("276","0279")]
rev={(r["A단위"],r["B단위"]):r for r in json.load(open('대칭성검증_0279_276.json',encoding='utf-8'))["rows"]}
mx=0
for (a,b),r in fwd.items():
    s=rev[(b,a)]; mx=max(mx,abs(r['종합유사도(0~100)']-s['종합유사도(0~100)']),*[abs(r[ax+'_유사도']-s[ax+'_유사도']) for ax in AX])
chk('대칭성 전치 최대차 0',mx==0.0,mx)
chk('비교쌍 수 6 = 4C2',len(PAIRS)==6)

# 3) md 표 — 전체×전체 6행
rows=re.findall(r'^\| (\d) \| (2026-\S+ ↔ 2026-\S+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|$',MD,re.M)
chk('md 전체유사도 표 6행',len(rows)==6,len(rows))
order=sorted(PAIRS,key=lambda p:-R[p][("전체","전체")]['종합유사도(0~100)'])
for i,g in enumerate(rows):
    a,b=order[i]; r=R[(a,b)][("전체","전체")]
    chk(f'md {i+1}위 쌍',g[1]==f'{SH[a]} ↔ {SH[b]}',g[1])
    chk(f'md {i+1}위 종합',float(g[2])==q(r['종합유사도(0~100)'],2),f'{g[2]} vs {q(r["종합유사도(0~100)"],2)}')
    for j,ax in enumerate(AX):
        chk(f'md {i+1}위 {ax}',float(g[3+j])==q(r[ax+'_유사도'],4),f'{g[3+j]} vs {q(r[ax+"_유사도"],4)}')
# 매트릭스
mrow=re.findall(r'^\| \*\*(2026-\S+)\*\* \| (\S+) \| (\S+) \| (\S+) \| (\S+) \|$',MD,re.M)
chk('md 매트릭스 4행',len(mrow)==4,len(mrow))
codes=["276","277","278","0279"]
for g in mrow:
    i=[SH[c] for c in codes].index(g[0])
    for j,c in enumerate(codes):
        v=g[1+j]
        if i==j: chk(f'매트릭스 대각 {g[0]}',v=='—',v)
        else:
            k=(codes[i],c) if (codes[i],c) in R else (c,codes[i])
            chk(f'매트릭스 {g[0]}x{SH[c]}',float(v)==q(R[k][("전체","전체")]['종합유사도(0~100)'],2),v)

# 4) md 축별 표
p=pd.DataFrame({f'{SH[a]} ↔ {SH[b]}':{ax:R[(a,b)][("전체","전체")][ax+'_유사도'] for ax in AX} for a,b in PAIRS}).T
arow=re.findall(r'^\| (사업목적|지원내용|지원대상|전달체계) \| (\d+) \| ([\d.]+) \| ([\d.]+) ~ ([\d.]+) \| ([\d.]+) \| ([^|]+) \| ([^|]+) \|$',MD,re.M)
chk('md 축별 표 4행',len(arow)==4,len(arow))
for g in arow:
    ax=g[0]; s=p[ax]
    chk(f'축 {ax} 원가중치',int(g[1])==RAW_W[ax])
    chk(f'축 {ax} 정규화',float(g[2])==q(W[ax],2))
    chk(f'축 {ax} 범위',float(g[3])==q(s.min(),4) and float(g[4])==q(s.max(),4),f'{g[3]}~{g[4]} vs {q(s.min(),4)}~{q(s.max(),4)}')
    chk(f'축 {ax} 평균',float(g[5])==q(s.mean(),4),f'{g[5]} vs {q(s.mean(),4)}')
    mxp=s.idxmax().replace('2026-','').replace(' ↔ ',' ↔ '); mnp=s.idxmin().replace('2026-','')
    chk(f'축 {ax} 최대쌍',g[6].strip()==mxp,f'{g[6]} vs {mxp}')
    chk(f'축 {ax} 최소쌍',g[7].strip()==mnp,f'{g[7]} vs {mnp}')
# 기여율
contr={ax:sum(R[pp][("전체","전체")][ax+'_유사도']*W[ax]/R[pp][("전체","전체")]['종합유사도(0~100)']*100 for pp in PAIRS)/6 for ax in AX}
for ax,v in [('지원대상',34.5),('지원내용',27.4),('사업목적',20.4),('전달체계',17.7)]:
    chk(f'기여율 {ax} {v}',q(contr[ax],1)==v,q(contr[ax],1))

# 5) md 기능 교차 표 (전체쌍 상회 6개)
up=[]
for a,b in PAIRS:
    base=R[(a,b)][("전체","전체")]['종합유사도(0~100)']
    for (ua,ub),r in R[(a,b)].items():
        if r['종합유사도(0~100)']-base>0: up.append((a,b,ua,ub,r,r['종합유사도(0~100)']-base))
up.sort(key=lambda z:-z[5])
chk('전체쌍 상회 6개',len(up)==6,len(up))
crow=re.findall(r'^\| (2026-\S+ ↔ 2026-\S+) \| (기능\d[^|]*?) \| (기능\d[^|]*?) \| ([\d.]+) \| \*?\*?([+\d.]+)\*?\*? \| ([\d.]+) \| ([\d.]+) \|$',MD,re.M)
chk('md 교차 표 6행',len(crow)==6,len(crow))
for i,g in enumerate(crow):
    a,b,ua,ub,r,dl=up[i]
    chk(f'교차 {i} 쌍',g[0]==f'{SH[a]} ↔ {SH[b]}',g[0])
    chk(f'교차 {i} A단위',g[1].strip()==ua,f'{g[1]} vs {ua}')
    chk(f'교차 {i} B단위',g[2].strip()==ub,f'{g[2]} vs {ub}')
    chk(f'교차 {i} 종합',float(g[3])==q(r['종합유사도(0~100)'],2),g[3])
    chk(f'교차 {i} 증감',float(g[4])==q(dl,2),f'{g[4]} vs {q(dl,2)}')
    chk(f'교차 {i} 지원내용',float(g[5])==q(r['지원내용_유사도'],4),g[5])
    chk(f'교차 {i} 전달체계',float(g[6])==q(r['전달체계_유사도'],4),g[6])

# 6) 54조합 극값
allr=[(a,b,k,r) for (a,b),d in R.items() for k,r in d.items()]
mx_dae=max(allr,key=lambda z:z[3]['지원대상_유사도']); mx_jd=max(allr,key=lambda z:z[3]['전달체계_유사도'])
mn_nae=min(allr,key=lambda z:z[3]['지원내용_유사도'])
chk('대상축 54최대 0.9290 277x0279 전체',q(mx_dae[3]['지원대상_유사도'],4)==0.9290 and mx_dae[2]==("전체","전체") and (mx_dae[0],mx_dae[1])==("277","0279"))
chk('전달축 54최대 0.9774 276기능1x277기능1',q(mx_jd[3]['전달체계_유사도'],4)==0.9774 and (mx_jd[0],mx_jd[1])==("276","277") and mx_jd[2][0].startswith('기능1'))
chk('내용축 54최소 0.5637',q(mn_nae[3]['지원내용_유사도'],4)==0.5637,q(mn_nae[3]['지원내용_유사도'],4))
chk('276기능1x277기능1 85.42',q(R[("276","277")][("기능1 사업화자금(시제품·인증)","기능1 제품 경쟁력·생산능력(시제품)")]['종합유사도(0~100)'],2)==85.42)
chk('그 조합 전체쌍 대비 -2.02',q(R[("276","277")][("기능1 사업화자금(시제품·인증)","기능1 제품 경쟁력·생산능력(시제품)")]['종합유사도(0~100)']-R[("276","277")][("전체","전체")]['종합유사도(0~100)'],2)==-2.02)
for a,b in [("276","277"),("276","278")]:
    base=R[(a,b)][("전체","전체")]['종합유사도(0~100)']
    chk(f'{a}x{b} 9조합 모두 전체쌍 이하',all(r['종합유사도(0~100)']<=base for r in R[(a,b)].values()))
vals=[R[p][("전체","전체")]['종합유사도(0~100)'] for p in PAIRS]
chk('6쌍 범위 74.34~87.44',q(min(vals),2)==74.34 and q(max(vals),2)==87.44)
chk('6쌍 평균 80.38',q(sum(vals)/6,2)==80.38,q(sum(vals)/6,2))

# 7) figrows / figspec
chk('figrows 6행',len(frows['rows'])==6)
for k,v in frows['rows'].items():
    a,b=[c for c in ["276","277","278","0279"] if SH[c] in k][:2]
    chk(f'figrows {k}',v==q(R[(a,b)][("전체","전체")]['종합유사도(0~100)'],2),v)
chk('figrows stats n6',frows['stats']['n']==6)
chk('figrows mean',q(frows['stats']['mean'],2)==80.38)
chk('figrows top',frows['stats']['top']=='2026-276 ↔ 2026-277' and frows['stats']['topv']==87.44)
chk('figspec 행주석 6',len(spec['행주석'])==6)
for k in spec['행주석']: chk(f'figspec 키 {k}',k in frows['rows'],k)
chk('figspec 축범위',spec['축최소']<=min(frows['rows'].values()) and spec['축최대']>=max(frows['rows'].values()))

# 8) xlsx
sn=xl.sheet_names
for s in ['종합비교표','종합비교표_매트릭스','전체_직접유사도','분석축별_유사도','기능별_교차유사도','원문_비교근거','지원조건_비교','실질적_중복검토','검증_로그']:
    chk(f'시트 {s}',s in sn,sn)
chk('기능별_교차유사도 54행',len(xl.parse('기능별_교차유사도'))==54)
chk('분석축별_유사도 24행',len(xl.parse('분석축별_유사도'))==24)
chk('원문_비교근거 48행',len(xl.parse('원문_비교근거'))==48)
chk('종합비교표 6행',len(xl.parse('종합비교표'))==6)
cr=xl.parse('기능별_교차유사도')
for _,r in cr.iterrows():
    a,b=[c for c in ["276","277","278","0279"] if SH[c] in r['비교쌍']][:2]
    src=R[(a,b)][(r['A 단위'],r['B 단위'])]
    chk(f'xlsx {r["비교쌍"]} {r["A 단위"][:8]}x{r["B 단위"][:8]}',r['종합 유사도(0~100)']==q(src['종합유사도(0~100)'],2))
# 원문_비교근거: 프로필 축 서술과 일치
PR={c:json.load(open(f'../case{n}/profile.json',encoding='utf-8')) for c,n in [("276",36),("277",37),("278",38),("0279",39)]}
sr=xl.parse('원문_비교근거')
for _,r in sr.iterrows():
    c=[k for k in PR if SH[k] in r['사업']][0]
    chk(f'원문 {SH[c]} {r["단위"][:8]} {r["분석축"]}',r['임베딩에 투입한 축 서술(원자료 기반)']==PR[c]['units'][r['단위']][r['분석축']])

# 9) 원본 md5
U='/root/.claude/uploads/48a7be44-e66a-585f-9512-c54081407b97/'
def m(f): return hashlib.md5(open(U+f,'rb').read()).hexdigest()
chk('276 md5 동일',m('8c177df5-2026_276_________________________.hwpx')==m('4c94e312-2026_276_________________________.hwpx'))
chk('278 md5 동일',m('9a3416e2-2026-278________________________.hwpx')==m('48e71179-2026-278________________________.hwpx'))
chk('0279 md5 동일',m('b0a7bd32-2026-0279___________________________.hwpx')==m('bbf98ed2-2026-0279___________________________.hwpx'))
chk('277 md5 상이',m('3cab2ec6-2026-277______________________.hwpx')!=m('c13bef1d-2026-277______________________.hwpx'))
chk('277 본문 591행 동일',open('raw/new277.txt',encoding='utf-8').read()==open('../case37/raw/text.txt',encoding='utf-8').read())
chk('md5 조각 일치',all(x in MD for x in ['215a9e8d','f9365db8','fa53aadb','49ae8afa','51ab3910']))

# 10) md 포함 문자열
for frag in ['6개 사업쌍','54개','4C2','최대 절대차 0','21.05','31.58','15.79','BAAI/bge-m3','591행',
             '0.00477','0.00364','0.00324','71.95','71.29','67.77','67.29','80.38','74.34','87.44',
             '0.9290','0.9774','0.5637','0.8762','0.6993','34.5%','27.4%','20.4%','17.7%',
             '+2.32','+1.80','85.42','2.02점','280백만원','200·250·250·200백만원','미산출']:
    chk(f'md "{frag}"',frag in MD,frag)
print(f'\n검증 {ok}/{ok+fail} 통과'+('' if fail==0 else f' — 실패 {fail}건'))
sys.exit(1 if fail else 0)
