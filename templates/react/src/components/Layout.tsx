/**
 * Layout.tsx — shared shell.
 *
 * Wraps every page. Contains the nav bar and the content area.
 * Add nav links here when you add new pages.
 */
import { NavLink, Outlet } from "react-router-dom";
import { config } from "../config";

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6">
        <span className="font-semibold text-gray-900">{config.appName}</span>
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            isActive ? "text-indigo-600 text-sm font-medium" : "text-gray-500 text-sm hover:text-gray-900"
          }
        >
          Home
        </NavLink>
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            isActive ? "text-indigo-600 text-sm font-medium" : "text-gray-500 text-sm hover:text-gray-900"
          }
        >
          Dashboard
        </NavLink>
        {/* Add nav links here when adding new pages */}
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <Outlet />  {/* current page renders here */}
      </main>
    </div>
  );
}
