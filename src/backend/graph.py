from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition

from src.backend.llm import llm
from src.backend.state import ChatState
from src.backend.tools import tools
from src.backend.memory import checkpointer

llm_with_tools = llm.bind_tools(tools)


def chat_node(state: ChatState, config=None):
    """LLM node that either answers directly or requests a tool call."""
    # System prompt no longer mentions thread_id — rag_tool now injects it from config itself.
    system_message = SystemMessage(
        content=(
            "You are a helpful assistant. For questions about the uploaded PDF, call the "
            "`rag_tool` with the user's question. You can also use the web search, stock price, "
            "and calculator tools when helpful. If no document is available, ask the user to "
            "upload a PDF."
        )
    )

    messages = [system_message, *state['messages']]
    response = llm_with_tools.invoke(messages, config=config)
    return {"messages": [response]}


tool_node = ToolNode(tools)

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)
graph.add_edge('tools', 'chat_node')

chatbot = graph.compile(checkpointer=checkpointer)