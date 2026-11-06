/**
 * routes.tsx — structure.
 *
 * The full map of this app. Read this file to see every page and its URL.
 * Add a new entry here when adding a new page.
 *
 * Pattern:
 *   1. Create the page component in pages/
 *   2. Import it here
 *   3. Add a <Route> inside the Layout route
 *   4. Add a <NavLink> in components/Layout.tsx
 */
import { createBrowserRouter } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,   // Layout wraps all pages
    children: [
      { index: true, element: <Home /> },           // /
      { path: "dashboard", element: <Dashboard /> }, // /dashboard
      // Add new pages here:
      // { path: "results", element: <Results /> },
    ],
  },
]);
