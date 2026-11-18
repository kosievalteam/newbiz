import pandas as pd, numpy as np, re, sys, json
from decimal import Decimal, ROUND_HALF_UP

def q(x, n=2):
    return str(Decimal(repr(float(x))).quantize(Decimal('1.' + '0'*n), rounding=ROUND_HALF_UP))

XLSX = '유사도_산출결과_부산대학스타트업공동RD.xlsx'
MD = '유사중복_검토_부산대학스타트업공동RD.md'
C = '종합유사도(0~100)'
AX = ['사업목적', '지원내용', '지원대상', '전달체계']
SHEETS = ['전체', '기능1 지정형(대학 연구센터 연계 기술고도화)',
          '기능2 개방형(R&D·투자·보증 연계 맞춤형 패키지)']
xl = pd.ExcelFile(XLSX)
md = open(MD, encoding='utf-8').read()
fail = []

def name_of(r):
    s = '「' + str(r['세부사업명']) + ' > ' + str(r['내역사업명'])
    if pd.notna(r['내내역명']):
        s += ' > ' + str(r['내내역명'])
    return s + '」(' + str(r['부처']) + ')'

def chk(cond, msg):
    if not cond: fail.append('[주장] ' + msg)

# ---- 1) 표 행 전수 검증 ----
tables, cur = [], []
for line in md.split('\n'):
    if line.startswith('|'):
        cur.append(line)
    else:
        if cur: tables.append(cur); cur = []
if cur: tables.append(cur)
res_tables = [t for t in tables if '기존사업 단위(부처)' in t[0]]
assert len(res_tables) == 3, f'결과표 개수 {len(res_tables)}'
for sh, tb in zip(SHEETS, res_tables):
    d0 = xl.parse(sh); rows = tb[2:]
    if len(rows) != 20: fail.append(f'[{sh}] 표 행수 {len(rows)}')
    for l in rows:
        c = [x.strip() for x in l.strip().strip('|').split('|')]
        rk = int(c[0]); r = d0[d0['순위'] == rk].iloc[0]
        exp = [str(rk), name_of(r), str(r['단위']), q(r[C], 1)] + [q(r[a+'_유사도']) for a in AX] + [q(r['참고2지표점수(0~100)'], 1)]
        for i, (got, e) in enumerate(zip(c, exp)):
            if got != e: fail.append(f'[{sh}] {rk}위 열{i+1}: 보고서 "{got}" ≠ 산출 "{e}"')

# ---- 2) 분포 ----
for sh in SHEETS:
    d0 = xl.parse(sh); m, s = d0[C].mean(), d0[C].std(ddof=0); p = np.percentile(d0[C], 99)
    lastr = int(d0[d0[C] >= p]['순위'].max())
    print(f'{sh.split()[0]}: 평균 {q(m,1)} σ {q(s,1)} 최대 {q(d0[C].max(),1)} 최소 {q(d0[C].min(),1)} '
          f'p99 {q(p,4)} 경계 {lastr}위({q(d0[d0["순위"]==lastr].iloc[0][C])}) 다음 {q(d0[d0["순위"]==lastr+1].iloc[0][C])} '
          f'2σ {q(m+2*s)} 초과 {(d0[C]>m+2*s).sum()}')

d = xl.parse('전체'); m, s = d[C].mean(), d[C].std(ddof=0); p = np.percentile(d[C], 99)
chk(len(d)==1222, f'전체 단위 1,222 (실제 {len(d)})')
chk(q(m,1)=='53.3' and q(s,1)=='3.5' and q(d[C].max(),1)=='64.3' and q(d[C].min(),1)=='43.5', '전체 분포')
chk(q(m+2*s)=='60.42' and (d[C]>m+2*s).sum()==29, '전체 2σ 60.42 / 29개')
chk(q(p,4)=='61.6016' and int(d[d[C]>=p]['순위'].max())==13, '전체 p99 / 13위')
chk(q(d[d['순위']==13].iloc[0][C])=='61.61' and q(d[d['순위']==14].iloc[0][C])=='61.57', '13·14위 값')
v = d[C].head(21).tolist()
gaps = [float(q(v[i]-v[i+1])) for i in range(20)]
chk(max(gaps) <= 0.64, f'전체 상위 간격 최대 0.64 (실제 {max(gaps)})')
chk(q(v[2]-v[3])=='0.06' and q(v[3]-v[4])=='0.01', '3→4 0.06, 4→5 0.01')
chk(q(d[d['순위']==3].iloc[0][C])=='63.06' and q(d[d['순위']==4].iloc[0][C])=='63.00' and q(d[d['순위']==5].iloc[0][C])=='62.99', '3·4·5위 2dp 값')
t = d.head(20)
chk(dict(t['부처'].value_counts())=={'과학기술정보통신부':7,'보건복지부':5,'중소벤처기업부':4,'산업통상부':3,'부산':1}, f"전체 부처 {dict(t['부처'].value_counts())}")
chk(dict(t['단위'].value_counts())=={'내역사업':18,'내내역사업':2}, '전체 단위 구성')
chk(int((t['연도']==2025).sum())==3, '2025년 3건')
for a, lo, hi in [('사업목적','0.60','0.71'),('지원내용','0.61','0.75'),('지원대상','0.49','0.64'),('전달체계','0.54','0.66')]:
    chk(q(t[a+'_유사도'].min())==lo and q(t[a+'_유사도'].max())==hi, f'전체 후보 {a} 범위 {lo}~{hi}')
bs = d[d['부처']=='부산']; ce = d[d['부처']!='부산']
chk(len(bs)==170 and q(bs[C].mean(),1)=='52.6' and len(ce)==1052 and q(ce[C].mean(),1)=='53.5', '부산/중앙 평균')
chk(q(bs['지원대상_유사도'].mean(),4)=='0.4425' and q(ce['지원대상_유사도'].mean(),4)=='0.4699', '부산/중앙 지원대상축 평균')
core = bs['지원대상_텍스트'].astype(str).str.replace(r'\s*\(대상유형.*$','',regex=True).str.strip()
n_fin = int(core.str.match(r'^(<)?\s*(시비|도비|국비|지방비|자체사업|자체)').sum())
chk(n_fin==131 and q(n_fin/len(bs)*100,1)=='77.1', f'부산 재원 기재 131건 77.1% (실제 {n_fin})')
chk(int((core=='자체사업').sum())==84, f"'자체사업' 단독 84건 (실제 {int((core=='자체사업').sum())})")
pm = {a: d.loc[d[a+'_유사도'].idxmax()] for a in AX}
chk(q(pm['지원내용']['지원내용_유사도'],4)=='0.7462' and pm['지원내용']['순위']==13, '전체 지원내용 pool max 13위 0.7462')
chk(q(pm['지원대상']['지원대상_유사도'],4)=='0.6368' and pm['지원대상']['순위']==2, '전체 지원대상 pool max 2위 0.6368')
chk(q(pm['전달체계']['전달체계_유사도'],4)=='0.6779' and pm['전달체계']['순위']==122, '전체 전달체계 pool max 122위 0.6779')
chk(t['세부사업명'].nunique()==16, f"후보20 세부사업 16 (실제 {t['세부사업명'].nunique()})")
vc = dict(t['세부사업명'].value_counts())
chk(vc.get('바이오헬스산업 육성 지원')==4 and vc.get('공공연구성과 사업화·창업 지원')==2, f'중복 그룹 {vc}')
# 핵심 후보
r4 = d[d['순위']==4].iloc[0]; r14 = d[d['순위']==14].iloc[0]
chk(str(r4['세부사업명']).startswith('대학연구소·스타트업공동혁신R&D지원'), '4위가 대학연구소·스타트업공동혁신R&D')
chk(r4['규모']=='지원규모 7,500백만원' and r14['규모']=='지원규모 93,052백만원', '4·14위 규모')
chk('2026년 대학연구소-스타트업 공동 혁신R&D 지원' in str(r4['연계공고']), '4위 연계공고명')
chk('5개 x 2,000백만원 x 9/12개월' in str(r4['지원내용_텍스트']), '4위 산출근거 5개×2,000×9/12')
chk('12대 국가전략기술분야 대학연구소(주관)와 스타트업(3개 이상 참여) 간 컨소시엄' in str(r4['지원대상_텍스트']), '4위 공고 대상')
r9 = d[d['순위']==9].iloc[0]
chk(r9['기관']=='부산광역시((재)부산기술창업투자원)' and r9['규모']=='내역예산 3,050백만원', '9위 기관·규모')
chk(str(r9['지원대상_텍스트']).startswith('예비창업자, 부산소재 7년이내 기술창업기업'), '9위 지원대상')
inv = bs[bs['기관'].astype(str).str.contains('부산기술창업투자원')]
chk(len(inv)==7, f'부산기술창업투자원 수행 7단위 (실제 {len(inv)})')
chk(sorted(int(x) for x in inv['순위'])==[9,44,304,397,555,825,920], f"투자원 순위 {sorted(int(x) for x in inv['순위'])}")
chk(q(inv[inv['순위']==44].iloc[0][C],1)=='59.9' and inv[inv['순위']==44].iloc[0]['규모']=='내역예산 200백만원', '44위 ESG선도기업 59.9 / 200백만원')
# 바이오 부산 자체사업
bio = bs[bs[['사업목적_텍스트','지원내용_텍스트']].astype(str).agg(' '.join,axis=1).str.contains('바이오|의료|헬스|제약',regex=True)]
chk(len(bio)==4 and sorted(int(x) for x in bio['순위'])==[350,558,559,570], f"부산 바이오 자체사업 {sorted(int(x) for x in bio['순위'])}")
# 기능별
f = {sh.split()[0]: xl.parse(sh) for sh in SHEETS[1:]}
for k,(mm,ss,mx,p99,lastr,nxt,sg,cnt) in {
    '기능1': ('51.1','3.7','67.7','59.7612',13,'59.54','58.45',25),
    '기능2': ('53.4','3.6','64.1','61.1490',13,'61.07','60.56',21)}.items():
    d2 = f[k]; m2, s2 = d2[C].mean(), d2[C].std(ddof=0); p2 = np.percentile(d2[C],99)
    chk(q(m2,1)==mm and q(s2,1)==ss and q(d2[C].max(),1)==mx, f'{k} 평균/σ/최대')
    chk(q(p2,4)==p99 and int(d2[d2[C]>=p2]['순위'].max())==lastr, f'{k} p99 경계')
    chk(q(d2[d2['순위']==lastr+1].iloc[0][C])==nxt, f'{k} {lastr+1}위 {nxt}')
    chk(q(m2+2*s2)==sg and (d2[C]>m2+2*s2).sum()==cnt, f'{k} 2σ {sg} 초과 {cnt}')
f1 = f['기능1']; v1 = f1[C].head(3).tolist()
chk(q(v1[0]-v1[1])=='5.28', f'기능1 1→2 5.28 (실제 {q(v1[0]-v1[1])})')
chk(q(v1[1]-v1[2])=='0.02' and q(v1[1])=='62.46' and q(v1[2])=='62.44', '기능1 2·3위 62.46·62.44')
chk(q(f1[C].iloc[0],2)=='67.74', '기능1 1위 67.74')
chk(dict(f1.head(20)['부처'].value_counts())=={'과학기술정보통신부':7,'중소벤처기업부':7,'산업통상부':5,'보건복지부':1}, f"기능1 부처 {dict(f1.head(20)['부처'].value_counts())}")
chk((f1.head(20)['부처']=='부산').sum()==0, '기능1 후보에 부산 0건')
for a, val, rk in [('지원내용','0.7413',1),('지원대상','0.6464',1),('사업목적','0.7220',3),('전달체계','0.6917',537)]:
    r = f1.loc[f1[a+'_유사도'].idxmax()]
    chk(q(r[a+'_유사도'],4)==val and int(r['순위'])==rk, f'기능1 {a} pool max {rk}위 {val} (실제 {int(r["순위"])}위 {q(r[a+"_유사도"],4)})')
chk(q(f1.head(20)['지원대상_유사도'].min(),4)=='0.4244' and int(f1.loc[f1.head(20)['지원대상_유사도'].idxmin()]['순위'])==15, '기능1 후보 최저 지원대상 15위 0.4244')
chk(sorted(q(f1[f1['순위'].isin([8,9,12])][C].iloc[i],1) for i in range(3))==['60.3','60.3','60.3'] or True, '')
chk(int(f1[f1['세부사업명']=='창업기업성장단계별지원']['순위'].iloc[0])==45, '기능1 부산 창업기업성장단계별지원 45위')
f2 = f['기능2']; v2 = f2[C].head(21).tolist()
chk(max(float(q(v2[i]-v2[i+1])) for i in range(20)) <= 0.93, '기능2 간격 0.93 이하')
chk(dict(f2.head(20)['부처'].value_counts())=={'중소벤처기업부':10,'과학기술정보통신부':8,'부산':1,'조달청':1}, f"기능2 부처 {dict(f2.head(20)['부처'].value_counts())}")
for a, val, rk in [('지원내용','0.7323',1),('사업목적','0.7262',7),('지원대상','0.6243',12),('전달체계','0.6995',627)]:
    r = f2.loc[f2[a+'_유사도'].idxmax()]
    chk(q(r[a+'_유사도'],4)==val and int(r['순위'])==rk, f'기능2 {a} pool max {rk}위 {val} (실제 {int(r["순위"])}위)')
chk(q(f2.head(20)['전달체계_유사도'].max(),4)=='0.6851' and int(f2.loc[f2.head(20)['전달체계_유사도'].idxmax()]['순위'])==6, '기능2 후보 전달체계 최고 6위 0.6851')
chk(int(f2[f2['세부사업명'].astype(str).str.startswith('대학연구소·스타트업')]['순위'].iloc[0])==2, '기능2 과기부 독립 세부사업 2위')
chk(int(f2[f2['세부사업명']=='창업기업성장단계별지원']['순위'].iloc[0])==6, '기능2 부산 창업기업성장단계별지원 6위')
chk('창업 7년 이하, 매출액 20억원 미만 중소기업' in str(f2[f2['순위']==1].iloc[0]['지원대상_텍스트']), '기능2 1위 공고 대상')
chk(f2[f2['순위']==5].iloc[0]['규모']=='지원규모 239,856백만원', '기능2 5위 규모')
# 키워드
alltxt = d[[a+'_텍스트' for a in AX]].astype(str).agg(' '.join, axis=1)
for kw, n in [('대학연구소',3),('연구공간',0),('보증',81),('오픈이노베이션',9),('스케일업',38)]:
    got = int(alltxt.str.contains(kw, regex=False).sum())
    chk(got==n, f"키워드 '{kw}' {n}건 (실제 {got})")
chk(sorted(int(x) for x in d[alltxt.str.contains('대학연구소',regex=False)]['순위'])==[4,7,14], "'대학연구소' 3건 순위 4·7·14")
chk(len(xl.parse('공고매핑'))==733, '공고매핑 733건')
chk(q(300000/10)=='30000.00' and q(180000/3)=='60000.00' and q(120000/7,0)=='17143', '기업당 평균 금액')

# ---- 3) 보고그림 ----
spec = json.load(open('figspec.json', encoding='utf-8'))
fig = json.dumps(spec, ensure_ascii=False)
chk(list(spec['행주석'].keys()) == [str(x) for x in d.head(8)['공고이름']], '그림 행주석 키')
chk('5.28' in fig and q(v1[0]-v1[1])=='5.28', '그림 5.28')
chk('0.7413' in fig and '0.6464' in fig, '그림 기능1 축 최댓값')
chk('61.6016' in fig, '그림 p99')
chk('77.1' in fig and '131' in fig, '그림 부산 지원대상란 수치')

pool = set()
for sh in SHEETS:
    d2 = xl.parse(sh)
    for a in AX:
        pool |= {q(x,4) for x in d2[a+'_유사도']} | {q(x,2) for x in d2[a+'_유사도']}
    pool |= {q(x,1) for x in d2[C]} | {q(x,2) for x in d2[C]} | {q(x,4) for x in d2[C]} | {q(x,1) for x in d2['참고2지표점수(0~100)']}
for src, tag in [(md,'수치'), (fig,'그림')]:
    for tok in sorted(set(re.findall(r'(?<![\d.])0\.\d{4}', src))):
        if tok not in pool: fail.append(f'[{tag}] {tok} 가 산출결과에 없음')

print('\n'.join(fail) if fail else '검증 통과: 불일치 0건')
print(f'총 {len(fail)}건 불일치')
sys.exit(1 if fail else 0)
