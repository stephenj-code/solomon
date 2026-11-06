"""
handlers.py — logic for HTTP endpoints.

Bridges the FastAPI layer to the LangGraph agent.
Handlers create a thread ID if none given, invoke the graph, return results.
"""
import json
import uuid
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.config import settings
from app.models import AguiRequest, InvokeRequest, InvokeResponse, HealthResponse, StreamRequest
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


async def agui(body: AguiRequest):
    """
    AG-UI Protocol endpoint.

    Streams typed SSE events so a UI can render the agent's work in real time:
    text tokens as they arrive, tool calls as they start and finish.
    Use /v1/stream if you only need raw tokens.
    Use /v1/agui if you have a UI that needs to show tool activity.
    """
    thread_id = body.thread_id or str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    def _emit(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    async def event_stream():
        yield _emit({"type": "RUN_STARTED", "thread_id": thread_id, "run_id": run_id})
        yield _emit({"type": "TEXT_MESSAGE_START", "message_id": msg_id, "role": "assistant"})

        # tool_call_id keyed by LangGraph run_id so we can close it on tool_end
        active_tools: dict[str, str] = {}

        try:
            async for event in get_graph().astream_events(
                {"messages": [HumanMessage(content=body.message)]},
                config=config,
                version="v2",
            ):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield _emit({
                            "type": "TEXT_MESSAGE_CONTENT",
                            "message_id": msg_id,
                            "delta": chunk.content,
                        })

                elif kind == "on_tool_start":
                    tool_call_id = str(uuid.uuid4())
                    active_tools[event["run_id"]] = tool_call_id
                    yield _emit({
                        "type": "TOOL_CALL_START",
                        "tool_call_id": tool_call_id,
                        "tool_call_name": event["name"],
                        "parent_message_id": msg_id,
                    })
                    yield _emit({
                        "type": "TOOL_CALL_ARGS",
                        "tool_call_id": tool_call_id,
                        "delta": json.dumps(event["data"].get("input", {})),
                    })

                elif kind == "on_tool_end":
                    tool_call_id = active_tools.pop(event["run_id"], None)
                    if tool_call_id:
                        yield _emit({"type": "TOOL_CALL_END", "tool_call_id": tool_call_id})

        except Exception as exc:
            yield _emit({"type": "RUN_ERROR", "message": str(exc)})
            return

        yield _emit({"type": "TEXT_MESSAGE_END", "message_id": msg_id})
        yield _emit({"type": "RUN_FINISHED", "thread_id": thread_id, "run_id": run_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
