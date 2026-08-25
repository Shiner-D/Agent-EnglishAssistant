"""LLM service wrapping DeepSeek / Qwen via OpenAI-compatible API."""
from typing import AsyncGenerator, List, Dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings


def build_llm(streaming: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        streaming=streaming,
        temperature=0.7,
        timeout=60,
        max_retries=2,
    )


def convert_messages(messages: List[Dict]) -> list:
    result = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
        else:
            result.append(HumanMessage(content=content))
    return result


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
async def chat_completion(messages: List[Dict], stream: bool = False) -> str:
    llm = build_llm(streaming=True)
    lc_messages = convert_messages(messages)
    response = await llm.ainvoke(lc_messages)
    return response.content


async def stream_chat(messages: List[Dict]) -> AsyncGenerator[str, None]:
    llm = build_llm(streaming=True)
    lc_messages = convert_messages(messages)
    async for chunk in llm.astream(lc_messages):
        if chunk.content:
            yield chunk.content
