#!/usr/bin/env python3
"""Import a plain text file into the Co-Reading MCP chunk format."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "book"


def count_words(text: str) -> int:
    words = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text)
    return len(words)


def split_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        if current and current_len + len(paragraph) + 2 > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

        if len(paragraph) > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start : start + max_chars])
            continue

        current.append(paragraph)
        current_len += len(paragraph) + 2

    if current:
        chunks.append("\n\n".join(current))

    return chunks or [text.strip()]


def chunk_id(index: int) -> str:
    return f"ch{index:02d}"


def write_book(
    text: str,
    title: str,
    author: str | None,
    out_dir: Path,
    book_id: str | None,
    max_chars: int,
) -> Path:
    resolved_book_id = book_id or slugify(title)
    book_dir = out_dir / resolved_book_id
    chunks_dir = book_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    chunks = split_text(text, max_chars)
    manifest_chunks = []

    for index, chunk in enumerate(chunks):
        cid = chunk_id(index)
        path = chunks_dir / f"{cid}.txt"
        display_title = title if len(chunks) == 1 else f"{title} Part {index + 1}/{len(chunks)}"
        path.write_text(f"# {display_title}\n\n{chunk.strip()}\n", encoding="utf-8")
        manifest_chunks.append(
            {
                "id": cid,
                "title": display_title,
                "order": index,
                "path": f"chunks/{cid}.txt",
                "charCount": len(chunk),
                "wordCount": count_words(chunk),
                "prevId": chunk_id(index - 1) if index > 0 else None,
                "nextId": chunk_id(index + 1) if index < len(chunks) - 1 else None,
            }
        )

    manifest = {
        "bookId": resolved_book_id,
        "title": title,
        "author": author,
        "language": None,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": {"type": "text"},
        "chunks": manifest_chunks,
    }
    (book_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return book_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author")
    parser.add_argument("--book-id")
    parser.add_argument("--out", type=Path, default=Path("data/books"))
    parser.add_argument("--max-chars", type=int, default=6000)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    book_dir = write_book(text, args.title, args.author, args.out, args.book_id, args.max_chars)
    print(book_dir)


if __name__ == "__main__":
    main()
