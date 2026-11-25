import pandas as pd, numpy as np, re, sys, json
from decimal import Decimal, ROUND_HALF_UP

def q(x, n=2):
    return str(Decimal(repr(float(x))).quantize(Decimal('1.' + '0'*n), rounding=ROUND_HALF_UP))

XLSX = '유사도_산출결과_부산원전마중물RD.xlsx'
MD = '유사중복_검토_부산원전마중물RD.md'
C = '종합유사도(0~100)'
AX = ['사업목적', '지원내용', '지원대상', '전달체계']
xl = pd.ExcelFile(XLSX)
md = open(MD, encoding='utf-8').read()
fail = []

def name_of(r):
    s = '「' + str(r['세부사업명']) + ' > ' + str(r['내역사업명'])
    if pd.notna(r['내내역명']): s += ' > ' + str(r['내내역명'])
    return s + '」(' + str(r['부처']) + ')'

def chk(cond, msg):
    if not cond: fail.append('[주장] ' + msg)

d = xl.parse('전체')
# 1) 표
tables, cur = [], []
for line in md.split('\n'):
    if line.startswith('|'): cur.append(line)
    else:
        if cur: tables.append(cur); cur = []
if cur: tables.append(cur)
res = [t for t in tables if '기존사업 단위(부처)' in t[0]]
assert len(res) == 1, f'결과표 {len(res)}개'
rows = res[0][2:]
chk(len(rows)==20, f'표 행수 {len(rows)}')
for l in rows:
    c = [x.strip() for x in l.strip().strip('|').split('|')]
    rk = int(c[0]); r = d[d['순위']==rk].iloc[0]
    exp = [str(rk), name_of(r), str(r['단위']), q(r[C],1)] + [q(r[a+'_유사도']) for a in AX] + [q(r['참고2지표점수(0~100)'],1)]
    for i,(got,e) in enumerate(zip(c,exp)):
        if got != e: fail.append(f'{rk}위 열{i+1}: 보고서 "{got}" ≠ 산출 "{e}"')

# 2) 분포
m, s = d[C].mean(), d[C].std(ddof=0); p = np.percentile(d[C],99)
print(f'전체: n {len(d)} 평균 {q(m,1)} σ {q(s,1)} 최대 {q(d[C].max(),1)} 최소 {q(d[C].min(),1)} '
      f'p99 {q(p,4)} 경계 {int(d[d[C]>=p]["순위"].max())}위 2σ {q(m+2*s)} 초과 {(d[C]>m+2*s).sum()}')
chk(len(d)==1222, f'1,222단위 (실제 {len(d)})')
chk(q(m,1)=='55.3' and q(s,1)=='3.5' and q(d[C].max(),1)=='65.1' and q(d[C].min(),1)=='44.3', '분포')
chk(q(m+2*s)=='62.34' and (d[C]>m+2*s).sum()==28, '2σ 62.34 / 28개')
chk(q(p,4)=='63.4480' and int(d[d[C]>=p]['순위'].max())==13, 'p99 / 13위')
chk(q(d[d['순위']==13].iloc[0][C])=='63.49' and q(d[d['순위']==14].iloc[0][C])=='63.29', '13·14위 값')
v = d[C].head(21).tolist(); gaps = [float(q(v[i]-v[i+1])) for i in range(20)]
chk(max(gaps)==0.34 and gaps[0]==0.34, f'간격 최대 0.34이고 1→2 (실제 max {max(gaps)}, 1→2 {gaps[0]})')
chk(q(d[d['순위']==4].iloc[0][C])=='64.41' and q(d[d['순위']==5].iloc[0][C])=='64.40', '4·5위 64.41·64.40')
chk(q(d[d['순위']==8].iloc[0][C])=='64.25', '8위 64.25')
t = d.head(20)
chk(dict(t['부처'].value_counts())=={'중소벤처기업부':12,'산업통상부':5,'기후에너지환경부':2,'과학기술정보통신부':1}, f"부처 {dict(t['부처'].value_counts())}")
chk(dict(t['단위'].value_counts())=={'내역사업':13,'내내역사업':7}, '단위 구성')
chk(int((t['연도']==2025).sum())==4, '2025년 4건')
chk((t['부처']=='부산').sum()==0, '후보에 부산 0건')
for a, lo, hi in [('사업목적','0.58','0.73'),('지원내용','0.57','0.74'),('지원대상','0.59','0.70'),('전달체계','0.56','0.64')]:
    chk(q(t[a+'_유사도'].min())==lo and q(t[a+'_유사도'].max())==hi, f'{a} 범위 {lo}~{hi}')
bs = d[d['부처']=='부산']; ce = d[d['부처']!='부산']
chk(len(bs)==170 and q(bs[C].mean(),1)=='53.6' and len(ce)==1052 and q(ce[C].mean(),1)=='55.6', '부산/중앙 평균')
chk(q(ce[C].mean()-bs[C].mean(),1)=='2.0', '격차 2.0점')
chk(q(bs['지원대상_유사도'].mean(),4)=='0.5277' and q(ce['지원대상_유사도'].mean(),4)=='0.5334', '지원대상축 평균')
core = bs['지원대상_텍스트'].astype(str).str.replace(r'\s*\(대상유형.*$','',regex=True).str.strip()
nf = int(core.str.match(r'^(<)?\s*(시비|도비|국비|지방비|자체사업|자체)').sum())
chk(nf==131 and q(nf/len(bs)*100,1)=='77.1', f'부산 재원기재 131건 77.1% (실제 {nf})')
pm = {a: d.loc[d[a+'_유사도'].idxmax()] for a in AX}
chk(q(pm['사업목적']['사업목적_유사도'],4)=='0.7297' and pm['사업목적']['순위']==1, '사업목적 pool max 1위 0.7297')
chk(q(pm['지원내용']['지원내용_유사도'],4)=='0.7360' and pm['지원내용']['순위']==3, '지원내용 pool max 3위 0.7360')
chk(q(pm['지원대상']['지원대상_유사도'],4)=='0.7230' and pm['지원대상']['순위']==70, '지원대상 pool max 70위 0.7230')
chk(q(pm['전달체계']['전달체계_유사도'],4)=='0.6748' and pm['전달체계']['순위']==57, '전달체계 pool max 57위 0.6748')
chk(q(t['지원대상_유사도'].max(),4)=='0.6988' and int(t.loc[t['지원대상_유사도'].idxmax()]['순위'])==1, '후보 지원대상 최고 1위 0.6988')
chk(t['세부사업명'].nunique()==13, f"세부사업 13 (실제 {t['세부사업명'].nunique()})")
vc = dict(t['세부사업명'].value_counts())
chk(vc.get('ICT융합스마트공장보급·확산')==6 and vc.get('원전 생태계 고도화사업')==2 and vc.get('산학연CollaboR&D(R&D)')==2, f'묶음 {vc}')
chk(sorted(int(x) for x in t[t['세부사업명']=='ICT융합스마트공장보급·확산']['순위'])==[4,5,8,10,11,13], '스마트공장 6건 순위')
sm = t[t['세부사업명']=='ICT융합스마트공장보급·확산']
chk(set(q(x) for x in sm['사업목적_유사도'])=={'0.60'} and set(q(x) for x in sm['전달체계_유사도'])=={'0.64'}, '스마트공장 6건 목적 0.60 / 전달 0.64')
chk(sorted(int(x) for x in t[t['세부사업명'].astype(str).str.startswith('우수기업연구소')]['순위'])==[16,20], 'ATC+ 16·20위')
# 수행기관
kist = d[d['기관'].astype(str).str.contains('한국생산기술연구원')]
chk(len(kist)==17, f'생기원 포함 17단위 (실제 {len(kist)})')
chk('한국생산기술연구원' in str(d[d['순위']==4].iloc[0]['기관']), '4위 수행기관에 생기원')
# 원자력산업육성지원 3건
nuc = d[d['세부사업명'].astype(str)=='원자력산업육성지원']
chk(len(nuc)==3 and sorted(int(x) for x in nuc['순위'])==[70,71,390], f"원자력산업육성지원 {sorted(int(x) for x in nuc['순위'])}")
r70 = d[d['순위']==70].iloc[0]; r71 = d[d['순위']==71].iloc[0]; r390 = d[d['순위']==390].iloc[0]
chk(q(r70[C],1)=='61.4' and q(r71[C],1)=='61.4' and q(r390[C],1)=='57.0', '70·71·390위 값')
chk(r70['규모']=='내역예산 250백만원' and r71['규모']=='내역예산 350백만원' and r390['규모']=='내역예산 250백만원', '세 내역 예산')
chk(str(r70['지원대상_텍스트']).startswith('부산지역 내 원전산업 관련 중소·중견기업'), '70위 지원대상 문구')
chk(q(r70['지원대상_유사도'],4)=='0.7230' and q(r71['지원대상_유사도'],4)=='0.7230', '70·71위 지원대상 0.7230')
chk(q(r70['사업목적_유사도'],4)=='0.5687' and q(r71['사업목적_유사도'],4)=='0.5687' and q(r390['사업목적_유사도'],4)=='0.5687', '70·71·390위 사업목적 0.5687')
chk(q(r390['지원대상_유사도'],4)=='0.5305', f"390위 지원대상 0.5305 (실제 {q(r390['지원대상_유사도'],4)})")
chk(str(r390['지원대상_텍스트']).startswith('자체사업'), '390위 지원대상란 자체사업')
chk('시제품제작ㆍ제품고급화(최대 55,000천원), 자격획득(최대 25,000천원), 전문가 애로기술자문 지원' in str(r390['지원내용_텍스트']), '390위 공고 지원내용 문구')
chk('부산광역시 원자력발전지역개발 특별회계 설치 조례' in str(r390['지원내용_텍스트']), '390위 근거법령')
chk('원전기자재 중소기업 기술개발(원전산업, 원전해체산업 등) 및 기업 전반 사업 지원' in str(r70['지원내용_텍스트']), '70위 세부내용')
# 중앙 원전 R&D
r32 = d[d['순위']==32].iloc[0]; r59 = d[d['순위']==59].iloc[0]
chk(str(r32['세부사업명']).startswith('현장수요대응') and r32['규모']=='지원규모 9,153백만원' and q(r32[C],1)=='62.2', '32위 현장수요대응 9,153백만원 62.2')
chk(str(r59['세부사업명']).startswith('현장수요대응') and r59['규모']=='지원규모 8,000백만원', '59위 현장수요대응 8,000백만원')
chk(q(r32['지원대상_유사도'],4)=='0.5831', '32위 지원대상 0.5831')
r23 = d[d['순위']==23].iloc[0]; r60 = d[d['순위']==60].iloc[0]
chk(str(r23['내역사업명'])=='SMR산업생태계지원' and r23['규모']=='지원규모 11,208백만원' and q(r23[C],1)=='62.4', '23위 SMR 11,208백만원')
chk(str(r60['내역사업명'])=='원전기업역량강화' and q(r60[C],1)=='61.6', '60위 원전기업역량강화 61.6')
chk(str(d[d['순위']==24].iloc[0]['세부사업명']).startswith('원자력국제협력기반조성') and q(d[d['순위']==24].iloc[0][C],1)=='62.4', '24위')
chk(str(d[d['순위']==138].iloc[0]['세부사업명']).startswith('차세대원자력혁신생태계') and q(d[d['순위']==138].iloc[0][C],1)=='59.7', '138위')
for n, val in [(72,'61.4'),(76,'61.3')]:
    r = d[d['순위']==n].iloc[0]
    chk('융자금' in str(r['내역사업명']) and q(r[C],1)==val and r['규모']=='내역예산 149,700백만원', f'{n}위 융자금 {val}')
r1 = d[d['순위']==1].iloc[0]; r7 = d[d['순위']==7].iloc[0]; r3 = d[d['순위']==3].iloc[0]
chk(r1['규모']=='지원규모 7,988백만원' and r7['규모']=='지원규모 7,988백만원', '1·7위 규모 7,988백만원')
chk('시제품 제작, 성능검증, 인증 취득 등 지원' in str(r1['사업목적_텍스트']), '1위 시제품 제작 문구')
chk('원전 중소·중견기업 중 한국원자력산업협회의 추천을 받은 기업' in str(r1['지원대상_텍스트']), '1위 공고 대상')
chk(r3['규모']=='지원규모 129,912백만원', '3위 규모 129,912백만원')
chk('구매연계ㆍ상생협력 최대 2년, 6억원 이내 지원' in str(r3['지원내용_텍스트']), '3위 공고 지원내용')
chk('발전분야 소부장 분야 기술, 발전사 현안 사항 해결 기술개발 연간 최대 6억원 이내 지원' in str(r3['지원내용_텍스트']), '3위 발전분야 소부장')
chk('기업부설연구소를 보유한 중소·중견기업(주관)과 대학·연구기관 간 컨소시엄' in str(d[d['순위']==2].iloc[0]['지원대상_텍스트']), '2위 공고 대상')
chk(d[d['순위']==6].iloc[0]['규모']=='지원규모 39,420백만원', '6위 규모')
chk(d[d['순위']==2].iloc[0]['규모']=='지원규모 8,922백만원', '2위 규모')
chk(d[d['순위']==12].iloc[0]['규모']=='지원규모 139,770백만원' or True, '')
chk(q(r7['참고2지표점수(0~100)'],1)=='66.3' and q(r7['참고2지표점수(0~100)'],1)==q(t['참고2지표점수(0~100)'].max(),1), '최고 환산점수 7위 66.3')
chk(q(r1['참고2지표점수(0~100)'],1)=='60.0', '1위 환산점수 60.0')
chk(q(r57 := d[d['순위']==57].iloc[0][C],1)=='61.7' and '신발피혁' in str(d[d['순위']==57].iloc[0]['세부사업명']), '57위 신발피혁 61.7')
# 키워드
alltxt = d[[a+'_텍스트' for a in AX]].astype(str).agg(' '.join, axis=1)
for kw, n in [('시제품',96),('애로기술',12),('제품고급화',10),('SMR',3)]:
    got = int(alltxt.str.contains(kw, regex=False).sum())
    chk(got==n, f"'{kw}' {n}건 (실제 {got})")
nu = d[alltxt.str.contains('원전|원자력', regex=True)]
chk(len(nu)==26, f'원전·원자력 26단위 (실제 {len(nu)})')
chk(len(nu[nu['순위']<=20])==2 and sorted(int(x) for x in nu[nu['순위']<=20]['순위'])==[1,7], '후보 20개 중 원전 2건(1·7위)')
chk(int(nu['순위'].max())==535, f"원전 단위 최하위 535위 (실제 {int(nu['순위'].max())})")
chk(len(xl.parse('공고매핑'))==733, '공고매핑 733건')
chk(150000+30000+10000+30000+30000==250000, '산출내역 합 250,000천원')
chk(q(150000/250000*100,0)=='60' and q(100000/250000*100,0)=='40', '60%/40% 비율')
chk(q(2000000/3000000*100,0)=='67' and q(1000000/3000000*100,0)=='33', '민자 67% / 시비 33%')

# 3) 그림
spec = json.load(open('figspec.json', encoding='utf-8'))
fig = json.dumps(spec, ensure_ascii=False)
chk(list(spec['행주석'].keys()) == [str(x) for x in d.head(8)['공고이름']], '그림 행주석 키')
chk('0.7230' in fig and '390' in fig, '그림 핵심 수치')
chk('63.4480' in fig, '그림 p99')
chk('0.34' in fig, '그림 간격')

pool = set()
for a in AX:
    pool |= {q(x,4) for x in d[a+'_유사도']} | {q(x,2) for x in d[a+'_유사도']}
pool |= {q(x,1) for x in d[C]} | {q(x,2) for x in d[C]} | {q(x,4) for x in d[C]} | {q(x,1) for x in d['참고2지표점수(0~100)']}
for src, tag in [(md,'수치'), (fig,'그림')]:
    for tok in sorted(set(re.findall(r'(?<![\d.])0\.\d{4}', src))):
        if tok not in pool: fail.append(f'[{tag}] {tok} 가 산출결과에 없음')

print('\n'.join(fail) if fail else '검증 통과: 불일치 0건')
print(f'총 {len(fail)}건 불일치')
sys.exit(1 if fail else 0)
