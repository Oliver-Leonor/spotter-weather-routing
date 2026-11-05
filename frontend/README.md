# StormRoute frontend

React 19 + TypeScript + Vite + Tailwind CSS 4 + TanStack Query + MapLibre GL.

```bash
nvm use            # Node 24 (.nvmrc at the repo root)
npm install
npm run dev        # http://localhost:5173
npm test           # Vitest
npm run typecheck  # tsc -b
npm run lint       # oxlint
npm run build
```

Copy `.env.example` to `.env` and point `VITE_API_BASE_URL` at the Django backend.
