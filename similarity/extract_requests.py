"""검토의견서 txt 91건에서 '협의요청서(별지1) + 사업기획 자체점검표의 객관 정보란'만 추출한다.

지시서 2-2에 따라 다음은 전면 배제한다.
 - 요청서 표제 앞의 검토의견·사업간 비교표 등 검토자 작성 구간
 - 요청서 뒤에 다시 나오는 사업간 비교표
 - 유사중복 자체점검표의 '점검 내용'(기존사업 비교·유사성·차별성·중복 판단)
 - [지원분야 분류 기준] 등 서식 부록, 부속자료(참고2 이후)
"""
import csv, re, sys
from pathlib import Path

SRC = Path(sys.argv[1]); OUT = Path(sys.argv[2]); LOG = Path(sys.argv[3])
TITLE = "중소기업지원사업 사전협의 요청서"
CMP = re.compile(r"사업\s*간\s*비교표|사업간 비교")
MARKS = ["추진|근거", "추진|사유", "정책|목적", "성과|지표", "정책|분야",
         "지원|대상", "지원|내용", "지원|규모", "시행|방법"]
END_OK = re.compile(r"^\s*(사업·제도 연계|유사중복 자체점검표)\s*$")

def find_pair(lines, a, b, start=0):
    for i in range(start, len(lines) - 1):
        if lines[i].strip() == a:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip() == b:
                return i, j
    return None, None

def clean(xs):
    out = []
    for x in xs:
        s = x.strip().lstrip("※").strip()
        if not s or s in {"내용 기재", "해당없음", "해당 없음", "-"}:
            continue
        if re.fullmatch(r"[□■◼☑\s]*", s):
            continue
        out.append(s)
    return re.sub(r"\s+", " ", " ".join(out)).strip()

OPT = re.compile(r"\(괄호안 내용 기재\)|\(내용 기재\)|내용 기재|해당내용 기재|간략 기재|상세 기재")
def note_lines(block):
    """서식의 선택지 줄은 버리고 실제 기재 내용만 남긴다.

    경량본에서 체크박스 선택지 줄은 앞에 공백이 붙은 채로 나오고(' 모든기업  중소·중견기업'),
    기관이 적어 넣은 내용은 '※' 로 시작하거나 행 첫 칸부터 시작한다.
    """
    keep = []
    for l in block:
        t = l.rstrip()
        if not t.strip():
            continue
        body = t.lstrip()
        norm = re.sub(r"\s+", " ", body)
        if body.startswith("※"):
            if not OPT.search(body):
                keep.append(body)
        elif norm not in BOILER and not OPT.search(body):
            keep.append(body)
    return clean(keep)

# 서식 보일러플레이트 판별: 같은 줄이 여러 문서에 공통으로 나오면 양식 문구다.
# (내용 줄은 문서마다 다르므로 1~2건, 선택지 줄은 77~91건으로 분포가 뚜렷이 갈린다)
import collections
_df = collections.Counter()
_cache = {}
for _f in sorted(SRC.glob("*.txt")):
    _raw = _f.read_text(encoding="utf-8"); _ti = _raw.find(TITLE)
    if _ti < 0: continue
    _L = _raw[_ti:].splitlines(); _he = len(_L)
    for _i, _l in enumerate(_L):
        _ls = _l.strip().lstrip("\uf072\uf06f\uf0fe\u25a0\u25a1\u25cf\u25cb ").strip()
        if _ls == "유사중복 자체점검표" and not _l.strip().startswith("2."): _he = _i; break
    _cache[_f.name] = (_raw, _ti, _he)
    for _s in {re.sub(r"\s+", " ", _x.strip()) for _x in _L[:_he] if _x.strip()}:
        _df[_s] += 1
BOILER = {k for k, v in _df.items() if v >= 30}
print(f"서식 보일러플레이트 {len(BOILER)}종(30개 문서 이상 공통) 제외")

rows, log = [], []
for f in sorted(SRC.glob("*.txt")):
    num = re.match(r"_?\s*(2026-\d{3})", f.name)
    if not num:
        log.append([f.name, "", "제외", "협의번호 식별 불가", "", ""]); continue
    no = num.group(1)
    raw = f.read_text(encoding="utf-8")
    ti = raw.find(TITLE)
    if ti < 0:
        log.append([f.name, no, "제외", "요청서 표제 없음", "", ""]); continue
    allowed = raw[ti:]
    cut = []
    for m in CMP.finditer(allowed):         # 요청서 뒤의 사업간 비교표 차단
        cut.append((max(0, m.start() - 200), m.start() + 4000))
    for a, b in sorted(cut, reverse=True):
        allowed = allowed[:a] + allowed[b:]
    L = allowed.splitlines()
    # 유사중복 자체점검표 '점검 내용' 이후 전면 차단
    si, sj = find_pair(L, "점검", "내용")
    chk_from = sj if sj else None
    hard_end = len(L)                       # 유사중복 자체점검표 '제목 줄'부터 차단
    for i, l in enumerate(L):                # (필수첨부 목록의 '2. 유사중복 자체점검표' 는 제외)
        ls = l.strip().lstrip("\uf072\uf06f\uf0fe\u25a0\u25a1\u25cf\u25cb ").strip()
        if ls == "유사중복 자체점검표" and not l.strip().startswith("2."):
            hard_end = i; break
    body = L[:hard_end]                      # 요청서 + 사업기획 자체점검표까지만 사용
    secs = {}
    pos = []
    for mk in MARKS:
        a, b = mk.split("|")
        i, j = find_pair(body, a, b)
        pos.append((i if i is not None else -1, mk, j))
    ordered = [p for p in pos if p[0] >= 0]
    ordered.sort()
    for k, (i, mk, j) in enumerate(ordered):
        end = ordered[k + 1][0] if k + 1 < len(ordered) else len(body)
        secs[mk] = body[j + 1:end]
    # 사업명·기관·사업개요
    def after(label, n=1):
        for i, l in enumerate(body):
            if l.strip() == label:
                v = [x.strip() for x in body[i + 1:i + 12] if x.strip()]
                return v[:n]
        return []
    agency = (after("신청기관") or [""])[0]
    dept = (after("신청부서") or [""])[0]
    name_parts = []
    for i, l in enumerate(body):
        if l.strip() == "사업명":
            for x in body[i + 1:i + 14]:
                s = x.strip()
                if s.startswith("(세부사업)") or s.startswith("(내역사업)") or s.startswith("(내내역사업)"):
                    v = s.split(")", 1)[1].strip()
                    if v and v != "-":
                        name_parts.append(v)
                elif s == "사업개요":
                    break
            break
    gaeyo = []
    for i, l in enumerate(body):
        if l.strip() == "사업개요":
            for x in body[i + 1:i + 40]:
                s = x.strip()
                if s.startswith("타 제도") or "협의·심사" in s or s == "협의부처":
                    break
                gaeyo.append(s)
            break
    gaeyo = clean(gaeyo)
    nm = " > ".join(name_parts) or f.stem
    rows.append({
        "공고이름": f"{no} {nm}",
        "부처": agency, "기관": note_lines(secs.get("시행|방법", [])) or dept,
        "목적": clean([gaeyo, note_lines(secs.get("정책|목적", [])), note_lines(secs.get("추진|사유", []))]),
        "내용": note_lines(secs.get("지원|내용", [])) or gaeyo,
        "대상": note_lines(secs.get("지원|대상", [])),
        "규모": note_lines(secs.get("지원|규모", [])),
        "설명": "", "대분류": "", "중분류": "", "대상유형": "", "업종": "",
        "정책목적": note_lines(secs.get("정책|목적", [])),
        "신규/기존": "협의사업", "공고링크": "", "시행방법": note_lines(secs.get("시행|방법", [])),
        "협의번호": no, "출처파일": f.name,
    })
    log.append([f.name, no, "포함", f"요청서 표제 {ti}자 지점부터 사용, 점검내용·비교표·부속자료 차단",
                f"목적 {len(rows[-1]['목적'])}자/내용 {len(rows[-1]['내용'])}자/대상 {len(rows[-1]['대상'])}자", nm])

with OUT.open("w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
with LOG.open("w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh); w.writerow(["출처파일", "협의번호", "처리", "추출 구간", "길이", "사업명"]); w.writerows(log)
print(f"추출 {len(rows)}건 → {OUT}")
empty = [r["공고이름"] for r in rows if not r["목적"] or not r["내용"] or not r["대상"]]
print(f"필수 축 비어 있는 건 {len(empty)}: {empty[:8]}")
