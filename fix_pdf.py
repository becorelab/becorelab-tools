# -*- coding: utf-8 -*-
import fitz
import shutil

src = r"c:\Users\pnp28\OneDrive\(주)비코어랩\경영운영지원\04. 법인관련서류\(주)채움컴퍼니 주주명부_260407.pdf"
tmp = r"c:\Users\pnp28\claude\주주명부_수정.pdf"
dst = r"c:\Users\pnp28\OneDrive\(주)비코어랩\경영운영지원\04. 법인관련서류\(주)채움컴퍼니 주주명부_260407_수정.pdf"

doc = fitz.open(src)
page = doc[0]

# Get exact span info
blocks = page.get_text("dict")["blocks"]
target = None
for b in blocks:
    if "lines" in b:
        for l in b["lines"]:
            for s in l["spans"]:
                if "820808" in s["text"]:
                    target = s

bbox = target["bbox"]
origin = target["origin"]
font_size = target["size"]
print(f"Original: '{target['text']}', Font: {target['font']}, Size: {font_size}")

# Step 1: Redact - remove original text completely
rect = fitz.Rect(bbox)
rect.x0 -= 1
rect.y0 -= 1
rect.x1 += 1
rect.y1 += 1
page.add_redact_annot(rect, text="", fill=(1, 1, 1))
page.apply_redactions()
print("Redacted original text")

# Step 2: Insert new text using system BatangChe
font_path = r"C:\Windows\Fonts\batang.ttc"
rc = page.insert_text(
    fitz.Point(origin[0], origin[1]),
    "850808-2029429",
    fontname="BatangChe",
    fontfile=font_path,
    fontsize=font_size,
    color=(0, 0, 0),
)
print(f"Inserted text, rc={rc}")

# Save to temp location first
doc.save(tmp)
doc.close()
print(f"Saved temp: {tmp}")

# Copy to OneDrive
try:
    shutil.copy2(tmp, dst)
    print(f"Copied to: {dst}")
except Exception as e:
    print(f"Copy failed: {e}")
    print(f"File is at: {tmp}")
