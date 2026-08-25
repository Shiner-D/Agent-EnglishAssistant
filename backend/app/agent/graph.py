"""LangGraph Agent workflow definition."""
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes import (
    intent_router_node,
    rag_retrieval_node,
    word_lookup_node,
    exercise_node,
    translate_node,
    rewrite_node,
    vocabulary_node,
    general_chat_node,
    route_intent,
)


def build_graph() -> StateGraph:
    """构建英语辅导 Agent 的有向图。

    图的执行流程：
      用户输入
        → intent_router（意图分类）
            ├─→ rag_retrieval → word_lookup → END  # 词义查询：RAG 检索语料后再补充词典数据
            ├─→ exercise → END                      # 练习题生成
            ├─→ translate → END                     # 翻译
            ├─→ rewrite → END                       # 改写润色
            ├─→ vocabulary → END                    # 词汇讲解
            └─→ general_chat → END                  # 通用闲聊
    """
    builder = StateGraph(AgentState)

    # 注册所有节点
    builder.add_node("intent_router", intent_router_node)
    builder.add_node("rag_retrieval", rag_retrieval_node)
    builder.add_node("word_lookup", word_lookup_node)
    builder.add_node("exercise", exercise_node)
    builder.add_node("translate", translate_node)
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("vocabulary", vocabulary_node)
    builder.add_node("general_chat", general_chat_node)

    # 入口节点：所有请求都先经过意图分类
    builder.set_entry_point("intent_router")

    # 根据 route_intent 返回的意图标签条件跳转到对应功能节点
    builder.add_conditional_edges(
        "intent_router",
        route_intent,
        {
            "rag_retrieval": "rag_retrieval",
            "exercise": "exercise",
            "translate": "translate",
            "rewrite": "rewrite",
            "vocabulary": "vocabulary",
            "general_chat": "general_chat",
        },
    )

    # RAG 检索到语义相关片段后，还需要 word_lookup 用词典补充精确的释义/例句
    builder.add_edge("rag_retrieval", "word_lookup")

    # 其余功能节点处理完毕后直接结束
    builder.add_edge("word_lookup", END)
    builder.add_edge("exercise", END)
    builder.add_edge("translate", END)
    builder.add_edge("rewrite", END)
    builder.add_edge("vocabulary", END)
    builder.add_edge("general_chat", END)

    return builder.compile()


# 模块级单例：编译一次供所有请求复用，避免每次请求重复构建图
agent_graph = build_graph()
