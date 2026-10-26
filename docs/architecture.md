# Architecture

```
Browser (React + Vite + Tailwind)
   │  HTTPS: /api/v1/*  (session cookie + X-CSRF-Token)
   │  Socket.IO: /socket.io/ (same cookie)
   ▼
FastAPI app wrapped by socketio.ASGIApp  (one process, one port)
   ├── api/routes/*        HTTP layer: validation (Pydantic), auth, CSRF, status codes
   ├── websocket/          Socket.IO auth, per-user rooms, message:send handler
   ├── services/*          application logic + persistence (Motor)
   │     ├── embedding_store   versioned embedding cache (Mongo)
   │     └── recommendations   documents → domain objects → engine → response
   ├── domain/*            PURE scoring engine (no I/O), paper Eqs. 1–6
   └── research/*          PURE offline evaluation pipeline + CLI
   ▼
MongoDB (Atlas in production; mongomock in tests and demos)   Redis (optional)
```

## Why this structure

- **Pure domain.** `domain/` and `research/` import neither FastAPI nor Mongo. You can test and reproduce them with plain Python, and later move them into a separate ML service without rewriting anything.
- **The ML runs in-process.** Sentence-BERT (`all-MiniLM-L6-v2`, 384 dimensions, used as provided) loads lazily and is warmed up in a background thread at startup. Encoding runs in a worker thread so the event loop isn't blocked.
- **No vector database.** Recommendation scores the whole visible pool (capped at 2,000) against cached embeddings. Measured on a laptop CPU with a pool of about 24 candidates (see `research/reports/`): median 9 ms per request with cached embeddings, 349 ms when every profile has to be encoded. Database time is excluded. If the pool grows large, measure first, then consider an ANN index.
- **No cached recommendations.** Results depend on team membership, every candidate profile, the requirements, the weights and the model version. Recomputing on demand is cheap once embeddings are cached.

## Data model (MongoDB collections)

| Collection | Key fields | Indexes |
|---|---|---|
| `users` | email, password_hash (scrypt), display_name, handle/handle_key, role, consent | unique email, unique handle_key |
| `sessions` | `_id` = SHA-256(token), user_id, csrf_token, expires_at | TTL on expires_at, user_id |
| `profiles` | `_id` = user id, skills[{label (canonical), proficiency, kind, recognized}], declared_absent, roles, interests, projects, availability (null = not stated), weekly_hours, work_mode, visible, text | visible |
| `embeddings` | user_id, model_id, text_hash (template version + text), dim, vector | unique (user_id, model_id) |
| `projects` | owner_id, requirements[], target_size, members[], open_positions, vacant_roles, rules, history[], version, embedding{model_id, text_hash, vector} | owner_id; status+type+created; members.user_id; event_key |
| `invitations` | project_id, kind (invite/request), from_user, candidate_id, role, status, reason | partial unique (project_id, candidate_id) where pending |
| `conversations` | kind (direct/team), participant_ids, direct_key, project_id, reads{user: ts} | participant_ids + last_message_at; unique direct_key |
| `messages` | conversation_id, sender_id, body, client_id | (conversation_id, created_at); unique (conversation, sender, client_id) for idempotent sends |
| `research_scenarios` | raw scenario JSON, provenance, packet (rater view), packet_key (coordinator only) | provenance |
| `judgments` | scenario_id, candidate_id, rater_id, rating | unique (scenario, candidate, rater) |
| `evaluation_runs` | state, report JSON, markdown, is_research_evidence | created_at |

All timestamps are stored in UTC and shown in local time in the browser.

## Concurrency: team size can't be exceeded

Joining is a single conditional `find_one_and_update` on the project document, which MongoDB applies atomically:

```
{_id, status: "open", open_positions: {$gt: 0}, members.user_id: {$ne: c}}
  → $inc open_positions −1, $push member
```

Before that, the invitation is claimed (`pending → accepting`). If the join matches nothing, the invitation is marked `expired / team_full_or_closed`; this is the compensating step. Edits use optimistic concurrency on `version` and the member count.

`tests/integration/test_projects_teams.py::test_concurrent_acceptance_cannot_exceed_target` races four acceptances for one place: exactly one wins.

## Realtime

Socket.IO authenticates using the session cookie and checks the Origin header against the allowlist. Each socket joins only `user:<id>`. Messages are stored in MongoDB first; the socket only notifies. Sends are idempotent through `client_id`.

With more than one instance, set `REDIS_URL` so the Socket.IO Redis manager fans events out across instances.
