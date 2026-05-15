"""실제 발송될 메일 Preview (DRY RUN, 발송 X)."""
import os, sys
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(os.path.join(_DIR, "..", "..", "sourcing", "analyzer", ".env"))

from pipeline import TEMPLATES, _pick_template_type, sheet_get_approved_unsent
from config import PARTNERS_SUBJECT_PREFIX

unsent = sheet_get_approved_unsent()
print(f"발송 대기: {len(unsent)}명\n")
print("=" * 80)

out_path = os.path.join(_DIR, "preview_output.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"발송 대기: {len(unsent)}명\n")
    f.write("=" * 80 + "\n")
    for c in unsent:
        name = c["name"]
        ttype = _pick_template_type(c.get("category", ""))
        tpl = TEMPLATES[ttype]
        hook = c.get("personal_hook", "") or ""
        hook_with_space = " " + hook if hook else ""
        subject = f"{PARTNERS_SUBJECT_PREFIX} {tpl['subject'].format(name=name)}"
        body = tpl["body"].format(name=name, personal_hook=hook_with_space)
        f.write(f"\n▶ {name} ({c['email']}) — 타입 {ttype}\n")
        f.write(f"제목: {subject}\n")
        f.write("-" * 80 + "\n")
        f.write(body + "\n")
        f.write("=" * 80 + "\n")
print(f"Preview 저장: {out_path}")
