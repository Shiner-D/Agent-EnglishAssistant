"""Agent 状态定义。

AgentState 是贯穿整条 LangGraph 流水线的共享上下文，
每个节点读取它并返回更新后的副本，由框架合并为新状态。
"""
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """LangGraph 图的全局状态容器，在各节点间传递。"""

    messages: Annotated[list, add_messages]  # 完整对话历史，add_messages 负责追加去重
    intent: str | None                        # 当前轮意图标签，由 intent_router_node 写入
    current_word: str | None                  # 本轮焦点单词，由 RAG 检索结果确定
    user_id: int                              # 当前登录用户 ID
    conversation_id: int | None               # 会话 ID，用于持久化到数据库
    retrieved_docs: list                      # RAG 召回的原始文档列表
    difficulty: str | None                    # 用户难度级别（easy / medium / hard）
    exercise_type: str | None                 # 练习类型（multiple_choice / fill_in 等）
    answer: str | None                        # 当前节点生成的最终回复文本
    should_save_word: bool                    # vocabulary 节点置 True 后触发词汇入库
    rag_sources: list                         # 结构化 RAG 来源，供前端展示引用卡片
    stream_tokens: list                       # 流式返回时暂存的 token 片段
