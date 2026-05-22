#!/usr/bin/env python3
"""Import an EPUB into the Co-Reading MCP chunk format.

This is deliberately dependency-light. It reads the EPUB zip, extracts XHTML/HTML
documents in spine order when possible, falls back to all HTML files otherwise,
strips tags, and delegates chunk writing to import_text.py.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from import_text import slugify, write_book


CONTAINER = "META-INF/container.xml"


def ns_name(name: str) -> str:
    return name.split("}", 1)[-1]


def text_from_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(p|div|section|article|h[1-6]|li|tr)>", "\n\n", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
    raw = re.sub(r"\n\s*\n\s*\n+", "\n\n", raw)
    return raw.strip()


def find_opf_path(zf: zipfile.ZipFile) -> str | None:
    try:
        root = ET.fromstring(zf.read(CONTAINER))
    except Exception:
        return None

    for element in root.iter():
        if ns_name(element.tag) == "rootfile":
            full_path = element.attrib.get("full-path")
            if full_path:
                return full_path
    return None


def parse_opf(zf: zipfile.ZipFile, opf_path: str) -> tuple[str | None, str | None, list[str]]:
    root = ET.fromstring(zf.read(opf_path))
    opf_dir = str(Path(opf_path).parent)
    if opf_dir == ".":
        opf_dir = ""

    title = None
    author = None
    manifest: dict[str, str] = {}
    spine_ids: list[str] = []

    for element in root.iter():
        local = ns_name(element.tag)
        if local == "title" and element.text and title is None:
            title = element.text.strip()
        elif local == "creator" and element.text and author is None:
            author = element.text.strip()
        elif local == "item":
            item_id = element.attrib.get("id")
            href = element.attrib.get("href")
            media_type = element.attrib.get("media-type", "")
            if item_id and href and ("html" in media_type or href.lower().endswith((".html", ".xhtml", ".htm"))):
                manifest[item_id] = str(Path(opf_dir) / href) if opf_dir else href
        elif local == "itemref":
            ref = element.attrib.get("idref")
            if ref:
                spine_ids.append(ref)

    ordered = [manifest[item_id] for item_id in spine_ids if item_id in manifest]
    return title, author, ordered


def html_files(zf: zipfile.ZipFile) -> list[str]:
    return sorted(
        name
        for name in zf.namelist()
        if name.lower().endswith((".html", ".xhtml", ".htm")) and not name.endswith("/")
    )


def read_epub(path: Path) -> tuple[str | None, str | None, str]:
    with zipfile.ZipFile(path) as zf:
        opf_path = find_opf_path(zf)
        title = None
        author = None
        ordered: list[str] = []
        if opf_path:
            try:
                title, author, ordered = parse_opf(zf, opf_path)
            except Exception:
                ordered = []
        if not ordered:
            ordered = html_files(zf)

        parts = []
        for name in ordered:
            try:
                raw = zf.read(name).decode("utf-8")
            except UnicodeDecodeError:
                raw = zf.read(name).decode("utf-8", errors="ignore")
            except KeyError:
                continue
            text = text_from_html(raw)
            if text:
                parts.append(text)

    return title, author, "\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--book-id")
    parser.add_argument("--out", type=Path, default=Path("data/books"))
    parser.add_argument("--max-chars", type=int, default=6000)
    args = parser.parse_args()

    title, author, text = read_epub(args.input)
    final_title = args.title or title or args.input.stem
    final_author = args.author or author
    book_id = args.book_id or slugify(final_title)

    if not text.strip():
        print("No readable text found in EPUB", file=sys.stderr)
        raise SystemExit(1)

    book_dir = write_book(text, final_title, final_author, args.out, book_id, args.max_chars)
    manifest_path = book_dir / "manifest.json"
    # Mark source as epub after write_book creates the manifest.
    import json

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source"] = {"type": "epub", "fileName": args.input.name}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(book_dir)


if __name__ == "__main__":
    main()
