# Deployment (Vercel + Render + MongoDB Atlas)

> **Neon is PostgreSQL, not MongoDB**, so don't use it here. Use **MongoDB Atlas** (or any MongoDB-compatible managed service).

## 1. MongoDB Atlas
1. Create a cluster and a database user, and allow Render's egress IPs (or 0.0.0.0/0 together with a strong password).
2. Copy the `mongodb+srv://…` URL. Indexes are created automatically at startup.

## 2. Backend on Render
- Use the blueprint `render.yaml` (Docker, `backend/Dockerfile`). The image bakes in CPU-only torch and the MiniLM model.
- Set these environment variables:
  - `MONGODB_URL`
  - `CORS_ORIGINS`: your frontend origin
  - `ADMIN_EMAILS`
  - optionally `REDIS_URL`
- Health checks:
  - `/api/v1/health` is liveness.
  - `/api/v1/health/ready` is readiness (database ping, encoder status).
- **Memory:** torch plus MiniLM needs roughly 500–700 MB of RAM, so use an instance with at least 1 GB. The free 512 MB tier is too small for `EMBEDDING_BACKEND=sbert`.
- **Instances:** run one instance unless `REDIS_URL` is set. Several instances also need sticky sessions for Socket.IO long-polling.

## 3. Frontend on Vercel
- Root directory `frontend`, build `npm run build`, output `dist`.

## 4. Choosing how to share the session cookie (important)

Vercel and Render are different sites. A cookie set by `*.onrender.com` and sent from `*.vercel.app` is a **third-party cookie**, which browsers block more and more. Use one of these two set-ups:

**A. Proxy through Vercel (simplest, no custom domain).**
- `frontend/vercel.json` rewrites `/api/*` and `/socket.io/*` to Render. Set the Render host there.
- The browser only talks to the Vercel origin, so the cookie is first-party: keep `COOKIE_SAMESITE=lax` and `COOKIE_SECURE=true`, and set `CORS_ORIGINS=https://<your-app>.vercel.app`.
- Vercel rewrites don't support WebSockets. Build the frontend with `VITE_SOCKET_TRANSPORTS=polling` (Socket.IO falls back to HTTP long-polling). Messaging still works, with slightly higher latency.

**B. Same-site custom domains (recommended for production).**
- Serve the frontend at `app.example.com` (Vercel) and the API at `api.example.com` (Render).
- Backend: `COOKIE_DOMAIN=.example.com`, `COOKIE_SAMESITE=lax`, `COOKIE_SECURE=true`, `CORS_ORIGINS=https://app.example.com`.
- Frontend: `VITE_API_BASE=https://api.example.com` and `VITE_SOCKET_URL=https://api.example.com`. WebSockets work directly.

**Test the chosen set-up in a real browser** after deploying: sign in, reload, send a message. That confirms the cookie survives under your exact origins.

## 5. After the first deploy
- Register with an e-mail listed in `ADMIN_EMAILS` to get the research-admin role.
- Never set `SEED_DEMO=1` in production. Startup rejects the in-memory DB and non-secure cookies in production anyway.
