"""Learning Dashboard stats API."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.database import get_db
from app.models.tables import UserWord, Word, Exercise, Message, Conversation

router = APIRouter()


@router.get("/{user_id}")
async def get_dashboard(user_id: int, db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # Total words learned
    total_words = await db.scalar(
        select(func.count(UserWord.id)).where(UserWord.user_id == user_id)
    )

    # Mastered words (mastery >= 80)
    mastered = await db.scalar(
        select(func.count(UserWord.id)).where(
            and_(UserWord.user_id == user_id, UserWord.mastery_score >= 80)
        )
    )

    # Due for review
    due_count = await db.scalar(
        select(func.count(UserWord.id)).where(
            and_(UserWord.user_id == user_id, UserWord.next_review_at <= now)
        )
    )

    # Exercise accuracy
    ex_total = await db.scalar(
        select(func.count(Exercise.id)).where(Exercise.user_id == user_id)
    )
    ex_correct = await db.scalar(
        select(func.count(Exercise.id)).where(
            and_(Exercise.user_id == user_id, Exercise.is_correct == True)
        )
    )
    accuracy = round((ex_correct or 0) / (ex_total or 1) * 100, 1)

    # Weekly learning trend (words reviewed per day)
    result = await db.execute(
        select(
            func.date(UserWord.updated_at).label("day"),
            func.count(UserWord.id).label("count"),
        )
        .where(
            and_(UserWord.user_id == user_id, UserWord.updated_at >= week_start)
        )
        .group_by(func.date(UserWord.updated_at))
        .order_by("day")
    )
    trend = [{"day": str(row.day), "count": row.count} for row in result]

    # Weakest words (lowest mastery, most wrong)
    result = await db.execute(
        select(UserWord, Word)
        .join(Word)
        .where(
            and_(UserWord.user_id == user_id, UserWord.wrong_count > 0)
        )
        .order_by(UserWord.mastery_score)
        .limit(10)
    )
    weak_words = [
        {
            "word": row.Word.word,
            "mastery_score": row.UserWord.mastery_score,
            "wrong_count": row.UserWord.wrong_count,
        }
        for row in result
    ]

    # Recent activity
    result = await db.execute(
        select(Message)
        .join(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Message.created_at.desc())
        .limit(5)
    )
    recent_msgs = [
        {"role": m.role, "content": m.content[:80], "created_at": m.created_at.isoformat()}
        for m in result.scalars().all()
    ]

    return {
        "total_words": total_words or 0,
        "mastered": mastered or 0,
        "due_count": due_count or 0,
        "exercise_total": ex_total or 0,
        "exercise_correct": ex_correct or 0,
        "accuracy": accuracy,
        "weekly_trend": trend,
        "weak_words": weak_words,
        "recent_activity": recent_msgs,
    }
