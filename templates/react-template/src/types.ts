/**
 * types.ts — data shapes.
 *
 * All TypeScript interfaces and types defined here.
 * Import from here in pages and components — never define types inline.
 *
 * Mirrors the response shapes from the backend API.
 */

export interface HealthResponse {
  status: string;
  version: string;
}

export interface DashboardStats {
  label: string;
  value: number;
}

// Add your domain types below:
// export interface Item {
//   id: string;
//   name: string;
//   value: number;
//   createdAt: string;
// }
