"""
Exemplo: LangGraph com scraping — SEM dependencia de API paga.
O agente eh deterministico: sempre decide scrapear a URL informada.
A tool scrape_page executa de verdade (httpx + BeautifulSoup).
Rode: .venv/bin/python scripts/example_langgraph_scraper_local.py
"""
import asyncio
import sys
from typing import Annotated

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

sys.path.insert(0, "/Users/thiagodocarmo/Downloads/agent.maestro")
from maestro.tools.scraper import scrape_page, extract_links


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


tools = [scrape_page, extract_links]
tool_node = ToolNode(tools)


def agent_node(state: AgentState):
    """
    Agente deterministico: interpreta a ultima mensagem humana,
    extrai a URL, e emite uma tool_call para scrape_page.
    (Num cenario real, um LLM faria essa decisao.)
    """
    last_human = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_human = msg.content
            break

    # Extrai URL simples do texto
    url = "https://robertslandscapecod.com"
    for word in (last_human or "").split():
        if word.startswith("http"):
            url = word
            break

    # Simula a resposta do LLM com tool_call
    from langchain_core.messages import AIMessage
    return {
        "messages": [
            AIMessage(
                content=f"Vou scrapear {url} para ver os servicos oferecidos.",
                tool_calls=[{
                    "id": "scrape_001",
                    "name": "scrape_page",
                    "args": {"url": url, "max_chars": 2000},
                }],
            )
        ]
    }


def should_continue(state: AgentState):
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


def final_answer(state: AgentState):
    """Resume o resultado do scraping para o usuario."""
    from langchain_core.messages import AIMessage

    # Pega o ultimo ToolMessage (resultado da tool)
    tool_result = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage):
            tool_result = msg.content
            break

    if tool_result:
        # Resumo simples baseado no texto retornado
        content = f"Aqui esta o que encontrei no site:\n\n{tool_result[:900]}..."
    else:
        content = "Nao consegui obter resultados do scraping."

    return {"messages": [AIMessage(content=content)]}


# --- Monta o grafo ---
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)
builder.add_node("final", final_answer)

builder.set_entry_point("agent")
builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "final")
builder.add_edge("final", END)

graph = builder.compile()


async def main():
    inputs = {
        "messages": [
            HumanMessage(content="Scrape https://robertslandscapecod.com and tell me what services they offer.")
        ]
    }
    print("=== LangGraph Scraping (Local/Dry-run LLM) ===\n")
    async for event in graph.astream(inputs, stream_mode="values"):
        for msg in event["messages"]:
            prefix = msg.type.upper()
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                prefix = "AI+TOOL"
            print(f"[{prefix}]: {str(msg.content)[:500]}...\n")
    print("=== FIM ===")


if __name__ == "__main__":
    asyncio.run(main())
