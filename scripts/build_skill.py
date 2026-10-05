#!/usr/bin/env python3
"""Claude 스킬 패키지(sme-review-drafter) 조립 스크립트.

저장소의 단일 원본(review_draft 패키지·프롬프트·예시·fixture)을 skill/ 의 SKILL.md 와 합쳐
dist/sme-review-drafter/ 폴더와 dist/sme-review-drafter.skill(zip) 을 만든다.

사용: python scripts/build_skill.py [--out dist]
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_SKILL = ROOT / "skill" / "sme-review-drafter"
PKG = ROOT / "review_draft"


def schema_guide() -> str:
    """pydantic 필드 설명으로 schema_guide.md 생성."""
    import sys

    sys.path.insert(0, str(ROOT))
    from review_draft import schema as s

    lines = ["# 검토의견 JSON 필드 설명", "", "`assets/opinion_template.json` 과 같은 구조. 모든 필드는 필수이며 값이 없으면 빈 문자열/빈 목록.", ""]
    for cls in (s.ReviewOpinion, s.Overview, s.ExtraInfo, s.VerdictSummary, s.SimilarProgram, s.AxisOpinion, s.Dash,
                s.ContentBox, s.CheckBox, s.Improvement, s.ComparisonTable):
        lines.append(f"## {cls.__name__}")
        if cls.__doc__:
            lines.append(cls.__doc__.strip().splitlines()[0])
        lines.append("")
        lines.append("| 필드 | 타입 | 설명 |")
        lines.append("|---|---|---|")
        for name, f in cls.model_fields.items():
            t = str(f.annotation).replace("typing.", "").replace("review_draft.schema.", "")
            lines.append(f"| `{name}` | {t} | {(f.description or '').replace('|', '／')} |")
        lines.append("")
    return "\n".join(lines)


def build(out_dir: Path) -> Path:
    dst = out_dir / "sme-review-drafter"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SRC_SKILL, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # scripts/review_draft : 패키지 복사 (프롬프트 포함)
    shutil.copytree(PKG, dst / "scripts" / "review_draft", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # references
    ref = dst / "references"
    ref.mkdir(exist_ok=True)
    shutil.copy(PKG / "prompts" / "system.md", ref / "writing_rules.md")
    ex_dst = ref / "exemplars"
    ex_dst.mkdir(exist_ok=True)
    for p in sorted((PKG / "prompts" / "exemplars").glob("*.md")):
        shutil.copy(p, ex_dst / p.name)
    (ref / "schema_guide.md").write_text(schema_guide(), encoding="utf-8")

    # assets
    assets = dst / "assets"
    assets.mkdir(exist_ok=True)
    tmpl = json.loads((ROOT / "tests" / "fixtures" / "opinion_sample.json").read_text(encoding="utf-8"))
    (assets / "opinion_template.json").write_text(json.dumps(tmpl, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy(SRC_SKILL / "profile_template.json", assets / "profile_template.json")
    (dst / "profile_template.json").unlink(missing_ok=True)

    # .skill (zip)
    skill_file = out_dir / "sme-review-drafter.skill"
    with zipfile.ZipFile(skill_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(dst.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(out_dir))
    return skill_file


PLUGIN_SKILLS = ROOT / "plugins" / "sme-review-drafter" / "skills"


def sync_plugin(built_dir: Path) -> Path:
    """빌드된 스킬 폴더를 플러그인(plugins/sme-review-drafter/skills/)에 복사한다. 이 폴더는 저장소에 커밋한다."""
    dst = PLUGIN_SKILLS / built_dir.name
    if dst.exists():
        shutil.rmtree(dst)
    PLUGIN_SKILLS.mkdir(parents=True, exist_ok=True)
    shutil.copytree(built_dir, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dst


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--no-plugin", action="store_true", help="플러그인 폴더 동기화 생략")
    args = ap.parse_args()
    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    f = build(out)
    print(f"스킬 패키지 생성: {f}")
    if not args.no_plugin:
        d = sync_plugin(out / "sme-review-drafter")
        print(f"플러그인 스킬 동기화: {d}")
