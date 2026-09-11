# AgriN Twin — Dashboard

React + Vite dashboard for the AgriN Twin platform (Track 4: AgriN &
Regenerative Agricultural Intelligence, Build with AI: Code for
Communities — Second Edition, Team VIDYUT).

## Run locally

```bash
npm install
npm run dev
```

Requires the backend running at `http://localhost:8000` (see
`../backend/README.md`) — API calls are proxied from `/api/*` in dev
(`vite.config.js`). For a production build served separately from the
API, set an absolute API base URL in `src/lib/api.js` or serve both
behind the same reverse proxy.

```bash
npm run build   # outputs to dist/
npm run preview
```

## Design

See the token comment block at the top of `src/index.css` for the full
design rationale ("Field Ledger" system — soil/canopy/sky palette,
Fraunces + Space Grotesk type pairing, ledger-index layout instead of a
SaaS card grid).
