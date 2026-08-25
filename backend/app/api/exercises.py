"""Exercise generation and submission API."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.models.database import get_db
from app.models.tables import Exercise, UserWord, Word
from app.models.schemas import ExerciseCreate, ExerciseSubmit, ExerciseOut
from app.services.llm import chat_completion
from app.agent.prompts import EXERCISE_PROMPT, SYSTEM_PROMPT

router = APIRouter()

EXERCISE_TYPES = ["multiple_choice", "chinese_to_english", "english_to_chinese", "fill_blank", "rewrite"]


@router.post("/generate", response_model=ExerciseOut)
async def generate_exercise(data: ExerciseCreate, db: AsyncSession = Depends(get_db)):
    """Generate an exercise based on user's vocabulary."""
    exercise_type = data.exercise_type if data.exercise_type in EXERCISE_TYPES else "multiple_choice"

    if data.word:
        result = await db.execute(select(Word).where(Word.word == data.word.lower()))
        word_obj = result.scalar_one_or_none()
        words_text = data.word
    else:
        # Get weakest words
        result = await db.execute(
            select(UserWord)
            .join(Word)
            .options(selectinload(UserWord.word))
            .where(UserWord.user_id == data.user_id)
            .order_by(UserWord.mastery_score)
            .limit(10)
        )
        user_words = result.scalars().all()
        if not user_words:
            raise HTTPException(status_code=400, detail="No vocabulary words found. Add some words first.")
        words_text = ", ".join([uw.word.word for uw in user_words[:5]])

    prompt = EXERCISE_PROMPT.format(
        words=words_text,
        exercise_type=exercise_type,
        level="intermediate",
    )
    raw = await chat_completion([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])

    try:
        # Extract JSON from response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        exercise_data = json.loads(raw[start:end])
    except Exception:
        exercise_data = {"question": raw, "answer": "", "explanation": ""}

    question = exercise_data.get("question", raw)
    choices = exercise_data.get("choices", [])
    if choices:
        question = question + "\n" + "\n".join(choices)
    answer = exercise_data.get("answer", "")

    exercise = Exercise(
        user_id=data.user_id,
        exercise_type=exercise_type,
        question=question,
        answer=answer,
        word=data.word,
    )
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    return ExerciseOut.model_validate(exercise)


@router.post("/submit", response_model=ExerciseOut)
async def submit_exercise(data: ExerciseSubmit, db: AsyncSession = Depends(get_db)):
    """Submit an exercise answer and update mastery."""
    result = await db.execute(select(Exercise).where(Exercise.id == data.exercise_id))
    exercise = result.scalar_one_or_none()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    user_answer = data.user_answer.strip().upper()
    correct_answer = exercise.answer.strip().upper()
    is_correct = user_answer == correct_answer or user_answer in correct_answer

    exercise.user_answer = data.user_answer
    exercise.is_correct = is_correct

    # Update word mastery if linked to a word
    if exercise.word:
        word_result = await db.execute(select(Word).where(Word.word == exercise.word.lower()))
        word_obj = word_result.scalar_one_or_none()
        if word_obj:
            uw_result = await db.execute(
                select(UserWord).where(
                    and_(UserWord.user_id == exercise.user_id, UserWord.word_id == word_obj.id)
                )
            )
            uw = uw_result.scalar_one_or_none()
            if uw:
                if is_correct:
                    uw.correct_count += 1
                else:
                    uw.wrong_count += 1
                total = uw.correct_count + uw.wrong_count
                uw.mastery_score = round(uw.correct_count / total * 100, 1)

    await db.commit()
    await db.refresh(exercise)
    return ExerciseOut.model_validate(exercise)


@router.get("/{user_id}/history", response_model=list[ExerciseOut])
async def exercise_history(user_id: int, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Exercise)
        .where(Exercise.user_id == user_id)
        .order_by(Exercise.created_at.desc())
        .limit(limit)
    )
    return [ExerciseOut.model_validate(e) for e in result.scalars().all()]


@router.get("/{user_id}/stats")
async def exercise_stats(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            func.count(Exercise.id).label("total"),
            func.sum(Exercise.is_correct.cast(int)).label("correct"),
        ).where(Exercise.user_id == user_id)
    )
    row = result.one()
    total = row.total or 0
    correct = row.correct or 0
    accuracy = round(correct / total * 100, 1) if total else 0
    return {"total": total, "correct": correct, "accuracy": accuracy}
