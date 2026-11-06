/**
 * api.ts — capabilities.
 *
 * All calls to the backend API live here.
 * Pages import functions from here — never use fetch() directly in a page.
 *
 * Pattern: one async function per API call, typed return value.
 * Throws an Error on non-2xx responses so callers can handle it.
 */
import { config } from "./config";
import type { HealthResponse } from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${config.apiUrl}${path}`, options);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  // Add domain calls below:
  // getItems: () => request<Item[]>("/v1/items"),
  // createItem: (body: { name: string; value: number }) =>
  //   request<Item>("/v1/items", {
  //     method: "POST",
  //     headers: { "Content-Type": "application/json" },
  //     body: JSON.stringify(body),
  //   }),
};
