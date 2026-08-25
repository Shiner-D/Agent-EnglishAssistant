"""LangGraph Agent nodes."""
import json
from typing import AsyncGenerator
from loguru import logger
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.state import AgentState
from app.agent.prompts import (
    INTENT_PROMPT, WORD_LOOKUP_PROMPT, EXERCISE_PROMPT,
    TRANSLATE_PROMPT, REWRITE_PROMPT, SYSTEM_PROMPT,
)
from app.rag.hybrid_search import hybrid_search
from app.services.llm import chat_completion, stream_chat
from app.core.config import settings


def _get_last_user_message(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            return msg.content
        if isinstance(msg, dict) and msg.get("role") == "user":
            return msg["content"]
    return ""


def _get_history_text(state: AgentState, max_turns: int = 5) -> str:
    messages = state["messages"][-max_turns * 2:]
    lines = []
    for msg in messages:
        if hasattr(msg, "type"):
            role = "User" if msg.type == "human" else "Assistant"
            lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


async def intent_router_node(state: AgentState) -> AgentState:
    """Classify user intent."""
    user_msg = _get_last_user_message(state)
    history = _get_history_text(state)
    prompt = INTENT_PROMPT.format(history=history, message=user_msg)
    intent = await chat_completion([
        {"role": "system", "content": "You are an intent classifier."},
        {"role": "user", "content": prompt},
    ])
    intent = intent.strip().upper()
    valid = {"WORD_LOOKUP", "EXERCISE", "TRANSLATE", "REWRITE", "VOCABULARY", "GENERAL_CHAT"}
    if intent not in valid:
        intent = "GENERAL_CHAT"
    logger.info(f"Intent: {intent}")
    return {**state, "intent": intent}


async def rag_retrieval_node(state: AgentState) -> AgentState:
    """RAG retrieval for word lookup."""
    user_msg = _get_last_user_message(state)
    docs = hybrid_search.search(user_msg, top_k=settings.RETRIEVAL_TOP_K)
    logger.info(f"Retrieved {len(docs)} documents")

    rag_sources = []
    for doc in docs:
        meta = doc.get("metadata", {})
        rag_sources.append({
            "word": meta.get("word", ""),
            "phonetic": meta.get("phonetic"),
            "pos": meta.get("pos"),
            "definition": meta.get("definition"),
            "translation": meta.get("translation"),
            "source": meta.get("source", "ECDICT"),
            "retrieval_score": doc.get("retrieval_score", doc.get("rrf_score", 0.0)),
            "rerank_score": doc.get("rerank_score"),
        })

    current_word = docs[0]["metadata"].get("word") if docs else state.get("current_word")
    return {**state, "retrieved_docs": docs, "rag_sources": rag_sources, "current_word": current_word}


async def word_lookup_node(state: AgentState) -> AgentState:
    """Generate word explanation using RAG context."""
    user_msg = _get_last_user_message(state)
    docs = state.get("retrieved_docs", [])

    context_parts = []
    for doc in docs[:5]:
        meta = doc.get("metadata", {})
        context_parts.append(
            f"Word: {meta.get('word')}\n"
            f"Phonetic: {meta.get('phonetic', '')}\n"
            f"POS: {meta.get('pos', '')}\n"
            f"Definition: {meta.get('definition', '')}\n"
            f"Translation: {meta.get('translation', '')}\n"
        )
    context = "\n---\n".join(context_parts) if context_parts else "No relevant word found in knowledge base."

    prompt = WORD_LOOKUP_PROMPT.format(
        context=context,
        question=user_msg,
        level="intermediate",
    )
    answer = await chat_completion([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    return {**state, "answer": answer}


async def exercise_node(state: AgentState) -> AgentState:
    """Generate exercise based on user vocabulary."""
    user_msg = _get_last_user_message(state)
    user_words_text = "persist, insist, persevere"  # placeholder; replaced by tool call
    prompt = EXERCISE_PROMPT.format(
        words=user_words_text,
        exercise_type="multiple_choice",
        level="intermediate",
    )
    answer = await chat_completion([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    return {**state, "answer": answer}


async def translate_node(state: AgentState) -> AgentState:
    """Handle translation requests."""
    user_msg = _get_last_user_message(state)
    prompt = TRANSLATE_PROMPT.format(message=user_msg)
    answer = await chat_completion([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    return {**state, "answer": answer}


async def rewrite_node(state: AgentState) -> AgentState:
    """Handle sentence rewrite/simplify requests."""
    user_msg = _get_last_user_message(state)
    prompt = REWRITE_PROMPT.format(
        text=user_msg,
        instruction=user_msg,
        difficulty=state.get("difficulty", "medium"),
    )
    answer = await chat_completion([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    return {**state, "answer": answer}


async def vocabulary_node(state: AgentState) -> AgentState:
    """Handle vocabulary list operations."""
    user_msg = _get_last_user_message(state)
    word = state.get("current_word", "")
    answer = f"已将 **{word}** 添加到您的生词本。" if word else "请告诉我您想添加哪个单词。"
    return {**state, "answer": answer, "should_save_word": bool(word)}


async def general_chat_node(state: AgentState) -> AgentState:
    """Handle general English learning conversation."""
    history = []
    for msg in state["messages"][-10:]:
        if hasattr(msg, "type"):
            role = "user" if msg.type == "human" else "assistant"
            history.append({"role": role, "content": msg.content})

    answer = await chat_completion([
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
    ])
    return {**state, "answer": answer}


def route_intent(state: AgentState) -> str:
    """Conditional edge: route based on intent."""
    intent = state.get("intent", "GENERAL_CHAT")
    routes = {
        "WORD_LOOKUP": "rag_retrieval",
        "EXERCISE": "exercise",
        "TRANSLATE": "translate",
        "REWRITE": "rewrite",
        "VOCABULARY": "vocabulary",
        "GENERAL_CHAT": "general_chat",
    }
    return routes.get(intent, "general_chat")
