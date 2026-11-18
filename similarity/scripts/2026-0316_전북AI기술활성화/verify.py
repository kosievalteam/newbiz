import pandas as pd, numpy as np, re, sys
from decimal import Decimal, ROUND_HALF_UP

def q(x, n=2):
    return str(Decimal(repr(float(x))).quantize(Decimal('1.' + '0'*n), rounding=ROUND_HALF_UP))

XLSX = '유사도_산출결과_전북AI기술활성화.xlsx'
MD = '유사중복_검토_전북AI기술활성화.md'
C = '종합유사도(0~100)'
AX = ['사업목적', '지원내용', '지원대상', '전달체계']
SHEETS = ['전체', '기능1 AI전환지원(수요 발굴·진단·기획)', '기능2 AI솔루션 개발·고도화',
          '기능3 AI공급기업 등록 지원', '기능4 현장실증·확산']
xl = pd.ExcelFile(XLSX)
md = open(MD, encoding='utf-8').read()
fail = []

def name_of(r):
    s = '「' + str(r['세부사업명']) + ' > ' + str(r['내역사업명'])
    if pd.notna(r['내내역명']):
        s += ' > ' + str(r['내내역명'])
    return s + '」(' + str(r['부처']) + ')'

# ---- 1) 표 행 전수 검증 ----
tables = []
cur = []
for line in md.split('\n'):
    if line.startswith('|'):
        cur.append(line)
    else:
        if cur:
            tables.append(cur); cur = []
if cur: tables.append(cur)
res_tables = [t for t in tables if '기존사업 단위(부처)' in t[0]]
assert len(res_tables) == 5, f'결과표 개수 {len(res_tables)}'
for sh, tb in zip(SHEETS, res_tables):
    d = xl.parse(sh)
    rows = [l for l in tb[2:]]
    if len(rows) != 20:
        fail.append(f'[{sh}] 표 행수 {len(rows)}')
    for l in rows:
        c = [x.strip() for x in l.strip().strip('|').split('|')]
        rk = int(c[0])
        r = d[d['순위'] == rk].iloc[0]
        exp = [str(rk), name_of(r), str(r['단위']), q(r[C], 1)] + [q(r[a + '_유사도']) for a in AX] + [q(r['참고2지표점수(0~100)'], 1)]
        for i, (got, e) in enumerate(zip(c, exp)):
            if got != e:
                fail.append(f'[{sh}] {rk}위 열{i+1}: 보고서 "{got}" ≠ 산출 "{e}"')

# ---- 2) 분포·수치 주장 검증 ----
def chk(cond, msg):
    if not cond: fail.append('[주장] ' + msg)

for sh in SHEETS:
    d = xl.parse(sh); m = d[C].mean(); s = d[C].std(ddof=0); p = np.percentile(d[C], 99)
    lastr = int(d[d[C] >= p]['순위'].max())
    key = '전체' if sh == '전체' else sh.split()[0]
    print(f'{key}: 평균 {q(m,1)} σ {q(s,1)} 최대 {q(d[C].max(),1)} 최소 {q(d[C].min(),1)} '
          f'p99 {q(p,4)} 경계 {lastr}위({q(d[d["순위"]==lastr].iloc[0][C])}) '
          f'다음 {lastr+1}위({q(d[d["순위"]==lastr+1].iloc[0][C])}) 2σ {q(m+2*s)} 초과 {(d[C]>m+2*s).sum()}')

d = xl.parse('전체')
m, s = d[C].mean(), d[C].std(ddof=0)
chk(q(m,1)=='53.7' and q(s,1)=='3.9' and q(d[C].max(),1)=='68.4' and q(d[C].min(),1)=='41.6', '전체 분포')
chk(q(m+2*s)=='61.63' and (d[C]>m+2*s).sum()==45, '전체 2σ')
p = np.percentile(d[C],99)
chk(q(p,4)=='63.5700' and int(d[d[C]>=p]['순위'].max())==14, '전체 p99/경계')
chk(q(d[d['순위']==13].iloc[0][C],4)==q(d[d['순위']==14].iloc[0][C],4)=='63.5700', '13·14위 동값')
chk(q(d[d['순위']==15].iloc[0][C])=='63.39', '15위 63.39')
v = d[C].head(7).tolist()
chk(q(v[0]-v[1])=='0.30' and q(v[1]-v[2])=='1.56' and q(v[2]-v[3])=='0.06'
    and q(v[3]-v[4])=='1.17' and q(v[4]-v[5])=='0.02', '전체 상위 간격')
chk(q(d[d['순위']==3].iloc[0][C])=='66.53' and q(d[d['순위']==4].iloc[0][C])=='66.47', '3·4위 값')
chk(q(d[d['순위']==5].iloc[0][C])=='65.30' and q(d[d['순위']==6].iloc[0][C])=='65.28', '5·6위 값')
t = d.head(20)
chk(dict(t['부처'].value_counts())=={'과학기술정보통신부':9,'중소벤처기업부':5,'산업통상부':4,'전북':1,'농림축산식품부':1}, '전체 후보 부처 구성')
chk(dict(t['단위'].value_counts())=={'내역사업':14,'내내역사업':6}, '전체 후보 단위 구성')
chk(set(t['연도'])=={2026}, '전체 후보 전부 2026')
for a, lo, hi in [('사업목적','0.58','0.73'),('지원내용','0.66','0.76'),('지원대상','0.46','0.66'),('전달체계','0.55','0.77')]:
    chk(q(t[a+'_유사도'].min())==lo and q(t[a+'_유사도'].max())==hi, f'전체 후보 {a} 범위 {lo}~{hi}')
jb = d[d['부처']=='전북']; ce = d[d['부처']!='전북']
chk(len(jb)==212 and q(jb[C].mean(),1)=='53.1' and len(ce)==1052 and q(ce[C].mean(),1)=='53.9', '전북/중앙 평균')
# 축 pool max
pm = {a: d.loc[d[a+'_유사도'].idxmax()] for a in AX}
chk(q(pm['사업목적']['사업목적_유사도'],4)=='0.7341' and pm['사업목적']['순위']==6, '사업목적 pool max 6위 0.7341')
chk(q(pm['지원내용']['지원내용_유사도'],4)=='0.7697' and pm['지원내용']['순위']==34 and pm['지원내용']['부처']=='해양수산부', '지원내용 pool max 34위 해수부 0.7697')
chk(q(pm['지원대상']['지원대상_유사도'],4)=='0.6639' and pm['지원대상']['순위']==4, '지원대상 pool max 4위 0.6639')
chk(q(pm['전달체계']['전달체계_유사도'],4)=='0.7852' and pm['전달체계']['순위']==69, '전달체계 pool max 69위 0.7852')
# 후보20 내 축 최고값 (2위/4위)
chk(t['지원내용_유사도'].idxmax()==t[t['순위']==2].index[0] and q(t['지원내용_유사도'].max(),4)=='0.7568', '후보20 지원내용 최고=2위 0.7568')
chk(t['지원대상_유사도'].idxmax()==t[t['순위']==4].index[0] and q(t['지원대상_유사도'].max(),4)=='0.6639', '후보20 지원대상 최고=4위 0.6639')
# 6위 / 76위 축값
r6 = d[d['순위']==6].iloc[0]
chk([q(r6[a+'_유사도'],4) for a in AX]==['0.7341','0.7381','0.4561','0.7673'], '6위 축값')
chk(q(r6[C],1)=='65.3' and r6['규모']=='내역예산 500백만원', '6위 65.3 / 500백만원')
r76 = d[d['순위']==76].iloc[0]
chk(str(r76['세부사업명']).startswith('융복합SW강소기업육성'), '76위가 융복합SW강소기업육성')
chk([q(r76[a+'_유사도'],4) for a in AX]==['0.6868','0.5890','0.5147','0.6866'], '76위 축값')
chk(q(r76[C],1)=='60.2' and r76['규모']=='내역예산 400백만원' and r76['기관']=='(재)전북테크노파크', '76위 60.2 / 400백만원 / TP')
chk(r6['지원대상_텍스트'].startswith('도비 100%'), '6위 지원대상란 도비 100%')
chk(r76['지원대상_텍스트'].startswith('국비(지특) 50%, 도비 50%'), '76위 지원대상란 국비 50/도비 50')
# 전북 AI·SW 사업 위치
def find1(key):
    sub = d[d['세부사업명'].astype(str).str.contains(key, regex=False)]
    return sub
for key, ranks in [('AI빅데이터전문인력양성', [61,65]), ('지역 SW서비스 사업화', [69]), ('체감형홀로그램', [340])]:
    got = sorted(int(x) for x in find1(key)['순위'])
    chk(got == ranks, f'{key} 순위 {ranks} (실제 {got})')
chk(q(find1('지역 SW서비스 사업화').iloc[0][C],1)=='60.3', '69위 60.3')
chk([q(x,1) for x in find1('AI빅데이터전문인력양성')[C]]==['60.6','60.4'], '61·65위 60.6·60.4')
chk(q(find1('체감형홀로그램').iloc[0][C],1)=='56.1', '340위 56.1')
chk(q(find1('AI빅데이터전문인력양성').iloc[0]['지원대상_유사도'],4)=='0.4561', 'AI빅데이터 지원대상 0.4561')
chk(q(find1('지역 SW서비스 사업화').iloc[0]['지원대상_유사도'],4)=='0.5082', '지역SW 지원대상 0.5082')
chk([q(x,4) for x in find1('AI빅데이터전문인력양성')['전달체계_유사도']]==['0.7661','0.7593'], 'AI빅데이터 전달체계 0.7661/0.7593')
# 기능별 주장
f = {sh.split()[0]: xl.parse(sh) for sh in SHEETS[1:]}
for k, (mm, ss, mx, p99, lastr, nxt, sg, cnt) in {
    '기능1': ('52.6','3.2','66.0','60.7300',14,'60.70','58.96',37),
    '기능2': ('53.7','3.6','68.6','62.6803',13,'62.61','60.92',40),
    '기능3': ('51.3','3.2','65.5','59.9181',13,'59.87','57.70',35),
    '기능4': ('52.6','2.6','62.8','58.9144',13,'58.87','57.68',31)}.items():
    d2 = f[k]; m2, s2 = d2[C].mean(), d2[C].std(ddof=0); p2 = np.percentile(d2[C],99)
    chk(q(m2,1)==mm and q(s2,1)==ss and q(d2[C].max(),1)==mx, f'{k} 평균/σ/최대')
    chk(q(p2,4)==p99 and int(d2[d2[C]>=p2]['순위'].max())==lastr, f'{k} p99 경계 {lastr}위')
    chk(q(d2[d2['순위']==lastr+1].iloc[0][C])==nxt, f'{k} {lastr+1}위 {nxt}')
    chk(q(m2+2*s2)==sg and (d2[C]>m2+2*s2).sum()==cnt, f'{k} 2σ {sg} 초과 {cnt}')
# 기능1 13·14위 동값, 15위 60.70
d1 = f['기능1']
chk(q(d1[d1['순위']==13].iloc[0][C],4)==q(d1[d1['순위']==14].iloc[0][C],4)=='60.7300', '기능1 13·14위 동값')
v1 = d1[C].head(5).tolist(); chk(q(v1[2]-v1[3])=='1.47', '기능1 3→4 간격 1.47')
v2 = f['기능2'][C].head(3).tolist(); chk(q(v2[0]-v2[1])=='2.34', '기능2 1→2 간격 2.34')
v3 = f['기능3'][C].head(3).tolist(); chk(q(v3[0]-v3[1])=='1.54', '기능3 1→2 간격 1.54')
v4 = f['기능4'][C].head(4).tolist(); chk(q(v4[0]-v4[1])=='0.18' and q(v4[1]-v4[2])=='1.62', '기능4 1→2 0.18, 2→3 1.62')
# 기능별 부처 구성
chk(dict(f['기능1'].head(20)['부처'].value_counts())=={'과학기술정보통신부':13,'중소벤처기업부':3,'전북':1,'산업통상부':1,'식품의약품안전처':1,'농림축산식품부':1}, '기능1 부처')
chk(dict(f['기능2'].head(20)['부처'].value_counts())=={'과학기술정보통신부':14,'중소벤처기업부':4,'전북':1,'문화체육관광부':1}, '기능2 부처')
chk(dict(f['기능4'].head(20)['부처'].value_counts())=={'과학기술정보통신부':9,'산업통상부':6,'중소벤처기업부':3,'전북':1,'농림축산식품부':1}, '기능4 부처')
# 기능별 축 pool max 주장
for k, a, val, rk in [('기능1','사업목적','0.7321',8),('기능1','지원내용','0.6769',1),('기능1','지원대상','0.6492',3),('기능1','전달체계','0.7793',175),
                      ('기능2','지원내용','0.7418',1),('기능2','지원대상','0.6606',3),('기능2','전달체계','0.8194',236),
                      ('기능3','사업목적','0.7189',11),('기능3','지원내용','0.7235',1),('기능3','지원대상','0.5893',2),('기능3','전달체계','0.7965',51),
                      ('기능4','사업목적','0.6912',5),('기능4','지원내용','0.6665',12),('기능4','지원대상','0.6041',1),('기능4','전달체계','0.7905',5)]:
    d2 = f[k]; r = d2.loc[d2[a+'_유사도'].idxmax()]
    chk(q(r[a+'_유사도'],4)==val and int(r['순위'])==rk, f'{k} {a} pool max {rk}위 {val} (실제 {int(r["순위"])}위 {q(r[a+"_유사도"],4)})')
# 기능3 지원대상 범위
t3 = f['기능3'].head(20)
chk(q(t3['지원대상_유사도'].min())=='0.39' and q(t3['지원대상_유사도'].max())=='0.59', '기능3 후보 지원대상 범위 0.39~0.59')
# SW강소 기능별 순위
for k, rk in [('기능1',226),('기능2',228),('기능3',275),('기능4',246)]:
    r = f[k][f[k]['세부사업명'].astype(str).str.startswith('융복합SW')].iloc[0]
    chk(int(r['순위'])==rk, f'{k} SW강소 {rk}위 (실제 {int(r["순위"])})')
# AI 자기사업 기능별 순위
for k, rk in [('기능1',8),('기능2',6),('기능3',9),('기능4',5)]:
    r = f[k][f[k]['세부사업명'].astype(str)=='인공지능(AI)기술활성화지원사업'].iloc[0]
    chk(int(r['순위'])==rk, f'{k} 자기사업 {rk}위 (실제 {int(r["순위"])})')
# 키워드 수
alltxt = d[[a+'_텍스트' for a in AX]].astype(str).agg(' '.join, axis=1)
for kw, n in [('바우처',54),('실증',271),('공급기업',25),('AI공급기업',1),('공급기업 등록',0)]:
    got = int(alltxt.str.contains(kw, regex=False).sum())
    chk(got==n, f"키워드 '{kw}' {n}건 (실제 {got})")
got = int(alltxt.str.contains('AI 공급기업', regex=False).sum())
chk(got==5, f"키워드 'AI 공급기업' 5건 (실제 {got})")
chk(set(d[alltxt.str.contains('AI 공급기업', regex=False)]['세부사업명'])=={'AI통합바우처'}, "'AI 공급기업' 5건 모두 AI통합바우처")
# 1위 산출근거 27,625
chk('212.5백만원 × 130개 과제 = 27,625백만원' in str(d[d['순위']==1].iloc[0]['지원내용_텍스트']), '1위 산출근거 27,625백만원')
chk(d[d['순위']==1].iloc[0]['규모']=='지원규모 89,775백만원', '1위 규모 89,775백만원')
# 세부사업 기준 후보 수
chk(t['세부사업명'].nunique()==11, f"후보20 세부사업 수 11 (실제 {t['세부사업명'].nunique()})")
# 중복 그룹
vc = dict(t['세부사업명'].value_counts())
chk(vc.get('AI통합바우처')==5 and vc.get('ICT융합스마트공장보급·확산')==4 and vc.get('지능형로봇보급 및 확산')==3, f'후보20 중복 그룹 {vc}')
# 공고 연결 733
chk(len(xl.parse('공고매핑'))==733, '공고매핑 733건')
# md에 등장하는 소수 4자리 수치가 산출에 실재하는지
pool = set()
for sh in SHEETS:
    d2 = xl.parse(sh)
    for a in AX:
        pool |= {q(x,4) for x in d2[a+'_유사도']}
        pool |= {q(x,2) for x in d2[a+'_유사도']}
    pool |= {q(x,1) for x in d2[C]} | {q(x,2) for x in d2[C]} | {q(x,4) for x in d2[C]}
    pool |= {q(x,1) for x in d2['참고2지표점수(0~100)']}
for tok in sorted(set(re.findall(r'(?<![\d.])0\.\d{4}', md))):
    if tok not in pool: fail.append(f'[수치] 보고서의 {tok} 가 산출결과에 없음')


# ---- 3) 보고그림 spec 수치 검증 ----
import json
spec = json.load(open('figspec.json', encoding='utf-8'))
fig = json.dumps(spec, ensure_ascii=False)
rows_keys = list(spec['행주석'].keys())
top8 = [str(x) for x in d.head(8)['공고이름']]
chk(rows_keys == top8, f'그림 행주석 키가 전체 상위 8개와 불일치: {rows_keys}')
chk('0.7568' in fig and q(t['지원내용_유사도'].max(),4)=='0.7568', '그림 0.7568')
chk('0.6639' in fig and q(d[d['순위']==4].iloc[0]['지원대상_유사도'],4)=='0.6639', '그림 0.6639')
chk('0.6554' in fig and q(d[d['순위']==5].iloc[0]['지원대상_유사도'],4)=='0.6554', '그림 0.6554')
chk('0.7341' in fig and q(d[d['순위']==6].iloc[0]['사업목적_유사도'],4)=='0.7341', '그림 0.7341')
chk('0.7852' in fig and q(pm['전달체계']['전달체계_유사도'],4)=='0.7852', '그림 0.7852')
chk('0.5893' in fig and q(f['기능3'].loc[f['기능3']['지원대상_유사도'].idxmax()]['지원대상_유사도'],4)=='0.5893', '그림 0.5893')
chk('63.5700' in fig, '그림 p99 63.5700')
chk('226·228·275·246위' in fig, '그림 SW강소 기능별 순위 표기')
chk('66.3' in fig and q(f['기능2'][f['기능2']['순위']==2].iloc[0][C],1)=='66.3', '그림 기능2 2위 66.3')
chk('62.8' in fig and q(f['기능1'][f['기능1']['순위']==6].iloc[0][C],1)=='62.8', '그림 기능1 6위 62.8')
chk('2.34점' in fig and q(f['기능2'][C].iloc[0]-f['기능2'][C].iloc[1])=='2.34', '그림 기능2 2.34점')
chk('271단위' in fig, '그림 실증 271단위')
for tok in sorted(set(re.findall(r'(?<![\d.])0\.\d{4}', fig))):
    if tok not in pool: fail.append(f'[그림] {tok} 가 산출결과에 없음')

print('\n'.join(fail) if fail else '검증 통과: 불일치 0건')
print(f'총 {len(fail)}건 불일치')
sys.exit(1 if fail else 0)
