"""
graph.py — structure.

Defines the graph: nodes and the edges between them.
Read this file to understand the full flow of the agent at a glance.

To add a new step:
  1. Write the node function in nodes.py
  2. Add it to the graph with graph.add_node(...)
  3. Wire it with graph.add_edge(...) or graph.add_conditional_edges(...)
"""
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.nodes import agent_node
from app.agent.state import AgentState
from app.agent.tools import tools


def should_continue(state: dict) -> str:
    """Edge condition: if the last message has tool calls, run tools. Otherwise end."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def build_graph(checkpointer=None):
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))

    # Edges
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")  # after tool call, return to agent

    return graph.compile(checkpointer=checkpointer)
