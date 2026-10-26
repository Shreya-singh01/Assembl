# API overview

The full, always-current schema is the generated OpenAPI document: run the backend and open **`/api/docs`**.

## Conventions
- All routes sit under `/api/v1`.
- JSON bodies are validated strictly; unknown fields give 422.
- "Auth" means a session cookie is required. Requests that change state also need `X-CSRF-Token`.
- Errors look like `{"detail": "..."}`, and validation errors add `errors: [{loc, msg}]`.
- Resources you're not allowed to see return 404, not 403.

## Auth: `/auth`
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/register` | – | 201 `{user, csrf_token}`; sets the cookie. 409 if the e-mail or handle is taken. 429 when rate-limited. |
| POST | `/auth/login` | – | 401 on bad credentials, 429 when rate-limited. Rotates the session. |
| POST | `/auth/logout` | ✓ | 204 |
| GET | `/auth/me` | ✓ | `{user, csrf_token}` |
| PUT | `/auth/consent` | ✓ | Research participation opt-in. |
| POST | `/auth/delete-account` | ✓ | `{password, confirm: "DELETE"}` → 204 |

## Profiles: `/profiles`
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/profiles/me` | ✓ | Your profile plus completion. |
| PUT | `/profiles/me` | ✓ | Returns the normalised profile and the alias decisions applied. |
| GET | `/profiles/vocabulary` | – | Canonical skills, proficiency anchors, suggested roles. |
| GET | `/profiles/{id}` | ✓ | Public view (never e-mail or slots). 404 if hidden, unless you share a team. |

## Projects and teams: `/projects`
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/projects` | optional | Filters `q`, `opportunity_type`, `skill`, `status`, `mine`; paginated with `limit`/`offset`. |
| POST | `/projects` | ✓ | 201. The creator becomes a member. |
| GET | `/projects/{id}` | optional | Includes `viewer` (your relationship to the project). |
| PUT | `/projects/{id}` | owner | Must send the current `version`; 409 if stale. |
| GET | `/projects/{id}/coverage` | ✓ | Per-requirement coverage and the weighted overall (Eqs. 2–3). |
| GET | `/projects/{id}/recommendations` | owner | Ranked candidates with features, contributions, structured and text explanations, pool summary, omitted features, active weights. |
| POST | `/projects/{id}/invitations` | owner | `{candidate_id, role?, message?}` |
| POST | `/projects/{id}/invitations/by-handle` | owner | Invite existing teammates. |
| POST | `/projects/{id}/join-requests` | ✓ | |
| GET | `/projects/{id}/invitations` | owner | |
| DELETE | `/projects/{id}/members/{uid}` | owner, or the member themselves | Removes a member, or lets them leave. |
| GET | `/projects/{id}/history` | member | Membership change history. |

## Invitations: `/invitations`
- `GET ?box=received|sent&status=` lists them.
- `POST /{id}/accept`, `POST /{id}/decline` and `POST /{id}/cancel` respond. A 409 means the team is full, the invitation was already answered, or the student is on another team for the same event.

## Conversations: `/conversations`
- `GET` lists conversations with unread counts. `POST {user_id}` gets or creates a direct conversation.
- `GET /{id}/messages?before=&limit=` returns history. `POST /{id}/messages {body, client_id?}` sends (429 when rate-limited). `POST /{id}/read` marks it read.

**Socket.IO** (path `/socket.io`, same cookie):
- Client to server: `message:send {conversation_id, body, client_id}`, acknowledged with `{ok, message|error}`; and `conversation:read`.
- Server to client: `message:new`, `invitation:new`, `invitation:update`, `team:update`.

## Research: `/research`
- **Any signed-in user:** `GET /status`, `GET /runs`, `GET /runs/{id}`.
- **Admin:**
  - `POST /evaluate` returns 202.
  - `GET /scenarios`.
  - `POST /scenarios/import` takes a list of scenario JSON objects.
  - `POST /scenarios/synthetic`.
  - `POST /scenarios/{id}/packet` builds a rating packet.
  - `POST /raters/{uid}` grants the rater role.
- **Rater:** `GET /judging/tasks`, `GET /judging/{scenario}` (anonymised, shuffled per rater), `POST /judging/{scenario} {ratings: {C01: 0..3}}`.

## Other
- `GET /dashboard` (auth required).
- `GET /health` and `GET /health/ready`.
