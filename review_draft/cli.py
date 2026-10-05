"""review-draft 명령행 인터페이스."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import __version__


@click.group(help="사전협의 요청서 → 검토의견서 초안 자동 생성 도구")
@click.version_option(__version__)
def main():
    pass


@main.command("extract", help=".hwp/.hwpx/.pdf 에서 평문을 추출한다.")
@click.argument("src", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--out", type=click.Path(dir_okay=False), help="저장 경로 (생략 시 표준출력)")
@click.option("--markers/--no-markers", default=False, help="[TABLE]/[CELL] 마커 유지")
def cmd_extract(src, out, markers):
    from .hwp import clean_lines, extract_text

    text = extract_text(src, markers=markers)
    text = "\n".join(clean_lines(text, keep_markers=markers))
    if out:
        Path(out).write_text(text, encoding="utf-8")
        click.echo(f"저장: {out} ({len(text)}자)")
    else:
        click.echo(text)


@main.command("parse", help="사전협의 요청서를 항목별로 파싱해 보여준다 (LLM 입력 확인용).")
@click.argument("src", type=click.Path(exists=True, dir_okay=False))
@click.option("--json", "as_json", is_flag=True, help="JSON 으로 출력")
def cmd_parse(src, as_json):
    from dataclasses import asdict

    from .request_parser import parse_request_file

    rf = parse_request_file(src)
    if rf.is_empty():
        click.echo("경고: 요청서 항목을 찾지 못했습니다. 양식이 다르거나 추출에 실패했을 수 있습니다.", err=True)
    if as_json:
        d = asdict(rf)
        d.pop("raw_text", None)
        click.echo(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        click.echo(rf.to_prompt_text())


@main.command("draft", help="요청서로부터 검토의견서 초안(.docx/.md/.json)을 생성한다.")
@click.argument("src", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--out-dir", type=click.Path(file_okay=False), default="output", show_default=True)
@click.option("--name", help="출력 파일 기본 이름 (기본: 입력 파일명)")
@click.option("--reviewer", default="", help="검토자 표기. 예: '홍길동 선임연구원'")
@click.option("--consult-no", default="", help="협의번호. 예: 2026-190")
@click.option("--context", "context_files", multiple=True, type=click.Path(exists=True, dir_okay=False),
              help="참고자료(.txt/.md/.hwp/.pdf). 기존 유사사업 공고 등. 여러 번 지정 가능")
@click.option("--exemplar-dir", type=click.Path(exists=True, file_okay=False), help="자체 예시(.md) 폴더. 생략 시 내장 예시 사용")
@click.option("--model", default=None, help="모델 ID (기본: claude-opus-5-5, 환경변수 REVIEW_DRAFT_MODEL)")
@click.option("--effort", default="high", type=click.Choice(["low", "medium", "high", "xhigh", "max"]), show_default=True)
@click.option("--max-tokens", default=32000, show_default=True)
@click.option("--no-fallback", is_flag=True, help="서버측 refusal fallback 비활성화")
@click.option("--with-appendix", is_flag=True, help="docx 끝에 협의요청서 원문을 참고1 로 첨부")
@click.option("--no-docx", is_flag=True, help=".docx 생성 생략")
def cmd_draft(src, out_dir, name, reviewer, consult_no, context_files, exemplar_dir, model, effort, max_tokens, no_fallback, with_appendix, no_docx):
    from .generator import DEFAULT_MODEL, generate
    from .hwp import clean_lines, extract_text
    from .request_parser import parse_request_file

    rf = parse_request_file(src)
    if rf.is_empty():
        click.echo("오류: 요청서 항목을 찾지 못했습니다. `review-draft extract` 로 추출 결과를 먼저 확인하세요.", err=True)
        sys.exit(2)

    extra = []
    for cf in context_files:
        extra.append(f"## {Path(cf).name}\n" + "\n".join(clean_lines(extract_text(cf))))
    click.echo(f"요청서 파싱 완료: {rf.사업명.splitlines()[0] if rf.사업명 else '(사업명 미확인)'}", err=True)
    click.echo(f"모델 호출 중… ({model or DEFAULT_MODEL}, effort={effort})", err=True)
    result = generate(rf, model=model or DEFAULT_MODEL, reviewer=reviewer, consult_no=consult_no,
                      extra_context="\n\n".join(extra), exemplar_dir=exemplar_dir, effort=effort,
                      max_tokens=max_tokens, use_fallback=not no_fallback)
    base = name or Path(src).stem
    paths = _write_outputs(result.opinion, Path(out_dir), base, appendix=rf.raw_text if with_appendix else None, docx=not no_docx)
    u = result.usage or {}
    click.echo(f"완료 (model={result.model}, in={u.get('input_tokens')}, cache_read={u.get('cache_read_input_tokens')}, out={u.get('output_tokens')})", err=True)
    for p in paths:
        click.echo(str(p))
    from .checks import check_opinion

    _print_findings(check_opinion(result.opinion))
    if result.opinion.reviewer_notes:
        click.echo("\n[검토자 확인 메모]", err=True)
        for n in result.opinion.reviewer_notes:
            click.echo(f"- {n}", err=True)


@main.command("render", help="저장된 검토의견 JSON 을 .docx/.md 로 다시 렌더링한다 (수정 후 재출력용).")
@click.argument("json_path", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--out-dir", type=click.Path(file_okay=False), default="output", show_default=True)
@click.option("--name", help="출력 파일 기본 이름")
@click.option("--appendix", type=click.Path(exists=True, dir_okay=False), help="참고1 로 첨부할 요청서 파일")
def cmd_render(json_path, out_dir, name, appendix):
    from .hwp import clean_lines, extract_text
    from .schema import ReviewOpinion

    op = ReviewOpinion.model_validate_json(Path(json_path).read_text(encoding="utf-8"))
    app = "\n".join(clean_lines(extract_text(appendix))) if appendix else None
    for p in _write_outputs(op, Path(out_dir), name or Path(json_path).stem, appendix=app, write_json=False):
        click.echo(str(p))


@main.command("check", help="검토의견 JSON 의 개조식 논리 정합성·표현을 점검한다 (헤드라인–dash 대응, 요약표, 개선의견, 금칙 표현).")
@click.argument("json_path", type=click.Path(exists=True, dir_okay=False))
def cmd_check(json_path):
    from .checks import check_opinion
    from .schema import ReviewOpinion

    op = ReviewOpinion.model_validate_json(Path(json_path).read_text(encoding="utf-8"))
    findings = check_opinion(op)
    _print_findings(findings)
    sys.exit(1 if any(f.level == "error" for f in findings) else 0)


def _print_findings(findings):
    if not findings:
        click.echo("정합성 점검: 지적 사항 없음")
        return
    errs = sum(1 for f in findings if f.level == "error")
    click.echo(f"정합성 점검: 오류 {errs}건, 주의 {len(findings) - errs}건")
    for f in findings:
        click.echo("  " + str(f))


@main.command("exemplar", help="기존 검토의견서(.hwp)를 익명화된 작성 예시(.md)로 변환한다.")
@click.argument("srcs", nargs=-1, type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--out-dir", type=click.Path(file_okay=False), required=True)
def cmd_exemplar(srcs, out_dir):
    from .exemplars import build_exemplar

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for s in srcs:
        text = build_exemplar(s)
        dst = out / (Path(s).stem.split("_")[0] + ".md")
        dst.write_text(text, encoding="utf-8")
        click.echo(f"{s} → {dst} ({len(text)}자)")
    click.echo("※ 생성된 예시에 담당자 성명 등 개인정보가 남아 있지 않은지 확인하세요.", err=True)


def _write_outputs(op, out_dir: Path, base: str, *, appendix=None, docx=True, write_json=True) -> list[Path]:
    from .render_docx import render_docx
    from .render_md import render_md

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    if write_json:
        p = out_dir / f"{base}.json"
        p.write_text(op.model_dump_json(indent=2), encoding="utf-8")
        paths.append(p)
    p = out_dir / f"{base}.md"
    p.write_text(render_md(op), encoding="utf-8")
    paths.append(p)
    if docx:
        paths.append(render_docx(op, out_dir / f"{base}.docx", appendix_text=appendix))
    return paths


if __name__ == "__main__":
    main()
