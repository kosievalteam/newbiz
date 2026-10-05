"""검토의견서 데이터 모델.

Claude 가 생성하는 JSON 과 docx/markdown 렌더러가 공유하는 단일 스키마.
구조는 샘플 검토의견서(지자체·부처 사전협의 검토의견서)의 지면 순서를 그대로 따른다.

    1. 협의신청사업 및 검토의견 개요
       □ 협의신청사업 개요 / □ 사업개요 추가정보 / □ 검토의견 요약 / ※ 유사중복검토 사업
    2. 검토의견
       1. 종합의견  ○ (사업 타당성) … / ○ (사업 적합성) … + 사업내용 박스 ⇩ 점검 박스 / ○ (유사·중복성) …
       2. 개선의견  ○ (라벨) 헤드라인 + dash
    사업간 비교표
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["동의", "권고"]


class Overview(BaseModel):
    """□ 협의신청사업 개요 표."""

    사업명: str = Field(description="예: '184. 투·융자연계형 연구개발지원 사업 / 세부신설'. 협의번호를 모르면 사업명 / 요청사유만 기재")
    신청기관: str = Field(description="예: '부산광역시 연구개발과'. 담당자 성명·연락처는 기재하지 않음")
    지원유형: str = Field(description="예: '육성 / 기술 / 중소기업, (예비)창업기업 / 전업종 / ’27년 예산 1,000백만원'")
    특이사항: str = Field(description="사후협의·시범사업 후속·이전 협의 이력 등. 없으면 '해당 없음'")
    검토자: str = Field(default="", description="검토자 성명·직위. 입력이 없으면 빈 문자열")


class ExtraInfo(BaseModel):
    """□ 사업개요 추가정보 표 (1-1 ~ 3-1)."""

    근거법령: str
    상위정책: str = Field(description="국정과제·기본계획·지자체 정책과제 등. 없으면 '해당 없음'")
    사업목적: str
    지원대상: str
    지원내용: str
    지원규모: str
    전달체계: str = Field(description="예: '서울특별시 → 서울경제진흥원 → 창업기업'")
    연계사업: str = Field(description="없으면 '해당 없음'")


class VerdictSummary(BaseModel):
    """□ 검토의견 요약 표."""

    종합의견: Verdict
    사업타당성: Verdict
    사업적합성: Verdict
    유사중복성: Verdict


class SimilarProgram(BaseModel):
    """※ 유사중복검토 사업 표의 한 행."""

    부처: str = Field(description="예: '중기부', '문체부'")
    사업명: str
    검토의견: str = Field(description="예: '중복수혜 방지 필요', '차별성 존재'")


class Dash(BaseModel):
    """'-' 항목: 검토자의 평가·판단 진술 (사실 압축 + 판단어휘)."""

    label: str = Field(description="괄호 라벨. 예: '사업성격', '법적근거·상위정책', '정책수요', '사업성과', '지원내용', '지원규모', '수행체계', '사업목적', '지원대상', '지원방식'. 라벨이 없으면 빈 문자열")
    text: str = Field(description="본문. 각주를 가리키는 '*', '**' 표시를 포함할 수 있음. 문장 끝 마침표 없음")
    notes: list[str] = Field(default_factory=list, description="'*' 각주 줄. 예: '(법적근거) 「…조례」 제17조'. 두 번째 각주는 '**' 로 시작하도록 텍스트 앞에 '** ' 를 붙이지 말고 순서로만 구분")


class AxisOpinion(BaseModel):
    """○ 평가축 항목 (사업 타당성 / 사업 적합성 / 유사·중복성)."""

    headline: str = Field(description="'(사업 타당성) 법적근거 및 정책수요 측면 타당, “원안 동의”' 형식. 앞의 '○ ' 는 붙이지 않음")
    group_labels: list[str] = Field(default_factory=list, description="유사·중복성에서 내역사업별로 dash 를 묶을 때 쓰는 소제목. 예: ['➊ 중장년 재도전 프로그램 운영', '➋ 대·중견기업 연계 밋업']. 사용하지 않으면 빈 목록")
    dashes: list[Dash]
    dash_groups: list[list[Dash]] = Field(default_factory=list, description="group_labels 를 쓰는 경우 소제목별 dash 묶음. group_labels 와 길이가 같아야 하며, 이때 dashes 는 비워 둠")
    remarks: list[str] = Field(default_factory=list, description="'※' 비고 줄. 예: 유사중복 자체점검표 미작성 지적")


class ContentBox(BaseModel):
    """사업 적합성 아래 '사업내용' 박스."""

    지원대상: str
    추진내용: str
    추진내용_세부: list[str] = Field(default_factory=list, description="내역별 세부 줄. 예: '(내역1) …'")
    지원규모: str
    지원규모_세부: list[str] = Field(default_factory=list, description="산출내역 줄. 예: '무료직업소개소 6개소 × 47백만원 = 282백만원'")
    수행기관: str


class CheckBox(BaseModel):
    """⇩ 아래 '사업내용 점검' 박스."""

    lines: list[str] = Field(description="예: ['지원대상, 수행체계 : (원안 동의)', '지원내용, 지원규모 : (권고안 제시) 지원물량 구체화'] 또는 ['지원대상, 지원규모, 지원내용, 수행기관 : (원안 동의)']")


class Improvement(BaseModel):
    """2. 개선의견의 ○ 항목."""

    headline: str = Field(description="'(성과관리) 사업목적과 연계된 성과지표 재설정' 형식. 앞의 '○ ' 는 붙이지 않음")
    dashes: list[Dash]


class ComparisonTable(BaseModel):
    """사업간 비교표."""

    columns: list[str] = Field(description="첫 열 제목(구분)을 제외한 열 제목. 예: ['(신규사업) 소상공인 인력 운영 지원', '(기존) 기업인력애로센터 활용 취업 지원']")
    rows: list[list[str]] = Field(description="각 행은 [구분, 값1, 값2, …]. 구분 순서: 사업부서, 사업구조, 사업기간, 지원예산, 사업목적, 수행기관, 지원내용, 지원규모, 지원대상. 셀 내 줄바꿈은 '\\n'")


class SimilarityCandidate(BaseModel):
    """유사도 분석 상위 후보 한 건 (〈참고〉 유사도 분석 결과 표의 행)."""

    순위: int
    사업명: str = Field(description="예: '핀테크 지원 사업 > 디지털 금융혁신 지원'")
    부처_기관: str = Field(description="예: '금융위·한국핀테크지원센터'")
    단위: str = Field(default="", description="'내역' | '내내역' | '공고' 등")
    종합유사도: float = Field(description="0~100")
    사업목적: float = Field(default=0.0, description="축별 코사인 유사도 0~1")
    지원내용: float = Field(default=0.0)
    지원대상: float = Field(default=0.0)
    전달체계: float = Field(default=0.0)
    비고: str = Field(default="", description="예: '비교표 반영(상위 3)', '연계 검토'")


class SimilarityReport(BaseModel):
    """유사도 분석 결과 요약. candidates 가 비어 있으면 문서에 출력하지 않는다."""

    method: str = Field(default="", description="분석 방법·기준 한 줄. 예: '2025·2026년 내역·내내역사업 3,631개 단위, bge-m3 임베딩, 가중치 사업목적 21.05·지원내용 31.58·지원대상 31.58·전달체계 15.79'")
    candidates: list[SimilarityCandidate] = Field(default_factory=list, description="종합 유사도 상위 10개")
    notes: list[str] = Field(default_factory=list, description="해석 유의사항. 예: '동일 수행기관 사업은 전달체계 축이 높게 산출'")


class ReviewOpinion(BaseModel):
    """검토의견서 전체."""

    overview: Overview
    extra_info: ExtraInfo
    summary: VerdictSummary
    similar_programs: list[SimilarProgram] = Field(default_factory=list, description="유사중복 사업이 없으면 빈 목록")
    validity: AxisOpinion = Field(description="○ (사업 타당성)")
    suitability: AxisOpinion = Field(description="○ (사업 적합성)")
    content_box: ContentBox
    check_box: CheckBox
    duplication: AxisOpinion = Field(description="○ (유사·중복성)")
    improvements: list[Improvement] = Field(description="개선의견. 전 항목 동의이면 headline '해당 없음' 1건")
    comparison: ComparisonTable
    similarity: SimilarityReport = Field(default_factory=SimilarityReport, description="유사도 분석 결과(선택). 비교표의 기존사업은 상위 3개 후보를 토대로 선정")
    reviewer_notes: list[str] = Field(default_factory=list, description="검토자가 확인해야 할 불확실 사항·가정. 문서 본문에는 출력하지 않고 별도 메모로 제공")

    def model_json_schema_strict(self) -> dict:  # pragma: no cover - 편의 함수
        return strict_schema(type(self))


def strict_schema(model: type[BaseModel]) -> dict:
    """structured outputs 용 JSON 스키마: 모든 object 에 additionalProperties=false, required=전체."""
    schema = model.model_json_schema()

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
                for v in node["properties"].values():
                    v.pop("default", None)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema
