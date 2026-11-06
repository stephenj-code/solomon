/**
 * Dashboard.tsx — the main dashboard page.
 *
 * Shows a stat card grid and a simple line chart.
 * Replace mock data with real api.ts calls as the app grows.
 */
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { DashboardStats } from "../types";

// Replace with api.getStats() when the backend is ready
const mockStats: DashboardStats[] = [
  { label: "Runs", value: 42 },
  { label: "Tokens", value: 18400 },
  { label: "Errors", value: 1 },
  { label: "Avg ms", value: 320 },
];

const mockChart = [
  { time: "00:00", value: 10 },
  { time: "04:00", value: 18 },
  { time: "08:00", value: 35 },
  { time: "12:00", value: 42 },
  { time: "16:00", value: 29 },
  { time: "20:00", value: 51 },
];

function StatCard({ label, value }: DashboardStats) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-semibold text-gray-900 mt-1">{value.toLocaleString()}</p>
    </div>
  );
}

export default function Dashboard() {
  return (
    <div className="space-y-8">
      <h2 className="text-2xl font-semibold text-gray-900">Dashboard</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {mockStats.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      {/* Line chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <p className="text-sm font-medium text-gray-700 mb-4">Activity (24h)</p>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={mockChart}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="time" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
