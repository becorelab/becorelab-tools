"""
상품 상세 폴더 구조 변환
단일 파일 → 상품별 폴더 (상품 정보.md + 견적.md)
"""
import os
import shutil
from pathlib import Path

BASE = Path(r"C:\Users\User\Documents\비코어랩\01. Becorelab AI Agent Team\3️⃣ Resources\🗂️ 상품 DB\상품 상세")

QUOTE_TEMPLATE = """# 💰 견적 — {name}

## 타겟 단가
| 항목 | 값 |
|---|---|
| 목표 판매가 | |
| 목표 원가 (CNY→KRW) | |
| 목표 마진율 | |
| 최대 허용 원가 | |

## 업체별 견적

| 업체 | 단가 (USD) | MOQ | 리드타임 | 견적일 | 비고 |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

## 샘플 이력
| 업체 | 요청일 | 수령일 | 결과 |
|---|---|---|---|
|  |  |  |  |

## 최종 선정
- **선정 업체**:
- **확정 단가**:
- **선정 이유**:
"""

files = [f for f in BASE.iterdir() if f.is_file() and f.suffix == ".md"]
print(f"변환 대상: {len(files)}개\n")

for f in sorted(files):
    name = f.stem
    folder = BASE / name

    # 폴더 생성
    folder.mkdir(exist_ok=True)

    # 기존 파일 → 상품 정보.md
    dest = folder / "상품 정보.md"
    shutil.move(str(f), str(dest))

    # 견적.md 생성
    quote_path = folder / "견적.md"
    quote_path.write_text(QUOTE_TEMPLATE.format(name=name), encoding="utf-8")

    print(f"OK: {name}")

print("\n완료!")
