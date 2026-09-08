"""Wordbook API — pre-curated word lists with mnemonics by education level."""
import os
import shutil
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.tables import WordbookLevel, WordbookWord, UserWordbookProgress
from app.models.schemas import (
    WordbookLevelOut,
    WordbookWordOut,
    UserWordbookProgressUpdate,
    StudyProgressSummary,
)

router = APIRouter()

IMAGE_DIR = "data/wordbook_images"
os.makedirs(IMAGE_DIR, exist_ok=True)


@router.get("/levels", response_model=list[WordbookLevelOut])
async def get_levels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WordbookLevel).order_by(WordbookLevel.sort_order))
    return result.scalars().all()


@router.get("/levels/{level_id}/words", response_model=list[WordbookWordOut])
async def get_level_words(
    level_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(WordbookWord)
        .where(WordbookWord.level_id == level_id)
        .order_by(WordbookWord.sort_order)
        .offset(offset)
        .limit(page_size)
    )
    return result.scalars().all()


@router.get("/words/{word_id}", response_model=WordbookWordOut)
async def get_word(word_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WordbookWord).where(WordbookWord.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return word


@router.post("/words/{word_id}/image")
async def upload_image(
    word_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(WordbookWord).where(WordbookWord.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{word_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest = os.path.join(IMAGE_DIR, filename)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    word.image_path = filename
    await db.commit()
    return {"ok": True, "image_path": filename}


@router.get("/progress/{user_id}", response_model=list[StudyProgressSummary])
async def get_progress(user_id: int, db: AsyncSession = Depends(get_db)):
    levels_result = await db.execute(select(WordbookLevel).order_by(WordbookLevel.sort_order))
    levels = levels_result.scalars().all()

    summaries = []
    for level in levels:
        total = (
            await db.execute(
                select(func.count()).where(WordbookWord.level_id == level.id)
            )
        ).scalar() or 0

        learned = (
            await db.execute(
                select(func.count())
                .select_from(UserWordbookProgress)
                .join(WordbookWord, UserWordbookProgress.word_id == WordbookWord.id)
                .where(
                    and_(
                        UserWordbookProgress.user_id == user_id,
                        WordbookWord.level_id == level.id,
                        UserWordbookProgress.status.in_(["learning", "mastered"]),
                    )
                )
            )
        ).scalar() or 0

        mastered = (
            await db.execute(
                select(func.count())
                .select_from(UserWordbookProgress)
                .join(WordbookWord, UserWordbookProgress.word_id == WordbookWord.id)
                .where(
                    and_(
                        UserWordbookProgress.user_id == user_id,
                        WordbookWord.level_id == level.id,
                        UserWordbookProgress.status == "mastered",
                    )
                )
            )
        ).scalar() or 0

        summaries.append(
            StudyProgressSummary(
                level_id=level.id,
                level_name=level.name,
                total=total,
                learned=learned,
                mastered=mastered,
            )
        )

    return summaries


@router.post("/progress/{user_id}/{word_id}")
async def update_progress(
    user_id: int,
    word_id: int,
    body: UserWordbookProgressUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserWordbookProgress).where(
            and_(
                UserWordbookProgress.user_id == user_id,
                UserWordbookProgress.word_id == word_id,
            )
        )
    )
    progress = result.scalar_one_or_none()
    now = datetime.utcnow()

    if not progress:
        progress = UserWordbookProgress(user_id=user_id, word_id=word_id, status=body.status)
        if body.status in ("learning", "mastered"):
            progress.learned_at = now
        if body.status == "mastered":
            progress.mastered_at = now
        db.add(progress)
    else:
        progress.status = body.status
        if body.status in ("learning", "mastered") and not progress.learned_at:
            progress.learned_at = now
        if body.status == "mastered" and not progress.mastered_at:
            progress.mastered_at = now

    await db.commit()
    return {"ok": True, "status": body.status}


@router.get("/study/{user_id}/{level_id}")
async def get_study_words(
    user_id: int,
    level_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return words for today's session, unlearned words first."""
    progress_result = await db.execute(
        select(UserWordbookProgress.word_id, UserWordbookProgress.status)
        .join(WordbookWord, UserWordbookProgress.word_id == WordbookWord.id)
        .where(
            and_(
                UserWordbookProgress.user_id == user_id,
                WordbookWord.level_id == level_id,
            )
        )
    )
    progress_map = {row.word_id: row.status for row in progress_result}

    words_result = await db.execute(
        select(WordbookWord)
        .where(WordbookWord.level_id == level_id)
        .order_by(WordbookWord.sort_order)
        .limit(limit * 3)
    )
    words = words_result.scalars().all()

    priority = {"unlearned": 0, "learning": 1, "mastered": 2}
    words_sorted = sorted(words, key=lambda w: priority.get(progress_map.get(w.id, "unlearned"), 0))[:limit]

    return [
        {**WordbookWordOut.model_validate(w).model_dump(), "status": progress_map.get(w.id, "unlearned")}
        for w in words_sorted
    ]
