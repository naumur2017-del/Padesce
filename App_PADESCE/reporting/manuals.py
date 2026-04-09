from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path

from django.conf import settings


def get_reporting_manual_path() -> Path:
    return Path(settings.BASE_DIR) / "docs" / "MANUEL_REPORTING_ANALYSE.md"


def load_reporting_manual_markdown() -> str:
    path = get_reporting_manual_path()
    if not path.exists():
        raise FileNotFoundError(f"Manual not found: {path}")
    return path.read_text(encoding="utf-8")


def _slugify_heading(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only.casefold()).strip("-")
    return slug or "section"


_INLINE_TOKEN_RE = re.compile(
    r"\[(?P<label>[^\]]+)\]\((?P<url>[^)]+)\)|`(?P<code>[^`]+)`|\*\*(?P<bold>.+?)\*\*"
)


def _render_inline(text: str) -> str:
    text = str(text or "")
    parts: list[str] = []
    cursor = 0

    for match in _INLINE_TOKEN_RE.finditer(text):
        parts.append(html.escape(text[cursor:match.start()]))
        label = match.group("label")
        code = match.group("code")
        bold = match.group("bold")

        if label is not None:
            url = str(match.group("url") or "").strip()
            safe_label = html.escape(label)
            safe_url = html.escape(url, quote=True)
            target = ""
            if safe_url and not safe_url.startswith("#"):
                target = ' target="_blank" rel="noopener noreferrer"'
            parts.append(f'<a href="{safe_url}"{target}>{safe_label}</a>')
        elif code is not None:
            parts.append(f"<code>{html.escape(code)}</code>")
        elif bold is not None:
            parts.append(f"<strong>{html.escape(bold)}</strong>")

        cursor = match.end()

    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def render_reporting_manual_html(markdown_text: str) -> str:
    lines = str(markdown_text or "").splitlines()
    parts: list[str] = []
    paragraph_lines: list[str] = []
    quote_lines: list[str] = []
    code_lines: list[str] = []
    math_lines: list[str] = []
    code_language = ""
    list_tag: str | None = None
    in_code = False
    in_math = False

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        text = " ".join(chunk.strip() for chunk in paragraph_lines if chunk.strip())
        if text:
            parts.append(f"<p>{_render_inline(text)}</p>")
        paragraph_lines = []

    def flush_quote() -> None:
        nonlocal quote_lines
        if not quote_lines:
            return
        quote_html = " ".join(_render_inline(chunk.strip()) for chunk in quote_lines if chunk.strip())
        if quote_html:
            parts.append(f"<blockquote><p>{quote_html}</p></blockquote>")
        quote_lines = []

    def flush_code() -> None:
        nonlocal code_lines, code_language
        if not code_lines:
            return
        lang_attr = f' class="language-{html.escape(code_language)}"' if code_language else ""
        parts.append(f"<pre><code{lang_attr}>{html.escape(chr(10).join(code_lines))}</code></pre>")
        code_lines = []
        code_language = ""

    def flush_math() -> None:
        nonlocal math_lines
        if not math_lines:
            return
        math_body = "\n".join(math_lines).strip()
        if math_body:
            parts.append(f"<div class=\"manual-math\">$$\n{html.escape(math_body)}\n$$</div>")
        math_lines = []

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            parts.append(f"</{list_tag}>")
            list_tag = None

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if in_code:
            if stripped.startswith("```"):
                flush_code()
                in_code = False
            else:
                code_lines.append(line)
            continue

        if in_math:
            if stripped == "$$":
                flush_math()
                in_math = False
            else:
                math_lines.append(line)
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            flush_quote()
            close_list()
            in_code = True
            code_language = stripped[3:].strip()
            continue

        if stripped == "$$":
            flush_paragraph()
            flush_quote()
            close_list()
            in_math = True
            math_lines = []
            continue

        if stripped == r"\newpage":
            flush_paragraph()
            flush_quote()
            close_list()
            parts.append('<hr class="manual-pagebreak" aria-hidden="true">')
            continue

        if not stripped:
            flush_paragraph()
            flush_quote()
            close_list()
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_quote()
            close_list()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_id = _slugify_heading(title)
            parts.append(f"<h{level} id=\"{heading_id}\">{_render_inline(title)}</h{level}>")
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            close_list()
            quote_lines.append(stripped[1:].strip())
            continue

        bullet_match = re.match(r"^\s*[-*]\s+(.*)$", line)
        ordered_match = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if bullet_match or ordered_match:
            flush_paragraph()
            flush_quote()
            next_tag = "ol" if ordered_match else "ul"
            if list_tag != next_tag:
                close_list()
                parts.append(f"<{next_tag}>")
                list_tag = next_tag
            item_text = ordered_match.group(1) if ordered_match else bullet_match.group(1)
            parts.append(f"<li>{_render_inline(item_text.strip())}</li>")
            continue

        flush_quote()
        close_list()
        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_quote()
    close_list()
    flush_code()
    flush_math()
    return "\n".join(parts)
