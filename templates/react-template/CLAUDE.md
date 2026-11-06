# __APP_NAME__ — React Template

Vite + React + TypeScript. Five files, one job each.

## File map

| File | Job | Add here when you need to... |
|------|-----|------------------------------|
| `src/routes.tsx` | Structure — every page and its URL in one place | Add a new page |
| `src/pages/` | Logic — what each page shows and does | Create a new page component |
| `src/types.ts` | Data — all TypeScript interfaces | Add a new data shape |
| `src/api.ts` | Capabilities — all backend fetch calls | Add a new API call |
| `src/config.ts` | Config — constants and env vars | Add a new setting |
| `src/components/` | Shared UI pieces | Add a reusable component |

## Adding a new page (always this order)

1. **types.ts** — add any new data types the page needs
2. **api.ts** — add the fetch function(s) the page will call
3. **pages/MyPage.tsx** — create the page component
4. **routes.tsx** — add `{ path: "my-page", element: <MyPage /> }`
5. **components/Layout.tsx** — add a `<NavLink to="/my-page">` in the nav

## React concepts for reference

- **Component** — a function that returns JSX (HTML-like syntax). Takes props, renders UI.
- **useState** — remembers a value that can change. When it changes, the component re-renders.
- **useEffect** — runs code after render (e.g. fetch data when the page loads).
- **props** — data passed from parent to child component, like function arguments.

```tsx
// Minimal page pattern
import { useEffect, useState } from "react";
import { api } from "../api";
import type { MyType } from "../types";

export default function MyPage() {
  const [data, setData] = useState<MyType | null>(null);

  useEffect(() => {
    api.getMyData().then(setData);
  }, []); // [] means "run once when page loads"

  if (!data) return <p>Loading...</p>;
  return <div>{data.name}</div>;
}
```

## Styling

Uses Tailwind CSS — utility classes directly on elements.
Common classes:
- Layout: `flex`, `grid`, `gap-4`, `p-6`, `mx-auto`, `max-w-6xl`
- Text: `text-sm`, `text-gray-500`, `font-semibold`
- Box: `bg-white`, `rounded-xl`, `border`, `border-gray-200`

## TypeScript quick reference

- `interface` — defines the shape of an object
- `string | null` — value is either a string or null
- `<T>` — generic, means "this works for any type T"
- Non-null assertion `!` — tells TypeScript "I know this is not null"
