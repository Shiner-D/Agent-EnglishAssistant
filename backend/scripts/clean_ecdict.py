"""
ECDICT data cleaning script.
Supports both SQLite (.db) and CSV (.csv) input.

Usage:
  # SQLite (recommended - download ecdict-sqlite-28.zip)
  python scripts/clean_ecdict.py --input ecdict.db --output data/words.json

  # CSV (if you cloned the repo and have stardict.csv)
  python scripts/clean_ecdict.py --input stardict.csv --output data/words.json
"""
import csv
import json
import sqlite3
import argparse
from pathlib import Path


LEVEL_MAP = {
    "zk": "middle",
    "gk": "high",
    "cet4": "CET4",
    "cet6": "CET6",
    "ky": "postgraduate",
    "toefl": "TOEFL",
    "ielts": "IELTS",
    "gre": "GRE",
}


def parse_level(tag: str) -> str | None:
    if not tag:
        return None
    for key, val in LEVEL_MAP.items():
        if key in tag.lower():
            return val
    return None


def parse_pos(definition: str) -> list[str]:
    pos_set = set()
    if not definition:
        return []
    for line in definition.split("\\n"):
        line = line.strip()
        for pos in ["n.", "v.", "vi.", "vt.", "adj.", "adv.", "prep.", "conj.", "pron.", "num.", "int."]:
            if line.startswith(pos):
                pos_set.add(pos)
    return list(pos_set)


def clean_row(row: dict) -> dict | None:
    word = (row.get("word") or "").strip()
    if not word or not word.isascii():
        return None
    if len(word.split()) > 3:
        return None

    definition = (row.get("definition") or "").strip()
    translation = (row.get("translation") or "").strip()
    phonetic = (row.get("phonetic") or "").strip()
    tag = row.get("tag") or ""
    bnc = int(row.get("bnc") or 0)
    frq = int(row.get("frq") or 0)
    frequency = bnc + frq

    pos_list = parse_pos(definition)
    if not pos_list and row.get("pos"):
        pos_list = [str(row["pos"]).strip()]

    collocations = []
    exchange = row.get("exchange") or ""
    if exchange:
        for part in exchange.split("/"):
            if ":" in part:
                collocations.append(part.split(":")[1])

    return {
        "word": word,
        "phonetic": phonetic or None,
        "pos": "/".join(pos_list) if pos_list else None,
        "definition": definition or None,
        "translation": translation or None,
        "collocations": collocations or None,
        "frequency": frequency,
        "level": parse_level(tag),
        "source": "ECDICT",
    }


def read_sqlite(path: str, limit: int):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # ECDICT sqlite uses table name 'stardict'
    query = "SELECT * FROM stardict"
    if limit:
        query += f" LIMIT {limit}"
    cur.execute(query)
    for row in cur:
        yield dict(row)
    conn.close()


def read_csv(path: str, limit: int):
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            yield row


def main():
    parser = argparse.ArgumentParser(description="Clean ECDICT (SQLite or CSV) to JSON")
    parser.add_argument("--input", required=True, help="Path to ecdict.db or stardict.csv")
    parser.add_argument("--output", default="data/words.json", help="Output JSON path")
    parser.add_argument("--limit", type=int, default=0, help="Limit rows (0=all)")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    input_path = args.input.lower()
    if input_path.endswith(".db") or input_path.endswith(".sqlite"):
        reader = read_sqlite(args.input, args.limit)
        fmt = "SQLite"
    else:
        reader = read_csv(args.input, args.limit)
        fmt = "CSV"

    print(f"Reading from {fmt}: {args.input}")
    words = []
    for row in reader:
        cleaned = clean_row(row)
        if cleaned:
            words.append(cleaned)
        if len(words) % 50000 == 0 and words:
            print(f"  Processed {len(words)} words...")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    print(f"Done: {len(words)} words → {output_path}")


if __name__ == "__main__":
    main()
