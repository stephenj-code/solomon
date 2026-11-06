/**
 * Home.tsx — the landing page.
 *
 * A page component receives no props from the router.
 * It fetches its own data and renders itself.
 */
import { config } from "../config";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <h1 className="text-4xl font-bold text-gray-900">{config.appName}</h1>
      <p className="text-gray-500 text-lg">Running on project-solomon</p>
    </div>
  );
}
