# -*- coding: utf-8 -*-
"""주주명부 PDF 수정: '820808' → '850808' (2번째 글자 '2'→'5'만 교체)"""
import fitz
import shutil

src = r"c:\Users\pnp28\OneDrive\(주)비코어랩\경영운영지원\04. 법인관련서류\(주)채움컴퍼니 주주명부_260407.pdf"
tmp = r"c:\Users\pnp28\claude\주주명부_수정.pdf"

doc = fitz.open(src)
page = doc[0]

# 1) 원본 텍스트 span 찾기
blocks = page.get_text("dict")["blocks"]
target = None
for b in blocks:
    if "lines" in b:
        for l in b["lines"]:
            for s in l["spans"]:
                if "820808" in s["text"]:
                    target = s
                    break

text = target["text"]  # "820808-2029429"
bbox = fitz.Rect(target["bbox"])
origin = target["origin"]
font_size = target["size"]
print(f"원본: '{text}', 폰트: {target['font']}, 크기: {font_size:.2f}pt")
print(f"Bbox: {bbox}")

# 2) BatangChe는 모노스페이스 — 글자당 폭 계산
char_width = (bbox.x1 - bbox.x0) / len(text)
print(f"글자당 폭: {char_width:.3f}pt ({len(text)}글자)")

# 3) '2' (인덱스 1)의 정확한 영역만 redact
idx = 1  # "820808" 에서 '2'의 위치
char_x0 = bbox.x0 + idx * char_width
char_x1 = bbox.x0 + (idx + 1) * char_width
char_rect = fitz.Rect(char_x0 - 0.5, bbox.y0 - 0.5, char_x1 + 0.5, bbox.y1 + 0.5)
print(f"'2' 영역: x={char_x0:.2f}~{char_x1:.2f}")

page.add_redact_annot(char_rect, text="", fill=(1, 1, 1))
page.apply_redactions()
print("'2' 제거 완료")

# 4) 같은 위치에 '5' 삽입 (시스템 BatangChe)
font_path = r"C:\Windows\Fonts\batang.ttc"
insert_x = char_x0
insert_y = origin[1]  # baseline

rc = page.insert_text(
    fitz.Point(insert_x, insert_y),
    "5",
    fontname="BatangChe",
    fontfile=font_path,
    fontsize=font_size,
    color=(0, 0, 0),
)
print(f"'5' 삽입 완료 (rc={rc}), 위치=({insert_x:.2f}, {insert_y:.2f})")

doc.save(tmp)
doc.close()
print(f"저장: {tmp}")
