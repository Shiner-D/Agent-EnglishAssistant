#!/usr/bin/env python3
"""Import a word list (CSV / TXT / JSON) into the wordbook database.

Supported CSV columns (case-insensitive):
  word, phonetic, pos, definition, example, example_translation

Usage:
  python scripts/import_wordlist.py --input cet4.csv --level CET4
  python scripts/import_wordlist.py --input words.txt --level 小学
"""
import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func

from app.models.database import AsyncSessionLocal, init_db
from app.models.tables import WordbookLevel, WordbookWord

LEVEL_META = {
    "幼儿": (0, "幼儿园基础词汇"),
    "小学": (1, "小学阶段核心词汇"),
    "初中": (2, "初中阶段核心词汇"),
    "高中": (3, "高中阶段核心词汇"),
    "CET4": (4, "大学英语四级核心词汇"),
    "CET6": (5, "大学英语六级核心词汇"),
}


async def _ensure_level(db, name: str) -> WordbookLevel:
    result = await db.execute(select(WordbookLevel).where(WordbookLevel.name == name))
    level = result.scalar_one_or_none()
    if not level:
        sort_order, desc = LEVEL_META.get(name, (99, ""))
        level = WordbookLevel(name=name, description=desc, sort_order=sort_order)
        db.add(level)
        await db.flush()
    return level


def _parse_kajweb(entry: dict) -> dict:
    """Parse kajweb/dict nested JSON entry into a flat dict."""
    word_head = entry.get("headWord", "")
    word_data = (entry.get("content") or {}).get("word") or {}
    inner = (word_data.get("content") or {})

    # phonetic: inside content.word.content (not content.word)
    phonetic = inner.get("usphone") or inner.get("ukphone") or ""

    # pos + definition from trans list
    trans_list = inner.get("trans") or []
    pos = ""
    definitions = []
    for t in trans_list:
        if not pos and t.get("pos"):
            pos = t["pos"]
        if t.get("tranCn"):
            definitions.append(t["tranCn"].strip())
    definition = "；".join(definitions)

    # example: inside content.word.content.sentence.sentences
    sentence_block = inner.get("sentence") or {}
    sentences = sentence_block.get("sentences") or []
    example = ""
    example_zh = ""
    if sentences:
        s = sentences[0]
        example = s.get("sContent") or ""
        example_zh = s.get("sCn") or ""

    return {
        "word": word_head,
        "phonetic": phonetic,
        "pos": pos,
        "definition": definition,
        "example": example,
        "example_translation": example_zh,
    }


def _load_rows(path: Path) -> list[dict]:
    if path.suffix == ".csv":
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        # JSONL: each line is a separate JSON object
        if content.startswith("{"):
            data = [json.loads(line) for line in content.splitlines() if line.strip()]
        else:
            data = json.loads(content)
        if not isinstance(data, list):
            return []
        # Detect kajweb/dict format: list of {"headWord": ..., "content": {...}}
        if data and isinstance(data[0], dict) and "headWord" in data[0]:
            print("Detected kajweb/dict nested format, parsing...")
            return [_parse_kajweb(e) for e in data]
        return data
    # Plain text: one word per line
    with open(path, encoding="utf-8") as f:
        return [{"word": line.strip()} for line in f if line.strip()]


def _field(row: dict, *keys: str) -> str | None:
    for k in keys:
        v = row.get(k) or row.get(k.lower()) or row.get(k.upper())
        if v:
            return str(v).strip() or None
    return None


async def import_words(filepath: str, level_name: str, start_order: int) -> None:
    await init_db()
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    rows = _load_rows(path)
    print(f"Loaded {len(rows)} rows from {path.name}")

    async with AsyncSessionLocal() as db:
        level = await _ensure_level(db, level_name)
        added = 0

        for i, row in enumerate(rows):
            word_text = (_field(row, "word", "Word") or "").lower()
            if not word_text:
                continue

            exists = await db.execute(
                select(WordbookWord).where(
                    WordbookWord.word == word_text,
                    WordbookWord.level_id == level.id,
                )
            )
            if exists.scalar_one_or_none():
                continue

            db.add(
                WordbookWord(
                    word=word_text,
                    level_id=level.id,
                    phonetic=_field(row, "phonetic", "音标"),
                    pos=_field(row, "pos", "词性"),
                    definition=_field(row, "definition", "释义"),
                    example=_field(row, "example", "例句"),
                    example_translation=_field(row, "example_translation", "例句翻译"),
                    sort_order=start_order + i,
                )
            )
            added += 1

            if added % 200 == 0:
                await db.commit()
                print(f"  Committed {added} words...")

        count = (
            await db.execute(select(func.count()).where(WordbookWord.level_id == level.id))
        ).scalar() or 0
        level.word_count = count

        await db.commit()
        print(f"Done! Added {added} new words. Level '{level_name}' now has {count} words total.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import word list into wordbook")
    parser.add_argument("--input", required=True, help="CSV / TXT / JSON file path")
    parser.add_argument("--level", required=True, choices=list(LEVEL_META) + ["other"],
                        help="Level name: 幼儿 小学 初中 高中 CET4 CET6")
    parser.add_argument("--start-order", type=int, default=0, help="Starting sort_order (default 0)")
    args = parser.parse_args()

    asyncio.run(import_words(args.input, args.level, args.start_order))
