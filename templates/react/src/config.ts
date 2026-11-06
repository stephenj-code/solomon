/**
 * config.ts — settings.
 *
 * All constants and environment values in one place.
 * VITE_ prefix required for Vite to expose env vars to the browser.
 */
export const config = {
  appName: "__APP_NAME__",
  apiUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  // Set VITE_AGENT_URL to connect AgentChat to a LangGraph agent's /v1/agui endpoint.
  // Example: https://my-agent.project-solomon.ai
  // Leave empty if this UI has no agent backend.
  agentUrl: import.meta.env.VITE_AGENT_URL ?? "",
};
