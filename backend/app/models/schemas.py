from datetime import datetime
from pydantic import BaseModel


# --- User ---
class UserCreate(BaseModel):
    username: str
    level: str = "CET4"
    target: str = "CET6"


class UserUpdate(BaseModel):
    level: str | None = None
    target: str | None = None
    daily_words: int | None = None
    preferred_difficulty: str | None = None
    weak_topics: list[str] | None = None


class UserOut(BaseModel):
    id: int
    username: str
    level: str
    target: str
    daily_words: int
    preferred_difficulty: str
    weak_topics: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Conversation ---
class ConversationCreate(BaseModel):
    user_id: int
    title: str = "New Conversation"


class ConversationOut(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Message ---
class MessageCreate(BaseModel):
    conversation_id: int
    role: str
    content: str


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    intent: str | None
    sources: list | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Chat Request ---
class ChatRequest(BaseModel):
    user_id: int
    conversation_id: int | None = None
    message: str


# --- Word ---
class WordOut(BaseModel):
    id: int
    word: str
    phonetic: str | None
    pos: str | None
    definition: str | None
    translation: str | None
    collocations: list[str] | None
    examples: list[str] | None
    frequency: int
    level: str | None
    source: str

    class Config:
        from_attributes = True


# --- UserWord ---
class UserWordOut(BaseModel):
    id: int
    user_id: int
    word_id: int
    word: WordOut
    mastery_score: float
    correct_count: int
    wrong_count: int
    review_count: int
    last_review_at: datetime | None
    next_review_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Exercise ---
class ExerciseCreate(BaseModel):
    user_id: int
    exercise_type: str
    word: str | None = None


class ExerciseSubmit(BaseModel):
    exercise_id: int
    user_answer: str


class ExerciseOut(BaseModel):
    id: int
    user_id: int
    exercise_type: str
    question: str
    answer: str
    user_answer: str | None
    is_correct: bool | None
    word: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# --- RAG ---
class RetrievedDoc(BaseModel):
    word: str
    phonetic: str | None = None
    pos: str | None = None
    definition: str | None = None
    translation: str | None = None
    source: str
    retrieval_score: float
    rerank_score: float | None = None


class RAGResult(BaseModel):
    query: str
    docs: list[RetrievedDoc]
    answer: str | None = None
