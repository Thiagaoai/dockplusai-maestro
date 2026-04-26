"""
Exemplo: LangGraph agent com web scraping tool.
Rode: .venv/bin/python scripts/example_langgraph_scraper.py

Este agent recebe uma pergunta, decide se precisa scrapear uma URL,
executa a tool, e responde com base no conteudo da pagina.
"""
import asyncio
import os
from typing import Annotated

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

# Carrega env e tools do projeto
load_dotenv("/Users/thiagodocarmo/Downloads/agent.maestro/.env")
import sys
sys.path.insert(0, "/Users/thiagodocarmo/Downloads/agent.maestro")

from maestro.tools.scraper import scrape_page, extract_links


# --- Estado do Grafo ---
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# --- Tools ---
tools = [scrape_page, extract_links]
tool_node = ToolNode(tools)

# --- LLM com tools bindadas ---
llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0,
).bind_tools(tools)


# --- Nodos ---
def agent_node(state: AgentState):
    """O agente decide qual tool chamar (ou responde direto)."""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def should_continue(state: AgentState):
    """Decide se vai para tools ou para END."""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


# --- Monta o grafo ---
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)

builder.set_entry_point("agent")
builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")

graph = builder.compile()


# --- Roda ---
async def main():
    # Exemplo 1: scrape direto da pagina da Roberts
    inputs = {
        "messages": [
            HumanMessage(
                content="Scrape https://robertslandscapecod.com and tell me what services they offer."
            )
        ]
    }
    print("=== LangGraph Scraping Example ===\n")
    async for event in graph.astream(inputs, stream_mode="values"):
        last_msg = event["messages"][-1]
        if hasattr(last_msg, "content") and last_msg.content:
            print(f"[{last_msg.type}]: {last_msg.content[:600]}...\n")


if __name__ == "__main__":
    asyncio.run(main())
