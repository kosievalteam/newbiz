#!/usr/bin/env python3
"""review-draft CLI 진입점 (스킬 동봉판). 같은 폴더의 review_draft 패키지를 사용한다.

사용: python scripts/rd.py {extract|parse|check|render|exemplar} ...
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from review_draft.cli import main
except ImportError as e:  # 의존 패키지 누락
    sys.stderr.write(
        f"필요한 패키지를 불러오지 못했습니다: {e}\n"
        "다음을 실행한 뒤 다시 시도하세요:\n  pip install olefile python-docx pydantic click\n"
    )
    sys.exit(2)

if __name__ == "__main__":
    main()
