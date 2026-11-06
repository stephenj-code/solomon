"""
nodes.py — logic.

One function per graph node. Each node receives the current state,
does one thing, and returns a dict of state fields to update.

Rules:
  - Node functions are pure: input is state, output is state update dict
  - One node, one responsibility
  - Nodes call tools via the LLM — do not call tool functions directly
  - Use the model from config (never hardcode a model name)
"""
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import tools
from app.config import settings

# Bind tools to the model so the LLM can call them
model = ChatOpenAI(
    model=settings.litellm_model,
    base_url=settings.litellm_base_url,
    api_key=settings.litellm_api_key,
).bind_tools(tools)


async def agent_node(state: dict) -> dict:
    """Main reasoning node. Calls the LLM with current messages."""
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = await model.ainvoke(messages)
    return {"messages": [response]}


# Add more nodes here as the graph grows:
# async def retrieval_node(state: dict) -> dict: ...
# async def validation_node(state: dict) -> dict: ...
