"""
handlers.py — logic for HTTP endpoints.

Bridges the FastAPI layer to the LangGraph agent.
Handlers create a thread ID if none given, invoke the graph, return results.
"""
import uuid
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.config import settings
from app.models import InvokeRequest, InvokeResponse, HealthResponse, StreamRequest
from app.agent.graph import build_graph

# Single compiled graph instance (checkpointer wired in main.py)
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.version)


async def invoke(body: InvokeRequest) -> InvokeResponse:
    thread_id = body.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    try:
        result = await get_graph().ainvoke(
            {"messages": [HumanMessage(content=body.message)]},
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    last_message = result["messages"][-1]
    return InvokeResponse(thread_id=thread_id, response=last_message.content)


async def stream(body: StreamRequest):
    thread_id = body.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    async def event_stream():
        async for chunk in get_graph().astream(
            {"messages": [HumanMessage(content=body.message)]},
            config=config,
            stream_mode="messages",
        ):
            if chunk[1].get("langgraph_node") == "agent":
                content = chunk[0].content
                if content:
                    yield f"data: {content}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
