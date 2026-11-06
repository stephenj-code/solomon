"""
tools.py — capabilities.

Functions the agent can call during a run. Each tool is decorated with @tool.
The LLM decides when to call them based on the tool description.

Rules:
  - Description must be clear — the LLM reads it to decide when to use the tool
  - Return a string or JSON-serialisable dict
  - Raise ValueError for bad inputs (the agent will see the error and can recover)
  - Keep tools focused — one tool, one job
"""
from langchain_core.tools import tool


@tool
def example_tool(query: str) -> str:
    """
    An example tool. Replace this with a real capability.
    Use this tool when you need to look something up or perform an action.
    """
    return f"Result for: {query}"


# Collect all tools here — graph.py imports this list
tools = [example_tool]
