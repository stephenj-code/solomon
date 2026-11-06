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
