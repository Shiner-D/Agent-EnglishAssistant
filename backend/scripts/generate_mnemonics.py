#!/usr/bin/env python3
"""Batch-generate Chinese mnemonic hints for wordbook words using the LLM.

Skips words that already have a mnemonic (safe to re-run / resume).

Usage:
  python scripts/generate_mnemonics.py              # all levels
  python scripts/generate_mnemonics.py --level CET4
  python scripts/generate_mnemonics.py --level CET4 --batch 3 --limit 100
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.models.database import AsyncSessionLocal, init_db
from app.models.tables import WordbookLevel, WordbookWord
from app.services.llm import chat_completion

PROMPT = """\
你是英语记忆专家。请为以下英语单词分三段生成中文记忆辅助内容，帮助中文学习者快速记住单词的拼写和含义。

单词：{word}
词性：{pos}
中文释义：{definition}

请严格按以下格式输出，每段以标签开头，换行分隔：

【谐音联想】发音近似哪个中文词或短语？自然吻合时用。30字以内。

【词根词缀】拆出有意义的词根/前缀/后缀，点明每部分的含义来源。若为基础词根无法拆解，写"基础词，无明显词根词缀"。40字以内。

【场景故事】用一个具体的画面或动作，把拼写、发音、含义串联成一个小故事或口诀，让人过目不忘。60字以内。

示例（aggressive）：
【谐音联想】"阿哥莱死"——听起来像个横冲直撞的人喊出的话。
【词根词缀】ag(朝向)+gress(走/攻)+ive(形容词)，朝着目标猛冲过去。
【场景故事】阿哥（ag）大步走（gress）过来，气势十足，侵略性（aggressive）爆棚！

直接输出三段，不加任何额外说明："""


async def _gen(word: WordbookWord) -> str | None:
    prompt = PROMPT.format(
        word=word.word,
        pos=word.pos or "n./v./adj.",
        definition=word.definition or word.word,
    )
    try:
        text = await chat_completion([{"role": "user", "content": prompt}], stream=False)
        return text.strip() or None
    except Exception as e:
        print(f"  [error] {word.word}: {e}")
        return None


async def run(level_name: str | None, batch_size: int, limit: int | None) -> None:
    await init_db()

    async with AsyncSessionLocal() as db:
        stmt = select(WordbookWord).where(WordbookWord.mnemonic.is_(None))

        if level_name:
            lv = (
                await db.execute(select(WordbookLevel).where(WordbookLevel.name == level_name))
            ).scalar_one_or_none()
            if not lv:
                print(f"Level '{level_name}' not found in database. Import words first.")
                return
            stmt = stmt.where(WordbookWord.level_id == lv.id)

        stmt = stmt.order_by(WordbookWord.id)
        if limit:
            stmt = stmt.limit(limit)

        words = (await db.execute(stmt)).scalars().all()
        total = len(words)
        print(f"Found {total} words without mnemonics.")
        if not total:
            return

        done = 0
        for i in range(0, total, batch_size):
            batch = words[i : i + batch_size]
            results = await asyncio.gather(*[_gen(w) for w in batch])

            for w, mnemonic in zip(batch, results):
                if mnemonic:
                    w.mnemonic = mnemonic
                    done += 1
                    print(f"  [{done}/{total}] {w.word}: {mnemonic}")

            await db.commit()

            remaining = total - (i + batch_size)
            if remaining > 0:
                await asyncio.sleep(1)  # gentle rate-limit

        print(f"\nFinished. Generated {done}/{total} mnemonics.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mnemonics for wordbook words")
    parser.add_argument("--level", help="Level name to filter (default: all)")
    parser.add_argument("--batch", type=int, default=5, help="Concurrent LLM calls per batch (default 5)")
    parser.add_argument("--limit", type=int, help="Max words to process in this run")
    args = parser.parse_args()

    asyncio.run(run(args.level, args.batch, args.limit))
