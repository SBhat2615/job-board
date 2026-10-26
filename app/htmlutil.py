from __future__ import annotations

import html
from html.parser import HTMLParser

_ALLOW = {
    "a",
    "p",
    "br",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "b",
    "i",
    "h1",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "code",
    "pre",
}
_SKIP = {"script", "style", "noscript", "iframe", "object", "embed"}
_BLOCKS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "blockquote", "pre", "tr", "ul", "ol"}


def prepare_html(raw: str) -> str:
    """Greenhouse sometimes stores the description as escaped markup."""
    text = raw or ""
    for _ in range(2):
        if "&lt;" not in text and "&gt;" not in text and "&amp;lt;" not in text:
            break
        nxt = html.unescape(text)
        if nxt == text:
            break
        text = nxt
    return text


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP:
            self.skip += 1
            return
        if self.skip or tag not in _ALLOW:
            return
        if tag == "br":
            self.out.append("<br>")
            return
        if tag == "a":
            href = ""
            for key, value in attrs:
                if key.lower() == "href" and value:
                    href = value.strip()
            if href.startswith("http://") or href.startswith("https://"):
                self.out.append(f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">')
                self.stack.append("a")
            return
        self.out.append(f"<{tag}>")
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP and self.skip:
            self.skip -= 1
            return
        if self.skip:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.skip or not data:
            return
        self.out.append(html.escape(data))

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out).strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in _BLOCKS:
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP and self.skip:
            self.skip -= 1
            return
        if self.skip:
            return
        if tag in _BLOCKS:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip or not data:
            return
        self.out.append(data)

    def result(self) -> str:
        text = "".join(self.out)
        lines = [" ".join(line.split()) for line in text.splitlines()]
        compact: list[str] = []
        blank = False
        for line in lines:
            if not line:
                if not blank and compact:
                    compact.append("")
                blank = True
                continue
            blank = False
            compact.append(line)
        return "\n".join(compact).strip()


def sanitize_html(raw: str) -> str:
    prepared = prepare_html(raw or "")
    if "<" not in prepared:
        plain = prepared.strip()
        return f"<p>{html.escape(plain)}</p>" if plain else ""
    parser = _Sanitizer()
    parser.feed(prepared)
    parser.close()
    cleaned = parser.result()
    if cleaned:
        return cleaned
    plain = html_to_text(prepared)
    return f"<p>{html.escape(plain)}</p>" if plain else ""


def html_to_text(raw: str) -> str:
    prepared = prepare_html(raw or "")
    if "<" not in prepared:
        return "\n".join(" ".join(line.split()) for line in prepared.splitlines()).strip()
    parser = _TextExtractor()
    parser.feed(prepared)
    parser.close()
    return parser.result()
