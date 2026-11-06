"""
state.py — data.

Defines what flows through the graph at every step.
Every node reads from and writes to this TypedDict.

Add a new field here when a node needs to pass data to a downstream node.
All fields should have a default so the graph can start with minimal input.
"""
from typing import Annotated
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # messages accumulates the conversation — add_messages merges new messages in
    messages: Annotated[list, add_messages]

    # Add fields your nodes need to share:
    # result: str           # a computed result to pass forward
    # context: list[str]   # retrieved documents
    # step: int            # which step we're on
