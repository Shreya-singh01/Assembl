# Security and privacy

## Authentication and sessions
- **Passwords:** scrypt from the standard library (N=2^15, r=8, p=1, 16-byte salt), with 10–128 characters required. Logins for unknown e-mails are timing-equalised.
- **Session tokens:** 256-bit random tokens in an **HttpOnly** cookie (`Secure` and `SameSite` are configurable). Only the token's SHA-256 is stored.
- **Expiry and logout:** sessions expire absolutely after `SESSION_TTL_HOURS`, enforced in code and by a Mongo TTL index. Logout deletes the session server-side.
- **Login rotates the session.**
- **Production guard:** startup **refuses** to run in production if `COOKIE_SECURE` is false or MongoDB is the in-memory mock.
- **No JWTs**, and nothing auth-related is kept in localStorage. The CSRF token lives only in memory.

## CSRF and origin checks
- **Synchroniser token:** every state-changing request needs the session's CSRF token in `X-CSRF-Token`, which `/auth/login` and `/auth/me` return.
- **Origin allowlist:** `OriginCheckMiddleware` rejects unsafe requests whose `Origin` isn't an allowed frontend origin.
- **CORS** is restricted to `CORS_ORIGINS`, with credentials allowed.
- **Socket.IO** checks Origin as well, which prevents cross-site WebSocket hijacking.

## Authorization
- **Server-side enforcement:** every resource is checked on the server. Ids supplied by the client are never trusted.
- **Unreadable resources look absent:** non-participants get **404** for conversations, private projects and hidden profiles, so ids can't be probed or enumerated. Malformed ids also return 404.
- **Owner-only actions:** only the creator can view recommendations, edit, invite or remove members. Invitations are accepted only by the counterparty.
- **Admin role:** `ADMIN_EMAILS` grants the admin role (research administration). Admins grant the rater role.

## Rate limits
- **Limits:** login per IP+e-mail (10 per 5 min), registration per IP, messages per user (30 per minute).
- **Backend:** Redis when configured; it falls back to in-process counters if Redis is unavailable (tested).

## Input and output
- **Validation:** strict Pydantic models (`extra=forbid`) with length limits. Messages are capped at 4,000 characters, payloads at 16 KB on sockets, and regex search input is escaped.
- **Output:** React escapes all output; no `dangerouslySetInnerHTML` is used.
- **Errors:** generic messages, with no stack traces in responses.
- **Logging:** JSON logs carry the method, route template, status, duration and request id. They never include passwords, tokens, e-mails or message bodies.

## Privacy
- **Ranking inputs:** names, e-mails, contact details and demographics are never ranking features, and demographics aren't collected.
- **Visibility:** profiles are hidden until the student turns on visibility. Other students never see weekly slots, only how many they share, and never see e-mails.
- **Research raters** see anonymised packets with no ids, names, method names or scores.
- **Account deletion** removes the account, sessions, profile, embeddings, invitations, owned projects, sent messages and direct conversations, and frees places on other teams (`services/account.py`).

## Cross-origin deployment
See `deployment.md`. The recommended setups keep the cookie **first-party**, so `SameSite=Lax` works. SameSite=None third-party cookies are blocked by Safari and increasingly by Chrome, so they aren't relied on.
