"""Chat API with SSE streaming."""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.messages import HumanMessage
from loguru import logger

from app.models.database import get_db
from app.models.tables import Conversation, Message, User
from app.models.schemas import ChatRequest, ConversationCreate, ConversationOut, MessageOut
from app.agent.graph import agent_graph
from app.agent.state import AgentState

router = APIRouter()


async def _get_or_create_conversation(
    db: AsyncSession, user_id: int, conversation_id: int | None
) -> Conversation:
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv
    conv = Conversation(user_id=user_id, title="New Conversation")
    db.add(conv)
    await db.flush()
    return conv


async def _load_history(db: AsyncSession, conversation_id: int) -> list:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .limit(20)
    )
    messages = result.scalars().all()
    lc_messages = []
    for m in messages:
        if m.role == "user":
            lc_messages.append(HumanMessage(content=m.content))
        else:
            from langchain_core.messages import AIMessage
            lc_messages.append(AIMessage(content=m.content))
    return lc_messages


async def _sse_event(event: str, data: dict | str) -> str:
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False)
    else:
        # Escape real newlines so SSE line framing stays intact.
        # Without this, a token like "a\nb" breaks into two data: lines
        # and the frontend parser drops the second line entirely.
        data = data.replace('\n', '\\n')
    return f"event: {event}\ndata: {data}\n\n"


@router.post("/stream")
async def chat_stream(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """SSE streaming chat endpoint."""
    conv = await _get_or_create_conversation(db, req.user_id, req.conversation_id)
    history = await _load_history(db, conv.id)

    # Save user message
    user_msg_record = Message(
        conversation_id=conv.id,
        role="user",
        content=req.message,
    )
    db.add(user_msg_record)
    await db.flush()

    # Update conversation title on first message
    if not history:
        conv.title = req.message[:50]

    await db.commit()

    async def event_stream():
        try:
            yield await _sse_event("agent_start", {"conversation_id": conv.id})

            initial_state: AgentState = {
                "messages": history + [HumanMessage(content=req.message)],
                "intent": None,
                "current_word": None,
                "user_id": req.user_id,
                "conversation_id": conv.id,
                "retrieved_docs": [],
                "difficulty": None,
                "exercise_type": None,
                "answer": None,
                "should_save_word": False,
                "rag_sources": [],
                "stream_tokens": [],
            }

            final_state = None
            async for event in agent_graph.astream_events(initial_state, version="v2"):
                kind = event["event"]

                if kind == "on_chain_start" and event.get("name") == "intent_router":
                    yield await _sse_event("intent_start", {})

                elif kind == "on_chain_end" and event.get("name") == "intent_router":
                    output = event.get("data", {}).get("output", {})
                    intent = output.get("intent", "GENERAL_CHAT")
                    yield await _sse_event("intent", {"type": intent.lower()})

                elif kind == "on_chain_start" and event.get("name") == "rag_retrieval":
                    yield await _sse_event("retrieval_start", {})

                elif kind == "on_chain_end" and event.get("name") == "rag_retrieval":
                    output = event.get("data", {}).get("output", {})
                    sources = output.get("rag_sources", [])
                    yield await _sse_event("retrieval_result", {"sources": sources})

                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield await _sse_event("token", chunk.content)

                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        final_state = output

            # Get final answer
            if final_state is None:
                result = await agent_graph.ainvoke(initial_state)
                final_state = result

            answer = final_state.get("answer", "")
            rag_sources = final_state.get("rag_sources", [])

            if rag_sources:
                yield await _sse_event("rerank_result", {"sources": rag_sources})

            yield await _sse_event("llm_done", {"answer": answer})

            # Save AI response
            async with db.begin_nested():
                ai_msg = Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=answer,
                    intent=final_state.get("intent"),
                    sources=rag_sources if rag_sources else None,
                )
                db.add(ai_msg)
            await db.commit()

            yield await _sse_event("done", {"conversation_id": conv.id})

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield await _sse_event("error", {"message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{user_id}")
async def list_conversations(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()
    return [ConversationOut.model_validate(c) for c in convs]


@router.get("/conversations/{user_id}/{conv_id}/messages")
async def get_messages(user_id: int, conv_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .join(Conversation)
        .where(
            Conversation.id == conv_id,
            Conversation.user_id == user_id,
        )
        .order_by(Message.created_at)
    )
    msgs = result.scalars().all()
    return [MessageOut.model_validate(m) for m in msgs]


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()
    return {"ok": True}
