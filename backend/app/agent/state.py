from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str | None
    current_word: str | None
    user_id: int
    conversation_id: int | None
    retrieved_docs: list
    difficulty: str | None
    exercise_type: str | None
    answer: str | None
    should_save_word: bool
    rag_sources: list
    stream_tokens: list
