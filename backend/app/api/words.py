"""Vocabulary (user word list) API."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.models.database import get_db
from app.models.tables import Word, UserWord, User
from app.models.schemas import UserWordOut, WordOut
from app.rag.hybrid_search import hybrid_search

router = APIRouter()

REVIEW_INTERVALS = [1, 3, 7, 15, 30]  # days


def _next_review(review_count: int, is_correct: bool) -> datetime:
    if not is_correct:
        return datetime.utcnow() + timedelta(days=1)
    idx = min(review_count, len(REVIEW_INTERVALS) - 1)
    days = REVIEW_INTERVALS[idx]
    return datetime.utcnow() + timedelta(days=days)


def _update_mastery(word: UserWord, is_correct: bool) -> float:
    total = word.correct_count + word.wrong_count + 1
    correct = word.correct_count + (1 if is_correct else 0)
    return round(correct / total * 100, 1)


@router.post("/{user_id}/save/{word_text}")
async def save_word(user_id: int, word_text: str, db: AsyncSession = Depends(get_db)):
    """Add a word to user's vocabulary list."""
    result = await db.execute(select(Word).where(Word.word == word_text.lower()))
    word = result.scalar_one_or_none()

    if not word:
        # Try to find via RAG then create record
        docs = hybrid_search.search(word_text, top_k=1, use_reranker=False)
        meta = docs[0]["metadata"] if docs else {}
        word = Word(
            word=word_text.lower(),
            phonetic=meta.get("phonetic"),
            pos=meta.get("pos"),
            definition=meta.get("definition"),
            translation=meta.get("translation"),
            source=meta.get("source", "ECDICT"),
        )
        db.add(word)
        await db.flush()

    # Check if already saved
    result = await db.execute(
        select(UserWord).where(and_(UserWord.user_id == user_id, UserWord.word_id == word.id))
    )
    uw = result.scalar_one_or_none()
    if uw:
        return {"ok": True, "message": "Word already in vocabulary"}

    uw = UserWord(
        user_id=user_id,
        word_id=word.id,
        next_review_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(uw)
    await db.commit()
    return {"ok": True, "message": f"Saved '{word_text}' to vocabulary"}


@router.delete("/{user_id}/remove/{word_text}")
async def remove_word(user_id: int, word_text: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserWord)
        .join(Word)
        .where(and_(UserWord.user_id == user_id, Word.word == word_text.lower()))
    )
    uw = result.scalar_one_or_none()
    if not uw:
        raise HTTPException(status_code=404, detail="Word not in vocabulary")
    await db.delete(uw)
    await db.commit()
    return {"ok": True}


@router.get("/{user_id}", response_model=list[UserWordOut])
async def list_user_words(
    user_id: int,
    search: str = Query(""),
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(UserWord)
        .join(Word)
        .options(selectinload(UserWord.word))
        .where(UserWord.user_id == user_id)
    )
    if search:
        stmt = stmt.where(Word.word.ilike(f"%{search}%"))

    col = getattr(UserWord, sort_by, UserWord.created_at)
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc())

    result = await db.execute(stmt)
    user_words = result.scalars().all()
    return [UserWordOut.model_validate(uw) for uw in user_words]


@router.get("/{user_id}/due")
async def get_due_words(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get words due for review today."""
    now = datetime.utcnow()
    result = await db.execute(
        select(UserWord)
        .join(Word)
        .options(selectinload(UserWord.word))
        .where(
            and_(
                UserWord.user_id == user_id,
                UserWord.next_review_at <= now,
            )
        )
        .order_by(UserWord.next_review_at)
    )
    due = result.scalars().all()
    return [UserWordOut.model_validate(uw) for uw in due]


@router.post("/{user_id}/review/{word_id}")
async def review_word(
    user_id: int,
    word_id: int,
    is_correct: bool,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserWord).where(and_(UserWord.user_id == user_id, UserWord.word_id == word_id))
    )
    uw = result.scalar_one_or_none()
    if not uw:
        raise HTTPException(status_code=404, detail="Word not found")

    if is_correct:
        uw.correct_count += 1
    else:
        uw.wrong_count += 1
    uw.review_count += 1
    uw.mastery_score = _update_mastery(uw, is_correct)
    uw.last_review_at = datetime.utcnow()
    uw.next_review_at = _next_review(uw.review_count, is_correct)

    await db.commit()
    return {"ok": True, "mastery_score": uw.mastery_score, "next_review_at": uw.next_review_at}
