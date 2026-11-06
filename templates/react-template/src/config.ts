/**
 * config.ts — settings.
 *
 * All constants and environment values in one place.
 * VITE_ prefix required for Vite to expose env vars to the browser.
 */
export const config = {
  appName: "__APP_NAME__",
  apiUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
};
