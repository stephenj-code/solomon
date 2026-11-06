# __APP_NAME__ — Agent Template

LangGraph agent with FastAPI wrapper. Five files, one job each.

## File map

| File | Job | Add here when you need to... |
|------|-----|------------------------------|
| `agent/graph.py` | Structure — nodes and edges wired together | Add a new step or change the flow |
| `agent/nodes.py` | Logic — what each node does | Add a new reasoning step |
| `agent/state.py` | Data — what flows through the graph | Add a new piece of shared state |
| `agent/tools.py` | Capabilities — what the agent can call | Add a new tool |
| `agent/prompts.py` | Instructions — system prompts | Change how the agent behaves |
| `routes.py` | HTTP API map | Add a new endpoint |
| `handlers.py` | HTTP logic | Add a new request handler |
| `models.py` | HTTP data shapes | Add a new request/response type |

## Adding a new tool (always this order)

1. **tools.py** — write the `@tool` function with a clear description
2. **tools.py** — add it to the `tools = [...]` list at the bottom
3. That's it. The graph automatically binds all tools in the list to the model.

## Adding a new node (always this order)

1. **state.py** — add any new fields the node needs to read or write
2. **nodes.py** — write the async node function
3. **graph.py** — add `graph.add_node("name", node_fn)` and wire edges

## Model selection

Set `LITELLM_MODEL` env var to choose the model tier:
- `smart` — Muse Glimmer 30B local, best for reasoning and long context
- `fast` — Nemotron Nano local, best for routing, classification, quick calls
- `external` — Claude Sonnet via Anthropic, highest quality ceiling

## Thread/conversation continuity

Pass the same `thread_id` in `/v1/invoke` or `/v1/stream` to continue a conversation.
LangGraph checkpoints state to Postgres — conversations survive restarts.
Omit `thread_id` to start a new conversation.

## Streaming

`POST /v1/stream` returns Server-Sent Events. Each `data:` line is a token chunk.
`data: [DONE]` signals the end of the stream.

## AG-UI (agent + UI)

`POST /v1/agui` streams typed SSE events that a React UI can render in real time.
Use this endpoint instead of `/v1/stream` when the agent has a UI.

Event types emitted:
```
RUN_STARTED          → run begins
TEXT_MESSAGE_START   → assistant message starts
TEXT_MESSAGE_CONTENT → one token delta (stream into the message)
TEXT_MESSAGE_END     → assistant message complete
TOOL_CALL_START      → a tool is being called (name visible to UI)
TOOL_CALL_ARGS       → the arguments being passed to the tool
TOOL_CALL_END        → tool returned
RUN_FINISHED         → run complete
RUN_ERROR            → something failed
```

The React template's `AgentChat` component consumes this endpoint automatically.
No new dependencies — `astream_events` is already in `langchain-core`.

## Agent-to-agent calls

Call another agent by adding it as an HTTP tool:
```python
@tool
def call_other_agent(message: str) -> str:
    """Delegate to the other-agent service."""
    import httpx
    r = httpx.post("http://other-agent.other-ns.svc.cluster.local:8000/v1/invoke",
                   json={"message": message}, timeout=30)
    r.raise_for_status()
    return r.json()["response"]
```
Istio handles mTLS. Add a SPIFFE allow rule in `infrastructure/other-ns/istio/` if
the target namespace is deny-by-default (`ai`, `auth`, `mcp-servers`).
