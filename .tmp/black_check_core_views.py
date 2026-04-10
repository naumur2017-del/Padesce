import difflib
from pathlib import Path

import black

p = Path(r"App_PADESCE/core/views.py")
s = p.read_text(encoding="utf-8")
try:
    f = black.format_file_contents(s, fast=False, mode=black.Mode())
    changed = f != s
except black.NothingChanged:
    f = s
    changed = False
print(f"changed= {changed}")
if changed:
    print(
        "\n".join(
            difflib.unified_diff(
                s.splitlines(), f.splitlines(), fromfile=str(p), tofile=str(p), lineterm=""
            )
        )
    )
