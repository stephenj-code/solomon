/**
 * AgentChat.tsx — AG-UI chat component.
 *
 * Connects to a LangGraph agent's POST /v1/agui endpoint and renders the
 * response in real time: text tokens stream in token by token, tool calls
 * appear as they start and disappear when they finish.
 *
 * Usage:
 *   import { AgentChat } from "../components/AgentChat";
 *   <AgentChat agentUrl={config.agentUrl} />
 *
 * The agentUrl should point at the agent's root URL.
 * Set VITE_AGENT_URL in your .env to configure it.
 *
 * AG-UI Protocol — this component reads these SSE event types:
 *   RUN_STARTED / RUN_FINISHED / RUN_ERROR
 *   TEXT_MESSAGE_START / TEXT_MESSAGE_CONTENT / TEXT_MESSAGE_END
 *   TOOL_CALL_START / TOOL_CALL_ARGS / TOOL_CALL_END
 */
import { useRef, useState } from "react";
import type { ChatMessage, ToolCall } from "../types";

interface Props {
  agentUrl: string;
}

export function AgentChat({ agentUrl }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  // thread_id persists for the lifetime of this component — same conversation
  const threadId = useRef(crypto.randomUUID());

  async function send() {
    if (!input.trim() || streaming) return;
    const userText = input.trim();
    setInput("");
    setStreaming(true);

    // Add the user's message immediately
    const userId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: userText },
    ]);

    // Placeholder for the assistant reply — content fills in as tokens arrive
    const assistantId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "", toolCalls: [] },
    ]);

    try {
      const res = await fetch(`${agentUrl}/v1/agui`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userText,
          thread_id: threadId.current,
        }),
      });

      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Accumulate into buffer — a single chunk may contain multiple events
        // or an event may be split across chunks
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop()!; // last item is incomplete — keep for next chunk

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let event: Record<string, string>;
          try {
            event = JSON.parse(raw);
          } catch {
            continue;
          }

          switch (event.type) {
            case "TEXT_MESSAGE_CONTENT":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + event.delta }
                    : m
                )
              );
              break;

            case "TOOL_CALL_START": {
              const tc: ToolCall = {
                id: event.tool_call_id,
                name: event.tool_call_name,
                status: "running",
              };
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, toolCalls: [...(m.toolCalls ?? []), tc] }
                    : m
                )
              );
              break;
            }

            case "TOOL_CALL_END":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: (m.toolCalls ?? []).map((tc) =>
                          tc.id === event.tool_call_id
                            ? { ...tc, status: "done" }
                            : tc
                        ),
                      }
                    : m
                )
              );
              break;

            case "RUN_ERROR":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: `Error: ${event.message}` }
                    : m
                )
              );
              break;
          }
        }
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `Failed to reach agent: ${String(err)}` }
            : m
        )
      );
    }

    setStreaming(false);
  }

  if (!agentUrl) {
    return (
      <p className="text-sm text-gray-400 p-4">
        Set <code>VITE_AGENT_URL</code> to connect to an agent.
      </p>
    );
  }

  return (
    <div className="flex flex-col h-full border border-gray-200 rounded-xl overflow-hidden">
      {/* Message history */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <p className="text-sm text-gray-400 text-center pt-8">
            Start a conversation.
          </p>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-xl px-4 py-2 text-sm whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {/* Tool calls shown above the text while they're running */}
              {(m.toolCalls ?? [])
                .filter((tc) => tc.status === "running")
                .map((tc) => (
                  <div
                    key={tc.id}
                    className="text-xs text-gray-500 mb-1 flex items-center gap-1"
                  >
                    <span className="animate-spin">⟳</span>
                    <span>{tc.name}…</span>
                  </div>
                ))}
              {m.content || (m.role === "assistant" && streaming ? "▌" : "")}
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          disabled={streaming}
          placeholder="Message…"
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={streaming || !input.trim()}
          className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium disabled:opacity-50 hover:bg-blue-700"
        >
          Send
        </button>
      </div>
    </div>
  );
}
