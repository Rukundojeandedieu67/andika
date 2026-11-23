# ANDIKA frontend

The reader, author, and administrator interfaces talk to the FastAPI API. Access tokens stay in memory. The refresh token is the HttpOnly `andika_refresh_token` cookie on `/api/v1/auth` and is never written to browser storage.

## Requirements

- Node.js 22 or newer
- The ANDIKA API running with PostgreSQL
- `CORS_ORIGINS` including the frontend origin, with credentials allowed. The development defaults already include `http://localhost:5173` and `http://127.0.0.1:5173`.
- `PUBLIC_APP_URL` set to the same origin so email links return to this app. Tokens stay in the URL fragment.

## Configure

```powershell
cd frontend
copy .env.example .env
npm install
```

`VITE_API_BASE_URL` is the API prefix. Development uses the same-origin path `/api/v1`. Vite proxies `/api` to `http://127.0.0.1:8000`.

## Run

```powershell
npm run dev
```

The app is served at http://localhost:5173.

| Command | Purpose |
|---|---|
| `npm run lint` | ESLint |
| `npm test` | Vitest |
| `npm run build` | Typecheck and production build |
| `npm run preview` | Serve the production build |

## Production

Serve the frontend and `/api` from the same origin. A reverse proxy should forward `/api` to the ANDIKA API without changing the path, and it should pass `Set-Cookie` through unchanged. Keep `VITE_API_BASE_URL=/api/v1` so the refresh cookie stays first-party and `SameSite=Strict`.

If the API must stay on a different origin, set `VITE_API_BASE_URL` to that absolute `/api/v1` URL at build time, list the site origin in `CORS_ORIGINS`, and allow credentials. Do not store the refresh token in browser storage, and do not change the backend cookie flags. Do not put secrets in frontend environment variables.
