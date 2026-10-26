# Assembl: complete walkthrough

Assembl is a working implementation of the paper *"Assembl: Team-Aware Candidate Recommendation Using Semantic Skill Matching and Complementarity"* (Shreya Kumari, Saiesha Mittal, Vidhi Arora).

Assembl helps a partly formed student team find its remaining members. It ranks candidates by what they would **add to the team as it currently stands**, not just by how well they match the project description. Every recommendation is explained using only the scoring inputs.

This document covers:
- every feature, and how it works underneath
- what is real and what is synthetic
- how sessions and tokens work
- what still has to be connected before going live
- what should be changed or improved

The `docs/` folder has deeper reference material, linked where relevant.

---

## Contents

0. [Status at a glance](#0-status-at-a-glance)
1. [Repository map](#1-repository-map)
2. [Running it locally](#2-running-it-locally)
3. [Feature walkthrough](#3-feature-walkthrough)
   1. [Registration and sign-in](#31-registration-and-sign-in)
   2. [Profile and onboarding](#32-profile-and-onboarding)
   3. [Skill normalisation (alias table)](#33-skill-normalisation-alias-table)
   4. [Dashboard](#34-dashboard)
   5. [Discovering projects](#35-discovering-projects)
   6. [Creating and editing a project (wizard)](#36-creating-and-editing-a-project-wizard)
   7. [Project page and team management](#37-project-page-and-team-management)
   8. [Invitations and join requests](#38-invitations-and-join-requests)
   9. [Recommendations (the core feature)](#39-recommendations-the-core-feature)
   10. [Explanations and the compare view](#310-explanations-and-the-compare-view)
   11. [Messaging (HTTP + Socket.IO)](#311-messaging-http--socketio)
   12. [Privacy, visibility and account deletion](#312-privacy-visibility-and-account-deletion)
   13. [Research dashboard, rating and evaluation](#313-research-dashboard-rating-and-evaluation)
   14. [Public pages](#314-public-pages)
4. [The scoring engine, step by step](#4-the-scoring-engine-step-by-step)
5. [Sessions, tokens and CSRF in detail](#5-sessions-tokens-and-csrf-in-detail)
6. [Other security controls](#6-other-security-controls)
7. [Data model](#7-data-model)
8. [What is real and what is synthetic](#8-what-is-real-and-what-is-synthetic)
9. [The research pipeline, and how to run the real study](#9-the-research-pipeline-and-how-to-run-the-real-study)
10. [Configuration reference (every environment variable)](#10-configuration-reference-every-environment-variable)
11. [What needs to be connected to go live](#11-what-needs-to-be-connected-to-go-live)
12. [Known gaps and changes to make](#12-known-gaps-and-changes-to-make)
13. [Tests](#13-tests)
14. [Troubleshooting](#14-troubleshooting)

---

## 0. Status at a glance

| Area | State | Evidence |
|---|---|---|
| Scoring engine (Eqs. 1–6, eligibility, explanations) | **Working, tested** | ~100 unit tests with hand-calculated values; metamorphic properties |
| Accounts, sessions, CSRF, rate limits | **Working, tested** | API tests (login, CSRF rejection, cross-origin rejection, rate limiting) |
| Profiles, skill aliases, completion | **Working, tested** | API tests + browser end-to-end test |
| Projects, wizard, discovery, editing | **Working, tested** | API tests + end-to-end test |
| Invitations, join requests, concurrency-safe joining | **Working, tested** | Test races 4 acceptances for 1 place: exactly 1 wins |
| Recommendations page, explanations, comparison | **Working, tested** | API, component and end-to-end tests |
| Real-time messaging (Socket.IO) | **Working, tested** | Real uvicorn + Socket.IO client test; end-to-end chat between two browsers |
| Research pipeline (M1–M5, metrics, calibration, ablations, robustness) | **Working, tested** | 20+ pipeline tests; full run with real SBERT |
| Rating workflow for human raters | **Working, tested** | API test of the full packet → rate → store flow |
| Real Sentence-BERT model | **Working** | Opt-in test + full evaluation run with `all-MiniLM-L6-v2` |
| Real MongoDB (Atlas or local server) | **Not yet tested** | All tests used an in-memory MongoDB substitute (mongomock) |
| Deployment (Vercel + Render + Atlas) | **Configured, not deployed** | `render.yaml`, `vercel.json`, `Dockerfile` written; never run in the cloud |
| Redis | **Optional; only the "Redis down" path is tested** | Rate limiter falls back to in-process counters |
| Research results | **None yet. Evaluation pending.** | The only report uses synthetic data and simulated ratings (§8) |

---

## 1. Repository map

```
Assembl/
├── README.md                     ← this file
├── .env.example                  every setting, with comments (§10)
├── render.yaml                   Render blueprint for the backend
├── backend/
│   ├── pyproject.toml            pinned Python dependencies (+ extras: ml, redis, dev)
│   ├── Dockerfile                production image (CPU torch, model baked in)
│   ├── app/
│   │   ├── main.py               builds the app: FastAPI + Socket.IO in one ASGI process
│   │   ├── seed.py               SYNTHETIC demo users/project (python -m app.seed)
│   │   ├── core/                 config, password hashing & tokens, rate limiting, logging, errors, JSON serialisation
│   │   ├── db/mongo.py           MongoDB client (real or in-memory) + all indexes
│   │   ├── domain/               PURE scoring engine (no web, no database)
│   │   │   ├── models.py         StudentProfile, Requirement, ProjectSpec, RecommendationRequest
│   │   │   ├── skills.py         alias registry  +  skill_aliases.json (the alias table)
│   │   │   ├── semantic.py       profile/project text templates, f_sem (Eq. 1)
│   │   │   ├── coverage.py       C_s, Coverage, G, f_gap (Eqs. 2–5)
│   │   │   ├── features.py       f_role, f_avail, f_work
│   │   │   ├── eligibility.py    mandatory filter with reason codes
│   │   │   ├── scoring.py        weights, renormalisation, tie-break (Eq. 6)
│   │   │   ├── explanations.py   structured + text explanations
│   │   │   ├── engine.py         rank_candidates(): the whole pipeline
│   │   │   └── parsing.py        dict → domain objects (applies aliases)
│   │   ├── services/             application logic + database access
│   │   │   ├── auth.py           accounts, sessions
│   │   │   ├── profiles.py       profile save/normalise/completion/public view
│   │   │   ├── projects.py       project create/edit/list/visibility
│   │   │   ├── teams.py          invitations, join requests, accept/leave/remove
│   │   │   ├── recommendations.py documents → engine → API response
│   │   │   ├── embeddings.py     SBERT encoder + non-semantic test encoder
│   │   │   ├── embedding_store.py cached, versioned embeddings in MongoDB
│   │   │   ├── messaging.py      conversations, messages, unread counts
│   │   │   ├── account.py        account deletion
│   │   │   └── research.py       scenarios, rating packets, evaluation runs
│   │   ├── api/routes/           HTTP endpoints (auth, profiles, projects, invitations, conversations, research, dashboard/health)
│   │   ├── api/deps.py           current user, CSRF check, role checks, Origin check middleware
│   │   ├── websocket/            Socket.IO server + notifier
│   │   ├── schemas/              request/response models (Pydantic)
│   │   └── research/             PURE offline evaluation pipeline + CLI
│   └── tests/                    unit/ (maths), research/ (pipeline), integration/ (API, sockets)
├── frontend/
│   ├── package.json              pinned JS dependencies
│   ├── vite.config.ts            dev proxy for /api and /socket.io; Vitest config
│   ├── vercel.json               rewrites to the backend (EDIT THE HOST, §11)
│   ├── playwright.config.ts      browser end-to-end tests
│   ├── e2e/journey.spec.ts       the full user journey in a real browser
│   └── src/
│       ├── api/                  fetch client (CSRF, cookies) + TypeScript types
│       ├── app/                  routes, auth context, socket context
│       ├── layouts/              navigation shell
│       ├── components/ui/        buttons, forms, dialogs, badges, meters, empty/loading/error states
│       ├── pages/                landing, dashboard, how-it-works, privacy, 404
│       ├── features/             auth, profiles, projects, teams, recommendations, messaging, research
│       └── test/                 Vitest component and journey tests
├── research/
│   ├── README.md                 scenario format, CLI
│   ├── scenarios/synthetic/      30 SYNTHETIC scenarios with SIMULATED ratings
│   ├── scenarios/real/           empty: real, consent-based scenarios go here
│   └── reports/<run_id>/         report.md, run.json, split_manifest.json
└── docs/                         architecture, research methodology, API, security, deployment
```

**Design rule:** `backend/app/domain/` and `backend/app/research/` never import FastAPI or MongoDB. The paper's mathematics can be tested and reproduced on its own, and could later be moved into a separate machine-learning service without rewriting.

---

## 2. Running it locally

### Requirements
- Python 3.10 or newer
- Node 20 or newer
- About 1.5 GB of disk for torch and the model
- No MongoDB installation needed for a demo

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate                 # Windows (Git Bash: source .venv/Scripts/activate); macOS/Linux: source .venv/bin/activate
pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[ml,dev]"
```

Start it with demo data and the in-memory database:

```bash
SEED_DEMO=1 MONGODB_URL=memory:// uvicorn app.main:app --port 8000
```

In PowerShell, set the variables first:

```powershell
$env:SEED_DEMO="1"; $env:MONGODB_URL="memory://"; uvicorn app.main:app --port 8000
```

- **Model download:** the first start downloads `sentence-transformers/all-MiniLM-L6-v2` (about 90 MB) unless it is already in your Hugging Face cache.
- **Fast/offline mode:** set `EMBEDDING_BACKEND=hashing` for a fast, offline start. That encoder is **not semantic**, so its rankings are not the real method.
- **API docs (OpenAPI):** http://127.0.0.1:8000/api/docs
- **Health checks:** `/api/v1/health` and `/api/v1/health/ready`

### Frontend

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173
```

Vite proxies `/api` and `/socket.io` to `127.0.0.1:8000`, so the browser sees a single origin. To point the proxy elsewhere, set `VITE_DEV_BACKEND`.

### Demo accounts (synthetic)

`SEED_DEMO=1` creates:
- **24 synthetic students**, named like "Aarav (demo)", with handles like `aarav_demo0` and e-mails like `aarav_demo0@demo.assembl.example`.
- **One recruiting team**, "Placement-prep platform (demo)":
  - owned by Aarav (demo), with Kabir (demo) as the second member
  - 5 requirements, vacant roles Backend and Designer

All demo accounts share the password **`demo-password-123`**. Sign in as `aarav_demo0@demo.assembl.example` to see recommendations for the demo team.

### The in-memory database loses everything on restart

`MONGODB_URL=memory://` is a mock that lives inside the backend process. Restarting it erases all accounts, projects and messages.

For persistent local data:
1. Run a MongoDB server (for example `docker run -p 27017:27017 mongo:7`).
2. Set `MONGODB_URL=mongodb://localhost:27017`.
3. Optionally seed it with `python -m app.seed`.

### Becoming an admin locally

Set `ADMIN_EMAILS=you@example.edu` before you **register** that address. The role is assigned only at registration (see §12, item A3).

---

## 3. Feature walkthrough

Each feature is described in four parts: what the user does, what happens underneath, its limits, and how it is tested.

### 3.1 Registration and sign-in

**User:**
- The landing page leads to **Create an account**.
- The form asks for a display name, a handle, an e-mail, a password, and a data-use consent checkbox.
- After registering, the user goes straight to profile setup.

**Underneath** (`POST /api/v1/auth/register`, `services/auth.py`):
- **Validation:**
  - e-mail must be valid; reserved test domains such as `.invalid` are rejected
  - password 10–128 characters
  - handle matches `^[a-zA-Z0-9_]{3,24}$`
  - display name 1–60 characters
  - `accept_terms` must be true
- **Uniqueness:** e-mail (lower-cased) and handle (case-insensitive, via `handle_key`) are both checked in code and by unique indexes. Duplicates get **409**.
- **Password storage:** hashed with scrypt (§5).
- **Role:** `admin` if the e-mail is listed in `ADMIN_EMAILS`, otherwise `student`.
- **Session:** a session is created and the cookie set, exactly as at sign-in (§5).
- **Rate limit:** 20 registrations per hour per IP address.

**Sign-in** (`POST /auth/login`):
- **Wrong password or unknown e-mail:** both get the same **401** message.
- **Unknown e-mails** still run a dummy password check, so response timing does not reveal which e-mails exist.
- **Rate limit:** 10 attempts per 5 minutes per IP + e-mail pair, then **429**.
- **Session rotation:** a successful sign-in deletes any session the browser already had and issues a new one.
- **Redirect:** to where the user was going, otherwise to the dashboard (profile complete) or profile setup (incomplete).

**Sign-out** (`POST /auth/logout`): deletes the session in the database and clears the cookie.

**Tested:** registration, duplicates, weak passwords, wrong passwords, rate limiting, cookie flags, CSRF and protected routes (`tests/integration/test_auth_profiles.py`). The browser test also registers a fresh user.

### 3.2 Profile and onboarding

**User:** `/profile`, shown as "Set up your profile" right after registration. It has five sections, each explaining why the information is collected:

1. **Skills**
   - Rows of skill, proficiency and type (technical or non-technical); up to 40 skills.
   - Proficiency uses the paper's anchored scale: 1 learning/tutorial · 2 used in one project · 3 several projects or could lead · 4 advanced, can guide others.
   - Skill names autocomplete from the canonical list.
   - Optional "Skills I explicitly do not have" list. This is how a student states an explicit "none" rather than leaving a skill unmentioned.
2. **Roles and interests**
   - Primary roles (up to 3), secondary roles (up to 5), domain interests (up to 15).
   - Previous projects (up to 8), each with a title, summary, own contribution and an optional link. Links are shown but **never scored**, as in the paper.
3. **About you:** year of study (1–6, or not stated) and branch.
4. **Working together**
   - A weekly availability grid: 7 days × morning/afternoon/evening = 21 slots, stored as `mon-am`, `tue-eve` and so on.
   - Hours per week (1–40) and working mode (online, in person, hybrid).
   - Availability has an explicit **"Prefer not to say for now"** option. That stores `null` (not stated), which is different from marking no slots (`[]`, "stated: none").
5. **Visibility:** "Show my profile to teams looking for members". **Off by default.** This toggle is the student's explicit opt-in to being recommended.

A completion meter tracks seven items: skills, roles, year and branch, interests or projects, availability, hours, and mode. The profile counts as "ready for matching" once at least one skill is stated.

**Underneath** (`PUT /api/v1/profiles/me`, `services/profiles.py`):
- Every skill label passes through the alias table (§3.3). Duplicates merge, keeping the **highest** stated proficiency.
- The response lists every normalisation applied. The UI shows them, for example "“nodejs” → Node.js", and lists labels kept as written.
- Roles are de-duplicated case-insensitively, and a role cannot be both primary and secondary.
- The **profile text** used for semantic matching is rebuilt and stored: skills + interests + roles + project summaries. Proficiency numbers are deliberately excluded (paper §4.2).
- Cached embeddings computed from older text are deleted (§3.9).

**Public view** (`GET /profiles/{id}`), seen by other signed-in students:
- **Shown:** skills, levels, roles, year/branch, interests, projects, hours, mode, and *whether* availability was stated.
- **Never shown:** e-mail and the actual weekly slots.
- **Hidden profiles** return 404, except to people on the same team.

**Tested:** normalisation and merging, unknown versus absent, validation (out-of-range proficiency, bad slot names, unknown fields), hidden-profile access, and the public view leaking nothing.

### 3.3 Skill normalisation (alias table)

**File:** `backend/app/domain/skill_aliases.json`: about 80 canonical skills, each with explicit spelling variants.

**Matching order** (`domain/skills.py`):
1. **Exact:** case- and whitespace-insensitive match on a canonical name.
2. **Alias:** the same match on a listed alias (`nodejs`, `node js` and `node` → **Node.js**; `postgres` → **PostgreSQL**).
3. **Compact:** the same again after removing spaces, dots, hyphens and underscores (`React-Native` → **React Native**).
4. **Otherwise unrecognised:** the label is kept as typed (whitespace tidied) and flagged `recognized: false`.

**Safety:**
- No fuzzy matching. "React" and "React Native", "Python" and "Django", "Java" and "JavaScript", and C, C++ and C# all stay separate.
- When the table loads, the code refuses ambiguous aliases and any compact form that would merge two different skills.

**To add a skill or alias:** edit the JSON and restart. There is no admin screen for this yet (§12).

**Tested:** every rule above, plus a robustness check that rewriting all skills with aliases leaves rankings identical.

### 3.4 Dashboard

**User:** `/dashboard`, built from one call to `GET /api/v1/dashboard`. Only real data is shown; every empty state is honest.

**Main column:**
- **Profile alert:** appears if the profile has no skills or is hidden.
- **Invitations waiting for you:** accept or decline in place.
- **Your teams:** member count, open places, and a **Find members** button for teams you created.
- **Projects related to your profile:** up to 5 open public projects you're not on, ordered by **semantic relevance only** (`f_sem` between your profile and each project). The page labels this clearly: it is a discovery convenience, not the team-aware ranking.

**Side column:**
- Profile completion with the missing items listed.
- The 5 most recent conversations with unread counts.
- Requests you sent, with their status.

**Note:** the suggestion list considers the 30 newest open projects. The first time a project is scored, its text is embedded, which can make the first dashboard load slow (§12, item C7).

### 3.5 Discovering projects

**User:** `/projects` has a search box (title and description), a type filter, a "needs skill" filter, and 12 projects per page with Previous/Next.
- Each card shows the type, description, required skills (essential ones highlighted), member count, open places and vacant roles.

**Underneath** (`GET /api/v1/projects`):
- **Visibility:** only `public` projects are listed. `mine=true` lists projects you belong to.
- **Status:** defaults to `open`.
- **Search:** the text is regex-escaped before searching.
- **Skill filter:** the skill is normalised first, so "postgres" finds PostgreSQL projects.
- **Sorting:** newest first. The API allows up to 50 per page.
- Search and filters only help people find projects; they never replace the ranking method.

### 3.6 Creating and editing a project (wizard)

**User:** `/projects/new` is a five-step wizard, validated at each step:

1. **Project**
   - Title (3–120 characters), description (20–4000; used for semantic matching), and type: hackathon, academic, research, startup, competition or other.
   - Optional **event key** such as `sih-2026`: a student can be on only one team per event key.
   - Public or private listing.
2. **Required skills** (1–20)
   - Each has an **importance** (Useful = 1, Important = 2, Essential = 3) that weights coverage, a **desired level** (1–4), and an optional **Mandatory** checkbox.
   - The page explains the difference: importance only affects ranking, while Mandatory removes every candidate who doesn't state at least the desired level.
3. **Team**
   - Target size (2–12, including you), your own role, and vacant roles (up to 8).
   - Existing teammates are invited by handle after the project is created.
4. **Working together**
   - "We meet at fixed times each week" turns on the shared-availability signal.
   - When it is on, you also set: the minimum number of shared slots (`h`, 1–21); whether team slots are those shared by **all** members or by **a majority**; and whether that minimum is mandatory.
   - Expected hours per week and working mode.
5. **Rules and review**
   - Allowed years of study (none ticked means no rule), and "candidates must prefer a vacant role".
   - **Unknown-information policy:** for a candidate who leaves a checked field blank, choose "Don't show them" (the default) or "Show them, flagged as unverified".
   - A summary of the whole project.

Creating the project takes you straight to its recommendations page.

**Underneath** (`POST /api/v1/projects`, `services/projects.py`):
- Requirement skills are normalised. Duplicates after normalisation, such as `nodejs` and `Node.js`, are rejected.
- The creator becomes the first member with the chosen role. That role is removed from the vacant roles.
- `open_positions = target_size − 1`.
- The full configuration is checked by the scoring engine's own validation. For example, a synchronous team needs `h ≥ 1`, and mandatory availability requires synchronous work.
- A team chat is created automatically.
- If an event key is set and you're already on a team for that event, you get **409**.

**Editing** (`/projects/:id/edit`, `PUT /projects/{id}`; creator only):
- The same wizard, plus a **Recruiting** toggle (open or closed).
- Every edit must send the project `version` it started from. If anyone else changed the project, or someone joined or left meanwhile, the edit is refused with **409**: "reload and try again".
- The target size can't go below the current team size.

### 3.7 Project page and team management

**User:** `/projects/:id`

- **Visitors see:**
  - The description, the requirements (importance and level), vacant roles, hours, mode, and meeting rules.
  - A **Mandatory conditions** box listing every rule a newcomer must meet, and whether blank fields lead to exclusion or a flag.
  - The **team list** (name, role, creator badge, joined time).
  - A **requirement coverage chart** showing each skill's coverage and the importance-weighted overall value.
  - **Ask to join**, if there's an open place and you aren't a member and don't already have a pending invitation or request.
- **The creator additionally sees:**
  - **Edit** and **Find members**.
  - All invitations and requests for this team, with accept/decline for incoming requests and withdraw for sent invitations.
  - **Invite by handle**, for existing teammates.
  - **Remove** next to members.
- **Members see** a **Leave** button and the membership history.

**Removing or leaving** (`DELETE /projects/{id}/members/{uid}`):
- One atomic update removes the member, frees the place (`open_positions + 1`), puts their role back among the vacant roles, and records a history entry.
- The creator cannot leave or be removed. They close the project instead.

**Live updates:** when someone joins or leaves, every member's open project page reloads its data through the `team:update` socket event.

### 3.8 Invitations and join requests

**Two kinds**, both stored in `invitations`. The field `candidate_id` is always the student who would join.

| Kind | Sent by | Answered by |
|---|---|---|
| `invite` | the team creator (from recommendations or by handle) | the invited student |
| `request` | any student ("Ask to join") | the team creator |

**Rules when creating one:**
- The team must be open and have a place.
- The student isn't already a member, and isn't on another team with the same event key.
- An offered role must be one of the vacant roles. It is stored with the project's own spelling.
- Only **one pending** invitation or request may exist per (team, student). This is enforced in code and by a partial unique index.
- An invited student must have a **visible** profile. Unknown ids and hidden profiles return 404.

**Statuses:** `pending` → `accepted` / `declined` / `cancelled` / `expired`. The transient state `accepting` is used during acceptance.

**How acceptance stays safe under concurrency** (`services/teams.py`):
1. **Claim:** a conditional update changes `pending` → `accepting`. Only one request can win, so double-clicks and duplicate tabs are harmless.
2. **Join:** one conditional update on the project document:
   - condition: status `open`, `open_positions > 0`, the student not already a member
   - change: decrement `open_positions`, add the member, remove the role from the vacancies, record history, bump `version`
   - MongoDB applies single-document updates atomically, so two people can **never** both take the last place.
3. **Finish:** mark the invitation `accepted`. If step 2 matched nothing, mark it `expired` with the reason `team_full_or_closed` and return 409.
4. **Afterwards:**
   - the team chat's participant list is synced
   - if the team just became full, all other pending invitations for it expire (reason `team_full`)
   - socket events notify everyone involved

**Inbox:** `/invitations` has Received and Sent tabs. Received includes invitations to you **and** requests to teams you created. It updates live via `invitation:new` and `invitation:update`.

**Tested:**
- Invite, accept, decline, cancel, duplicates, wrong party trying to accept, role mapping.
- A full team rejecting new invitations; the one-team-per-event rule.
- Hidden or unknown candidates.
- **4 simultaneous acceptances for 1 place: exactly one 200 and three 409s, with no invitation left stuck.**

### 3.9 Recommendations (the core feature)

**User:** `/projects/:id/recommendations`, creator only. Others get 403 or 404.

**Left column: ranked candidate cards.** Each card shows:
- **Rank, name, @handle, year, branch, primary roles.**
- The **ranking score** (0–1). Hovering explains it is "a relative ranking value for this team's request, not a probability of success". No percentages or "match %" appear anywhere.
- A **coloured contribution bar** showing how much each signal added to the score.
- **Skill chips:** green "+ Node.js 3/4" for skills that would newly add coverage; grey chips for skills the team already covers.
- The **explanation sentence**, for example: *"Adds PostgreSQL (essential; stated proficiency 3 of 4). Prefers the vacant Backend role. Shares 3 of the team's 6 weekly slots. Node.js remains uncovered. Proficiency is self-reported."*
- **Why this rank?** expands the full explanation panel (§3.10).
- A **Compare** checkbox; pick two candidates, then **Compare selected**.
- **Invite**, with an optional role dropdown. Once sent, the card shows "Invitation pending".

**Right column:**
- **Team coverage:** the chart for each requirement. Hovering a candidate previews how each bar would change if they joined.
- **How this list is scored:**
  - the active weight of each signal after renormalisation
  - which signals are "not used for this request", and why (for example "the team does not work synchronously")
  - a reminder that the weights are the paper's initial design values and are not yet calibrated
- **Candidate pool:** for example "24 visible · 21 eligible · 3 excluded by mandatory conditions", with a count per reason ("Below a mandatory skill level: 2", ...). Only counts are shown, never the excluded individuals.
- The encoder used, and a link to "How ranking works".

**Special states** (each with its own message):
- the team is full (no recommendations, as the paper requires)
- the project is closed
- no eligible candidates
- warnings, for example "No current member has stated weekly availability"

**Underneath** (`GET /projects/{id}/recommendations?limit=20&offset=0`, `services/recommendations.py`):
1. **Load the project; check the caller is the creator.**
2. **Build the team** from members' profiles. A member without a profile counts as an empty profile.
3. **Build the candidate pool:** all profiles with `visible: true` that aren't members, in a stable order, capped at 2,000. Hidden profiles never leave the database.
4. **Event conflicts:** if the project has an event key, collect students on *other* teams for that event.
5. **Semantic scores** (`services/embedding_store.py`):
   - The project text (title + description + required skills) is embedded, and the vector is cached on the project.
   - Each candidate's profile text is embedded, and the vector is cached in `embeddings`.
   - A cached vector is reused only if the model id, the text-template version and a SHA-256 of the exact text all match, and its dimension is right. Otherwise it is recomputed.
   - Encoding runs in a worker thread.
   - `f_sem = max(0, cosine)`. An empty profile text gives 0.
6. **Run the pure engine** `rank_candidates` (§4) in a worker thread, with a 30-second timeout (`RECOMMENDATION_TIMEOUT_S`).
7. **Respond:** coverage, active weights, omitted signals, warnings, pool counts, and the requested page of candidates. Each candidate carries its public profile, features, contributions, structured explanation and explanation text.
- Results are **computed fresh on every request**, not cached. They depend on the team, every profile, the requirements, the weights and the model version.

**Refresh:** when someone joins or leaves, the `team:update` event makes the page reload. Coverage is recomputed, and a requirement that is now covered stops earning anyone gap credit. This is the paper's step-by-step recruitment.

**Speed** (laptop CPU, pool of about 24):
- **Warm cache:** median 9 ms per request.
- **Cold:** 349 ms when every profile has to be encoded.
- **First request after a restart:** can take about 10 s, because the model is still loading.

**Tested:**
- The backend developer ranks above the duplicate frontend developer; coverage is 0.4 before the backend developer joins and complete after.
- Membership changes refresh the ranking.
- Only the creator has access; mandatory rules filter and report their reasons.
- Embeddings are cached and invalidated correctly; availability slots never leak.
- Plus a full browser test.

### 3.10 Explanations and the compare view

**The explanation panel** ("Why this rank?") shows:
- **A table of the five signals:** value, weight and contribution (= value × weight), adding up to the score. Signals not used for this request say so. Neutral values used because information was missing are flagged "neutral — not stated".
- **Would add:** each newly covered or improved requirement, with its importance, the candidate's stated level, the desired level, and coverage before → after.
- **Already covered by the team:** required skills the candidate has, where a teammate is already at least as strong.
- **Still open after joining:** requirements that remain below 100%.
- Team coverage before → after (+ the gain), semantic relevance (labelled "topical similarity only"), shared slots ("3 of the team's 6, asked for 2"), and hours and mode against the team's.
- **Missing information** (amber box):
  - availability, hours or mode not stated
  - required skills the candidate doesn't mention, labelled **"not stated ≠ does not have"**
  - any unverified mandatory rule
- The caveat "Proficiency is self-reported."

Everything comes from `domain/explanations.py`, built only from the scoring inputs. Nothing is generated by an LLM, and the same inputs always produce the same explanation (tested).

**Compare view:** pick any two candidates and open **Compare selected**.
- It states, for example, "Bea (#1) scores 0.511 higher than Fred (#2), mostly because of skill-gap contribution."
- A table shows each signal's contribution for both and the difference, sorted by size.
- Both explanation sentences sit side by side.
- This is an exact breakdown of the score difference. It is valid because both candidates were scored in the same request with the same weights.

### 3.11 Messaging (HTTP + Socket.IO)

**User:** `/messages`
- A conversation list with unread badges, the last message preview and its time, and the selected conversation's thread.
- Messages appear instantly ("sending…", then the time). Failed messages are outlined in red.
- **Load older messages** pages back through history.
- Enter sends; Shift+Enter adds a new line.
- **Starting a conversation:** "Message" on any student's profile page.
- **Team chats:** created automatically for every project. Participants follow the membership, so leaving a team removes access to its chat.
- A green dot in the header shows the live connection. When offline, messages still send over HTTP.

**Underneath:**
- **Storage:** messages are stored in MongoDB **first**; the socket only delivers a notification.
- **Who you can message directly:**
  - someone with a visible profile, **or**
  - someone you share a team with, **or**
  - someone with whom an invitation or request exists.
  - Anyone else returns 404.
- **Direct conversations** are unique per pair of people, keyed `direct_key` = the two sorted user ids.
- **Sending** (HTTP `POST /conversations/{id}/messages` or socket `message:send` with an acknowledgement):
  - The same service and authorization check is used for both, and only participants can send.
  - 1–4000 characters; 30 messages per minute per user.
- **Idempotency:** each message carries a `client_id`. A retried send returns the already-stored message instead of creating a duplicate, enforced by a unique index.
- **Delivery:** after storing, the server emits `message:new` to each participant's private room `user:<id>`. Nothing is ever broadcast.
- **Unread counts:** each conversation stores `reads.<userId>` = the time that person last read it. Unread = messages from others after that time. Opening a thread marks it read.
- **Non-participants** get 404 for everything, so conversation ids can't be enumerated.

**Socket.IO connection** (`websocket/server.py`):
- Authenticates with the **same session cookie** as the API.
- Rejects connections from origins not in `CORS_ORIGINS`.
- Allows at most 10 connections per user (per process) and payloads of at most 16 KB.

**Tested:** access control, unread counts, idempotent sends, rate limiting, team chat following membership. A real uvicorn + Socket.IO test checks rejected unauthenticated and foreign-origin connections, delivery only to participants, and refusal of non-participant sends. The browser test exchanges a live chat message between two users.

### 3.12 Privacy, visibility and account deletion

**`/settings` ("Privacy & account"):**
- **Research participation** opt-in toggle, stored in `users.consent.research_participation`. This is **not yet enforced** anywhere (§12, item B2).
- A pointer to the visibility toggle on the profile page.
- **Delete account:** a confirmation dialog needs your password **and** typing `DELETE`.

**Deleting an account** (`services/account.py`) permanently removes:
- the user, all their sessions, their profile, and every stored embedding
- all invitations and requests they sent or received
- every project they created, with its invitations, team chat and messages (other members are notified)
- their place on other teams, which reopens with their role vacant again
- every message they sent, and their direct conversations
- any research ratings they gave

Evaluation reports already written are not edited. They contain ids, never names.

**Privacy rules enforced throughout:**
- **Ranking inputs:** names, e-mails, contact details and demographics are never used; demographics are not collected at all.
- **E-mail** is visible only to its owner.
- **Weekly slots** are never shown to other students.
- **Logs** never contain passwords, tokens, e-mails or message text.

### 3.13 Research dashboard, rating and evaluation

**`/research`** is visible to everyone signed in, for transparency.

**Evaluation status:**
- **"Evaluation pending"** until a run on real, human-rated data exists.
- Real scenarios against the target of 30, real human-rated scenarios, the number of human ratings, and the number of synthetic scenarios.
- **Open tasks**, for example "Collect consent-based real scenarios (target: 30)".
- The methods implemented.

**Administration** (admins only):
- **Load synthetic scenarios:** imports the labelled synthetic set.
- **Run evaluation:** starts a background run.
- **Not in the UI:** importing real scenarios, building rating packets and granting the rater role are **API-only** today (§12, item B1).

**Rating tasks** (raters and admins):
- A list of prepared packets, with links to **Rate**.

**Evaluation runs:**
- Each run is badged **measured** or **demonstration**.
- **View results** opens the method table, the ablation table, the paired tests, Krippendorff's α and timings.
- Unmeasured cells print "not measured". Demonstration runs carry a warning banner.

**`/research/judging/:scenarioId`** is the rating form:
- **The rater sees:** the project, its requirements and the current team, plus each candidate as an anonymous label (C01, C02, ...) with skills, roles, year, hours, mode and the number of availability slots.
- **The rater never sees:** names, handles, ids, method names or scores.
- **Order:** candidates are shuffled differently for each rater, deterministically.
- **Ratings:** each candidate gets 0 not suitable / 1 marginally / 2 suitable / 3 strongly suitable. All candidates must be rated, and each rater can submit once per scenario.
- **Use:** ratings are stored in `judgments` and used **only offline** by the evaluation. They never affect live recommendations.

**Research API:**

| Endpoint | Who | Purpose |
|---|---|---|
| `POST /research/scenarios/import` | admin | Import real scenarios (JSON list) |
| `POST /research/scenarios/{id}/packet` | admin | Pool each method's top 10 + 3 random eligible candidates into an anonymised packet |
| `POST /research/raters/{user_id}` | admin | Grant the rater role |
| `POST /research/evaluate` | admin | Run the full protocol in the background (202) |
| `GET /research/judging/tasks`, `GET/POST /research/judging/{id}` | rater | List tasks, fetch a packet, submit ratings |

The full pipeline is described in §9.

### 3.14 Public pages

- **`/` (landing):** the paper's Scenario A as a worked picture (Candidate X duplicates React; Candidate Y fills Node.js + PostgreSQL), plus the "evaluation not yet completed" notice.
- **`/how-it-works`:**
  - the filter-then-score pipeline, coverage in plain language
  - the five signals and their initial weights
  - what the score is *not* (a probability, objective, demographic-based, or a guarantee of collaboration)
- **`/privacy`:** what is collected and why, who sees what, research use, and deletion.
- **Accessibility and layout throughout:**
  - a "Skip to content" link, visible keyboard focus, labelled controls, and real `<table>` elements
  - meters with numeric values
  - a responsive layout with a mobile menu, tested at 390 px wide with no horizontal scrolling

---

## 4. The scoring engine, step by step

Code: `backend/app/domain/engine.py → rank_candidates(request, weights)`. Everything here is pure and deterministic.

### Step 0: Team full?
If `target_size − team size = 0`, the status is `team_full` and no candidates are returned.

### Step 1: Mandatory eligibility filter (`eligibility.py`)

Each candidate is checked against these rules. Ineligible candidates are **never** ranked.

| Rule | Fails when | Reason code | When the field is blank |
|---|---|---|---|
| Visible | profile hidden | `PROFILE_HIDDEN` | – |
| Not a member | already on this team | `ALREADY_MEMBER` | – |
| One team per event | on another team with the same event key | `COMMITTED_TO_EVENT_TEAM` | – |
| Allowed years | year not in the list | `YEAR_NOT_ALLOWED` | `YEAR_UNVERIFIED` |
| Mandatory skill | stated level < desired level, or explicitly "none" | `MANDATORY_SKILL_NOT_MET` | `MANDATORY_SKILL_UNVERIFIED` |
| Mandatory role | prefers no vacant role | `ROLE_NOT_MATCHED` | `ROLE_UNVERIFIED` |
| Mandatory availability | shared slots < `h` | `AVAILABILITY_NOT_MET` | `AVAILABILITY_UNVERIFIED` |

- "Unverified" codes are **never** treated as a failure.
- The project's `unverifiable_policy` decides what happens: `exclude` (default) leaves them out; `include` ranks them with a flag.

### Step 2: Team coverage (Eqs. 2–3)
- **Per requirement:** `C_s(T) = min(1, best member level / desired level)`.
- **Overall:** `Coverage(T) = Σ a_s·C_s / Σ a_s`, where `a_s` is importance 1/2/3.
- Unstated and explicitly-absent skills both count as 0, as in the paper.

### Step 3: Signals that apply to the whole request
A signal is **omitted** for everyone in the request when:

| Signal | Omitted when |
|---|---|
| `gap` | the team already has 100% coverage (`f_gap` undefined) |
| `role` | the team lists no vacant roles |
| `avail` | the team isn't synchronous, or no member stated availability |
| `work` | the team states neither hours nor mode |

The remaining weights are renormalised to sum to 1: `w'_k = w_k / Σ active w`.

### Step 4: Per-candidate signals (each between 0 and 1)
- **`f_sem`** = max(0, cosine(profile embedding, project embedding)).
- **`f_gap`** = `G / (1 − Coverage(T))`, where `G = Coverage(T ∪ {c}) − Coverage(T)`.
  - Repeating skills the team already covers adds 0.
  - Skills the project doesn't require add 0.
- **`f_role`** = 1 if any vacant role is a primary preference, 0.5 if secondary, otherwise 0 (also 0, flagged, if no roles were stated).
- **`f_avail`** = min(1, |candidate slots ∩ team slots| / h).
  - Team slots are the intersection across members, or majority-shared slots under the majority policy.
  - Unstated availability gives **0.5**, flagged. Stated with no overlap gives 0.
- **`f_work`** = the mean of whichever components the team states:
  - **Commitment:** `1 − |h_c − h_T| / 39`; 39 is the largest possible difference on the 1–40 form.
  - **Mode:** 1 if the same mode or either side is hybrid; 0 for online versus offline.
  - A component the candidate didn't state gives 0.5, flagged.

### Step 5: Score and order
- **Score** = Σ active weight × signal.
- **Initial weights** (paper): sem 0.30, gap 0.35, role 0.15, avail 0.10, work 0.10.
- **Order:** score ↓, then `f_gap` ↓, then `f_sem` ↓, then candidate id. The result is fully deterministic regardless of database order (tested).

### Worked example (the paper's Scenario A; this exact case is a unit test)

**Requirements:**

| Skill | Importance | Desired level |
|---|---|---|
| React | 2 | 3 |
| Machine Learning | 2 | 3 |
| Node.js | 3 | 3 |
| PostgreSQL | 3 | 2 |

**Team:** Alice (React 3) and Bob (ML 4) → coverage = (2·1 + 2·1 + 0 + 0) / 10 = **0.40**.

**Request settings:** the team is asynchronous and states no hours or mode, with Backend vacant. So `avail` and `work` are omitted, and the weights become sem 0.375, gap 0.4375, role 0.1875.

| Candidate | Skills | f_sem | G | f_gap | f_role | Score |
|---|---|---|---|---|---|---|
| X | React 4 | 0.90 | 0 | 0 | 0 | 0.375×0.9 = **0.3375** |
| Y | Node.js 3, PostgreSQL 2 | 0.60 | 0.60 | 0.60 / 0.60 = 1 | 1 | 0.225 + 0.4375 + 0.1875 = **0.85** |

**Y ranks first** despite lower semantic similarity. If Y joins, coverage becomes 1.0. The `gap` signal is then omitted for the next request, and its weight is shared among the rest.

### Limits inherited from the paper
- Proficiency is self-reported.
- Coverage counts only the single strongest member per skill: no workload, and no "we need two backend developers".
- The candidate's own interest in the team isn't modelled.
- Selection is one at a time, not joint.

All decisions taken where the paper is ambiguous are in `docs/research-methodology.md`.

---

## 5. Sessions, tokens and CSRF in detail

### What exists

| Item | Value | Where |
|---|---|---|
| **Session cookie** | name `assembl_session` (`SESSION_COOKIE_NAME`) | browser |
| Cookie value | 256-bit random token (`secrets.token_urlsafe(32)`, 43 characters) | browser only |
| Cookie flags | `HttpOnly` (JavaScript can't read it); `Secure` if `COOKIE_SECURE=true`; `SameSite=lax` (configurable); `Path=/`; optional `Domain` (`COOKIE_DOMAIN`); `Max-Age` = session lifetime | |
| **Server record** | `sessions` document: `_id` = **SHA-256 of the token** (the token itself is never stored), `user_id`, `csrf_token`, `created_at`, `last_seen`, `expires_at` | MongoDB |
| Lifetime | absolute **7 days** (`SESSION_TTL_HOURS=168`); no sliding renewal | |
| Expiry enforcement | checked on every request (expired sessions are deleted), plus a MongoDB TTL index on `expires_at` that removes expired sessions automatically | |
| **CSRF token** | a second 256-bit random value, stored in the session record | MongoDB + browser memory |
| **Password hash** | `scrypt$32768$8$1$<salt>$<hash>` (N=2^15, r=8, p=1, 16-byte salt, 32-byte key) | `users.password_hash` |

There are no JWTs and no tokens in `localStorage`. Being signed in is always decided by the server.

### Lifecycle

```
REGISTER / LOGIN
  browser ──POST /auth/login {email, password}──────────────► server
          ◄── Set-Cookie: assembl_session=<token>; HttpOnly ──  ① verify scrypt hash
          ◄── body: {user, csrf_token}                          ② delete the browser's previous session (rotation)
                                                                 ③ insert {_id: sha256(token), csrf_token, expires_at: now+7d}
  frontend keeps csrf_token in a JS variable (src/api/client.ts), NOT in storage

EVERY REQUEST
  GET  /api/v1/...  Cookie: assembl_session=<token>
        server: sha256(token) → session → not expired → user          (401 if any step fails)
  POST/PUT/DELETE   Cookie + header X-CSRF-Token: <csrf_token>
        server: as above, PLUS constant-time compare of the header with session.csrf_token  (403 if wrong)
        middleware: if an Origin header is present it must be in CORS_ORIGINS                  (403 otherwise)

PAGE RELOAD
  the JS variable is lost → frontend calls GET /auth/me (cookie only) → {user, csrf_token} again

SOCKET.IO
  the browser sends the same cookie with the WebSocket/polling handshake
  server: Origin must be allowed → parse cookie → same session lookup → join room "user:<id>"

LOGOUT              → session document deleted, cookie cleared
DELETE ACCOUNT      → every session for the user deleted
EXPIRY (7 days)     → next request finds it expired, deletes it, returns 401 → frontend shows sign-in
```

### Why CSRF needs a token on top of SameSite
`SameSite=Lax` already stops most cross-site form posts. Even so:
- the API requires the `X-CSRF-Token` header, which another site cannot read because of the cross-origin rules
- the Origin check rejects foreign origins

That gives three independent layers of protection.

### What is NOT implemented yet (session-related)
These are listed again in §12:
- **Idle timeout / sliding renewal:** `last_seen` is written at sign-in but never updated.
- **"Sign out of all devices":** `destroy_all_sessions()` exists in `services/auth.py` but nothing calls it.
- **Password change and reset:** neither exists, so nothing rotates sessions on a password change.
- **E-mail verification:** none, which matters for `ADMIN_EMAILS` (§12, item A3).

---

## 6. Other security controls

| Control | Detail |
|---|---|
| **Rate limits** | Login 10 / 5 min per IP + e-mail; registration 20 / hour per IP; messages 30 / min per user. Uses Redis when `REDIS_URL` is set, and falls back to in-process counters if Redis is missing or down (tested). |
| **CORS** | Only `CORS_ORIGINS`, with credentials. Methods GET/POST/PUT/DELETE. Headers Content-Type, X-CSRF-Token, X-Request-ID. |
| **Authorization** | Checked on the server for every resource. Unauthorised reads look like **404** for private projects, conversations and hidden profiles, so ids can't be probed. Malformed ids are also 404. |
| **Roles** | `student` (default) · `rater` (may rate research packets) · `admin` (research administration; set by `ADMIN_EMAILS` at registration) |
| **Validation** | Strict request models (unknown fields → 422), length limits everywhere, slot format checked, search text escaped |
| **Errors** | Generic messages; stack traces are never returned |
| **Logging** | JSON lines: time, level, request id, method, route template, status, duration. **No** passwords, tokens, e-mails or message bodies. Each response carries an `X-Request-ID` header. |
| **Production guard** | With `ENVIRONMENT=production`, startup **fails** if `COOKIE_SECURE` is false or `MONGODB_URL` is the in-memory mock |
| **Frontend** | React escapes all output; no raw HTML injection. `vercel.json` adds `nosniff`, `X-Frame-Options: DENY` and a referrer policy. |

### Who can do what

| Action | Creator | Member | Other student | Signed out |
|---|---|---|---|---|
| View a public project | ✓ | ✓ | ✓ | ✓ |
| View a private project | ✓ | ✓ | only if invited | ✗ |
| Edit, invite, view recommendations | ✓ | ✗ | ✗ | ✗ |
| Ask to join | – | – | ✓ (public projects only) | ✗ |
| Leave | ✗ (close instead) | ✓ | – | – |
| Remove a member | ✓ | ✗ | ✗ | – |
| Team chat, history | ✓ | ✓ | ✗ | ✗ |

---

## 7. Data model

MongoDB collections. Indexes are created automatically at startup (`db/mongo.py`). Full detail is in `docs/architecture.md`.

| Collection | Holds |
|---|---|
| `users` | e-mail, password hash, display name, handle, role, consent |
| `sessions` | hashed session token, CSRF token, expiry (TTL index) |
| `profiles` | skills (canonical, level, type, recognised flag), explicit absences, roles, interests, projects, links, availability (`null` = not stated), hours, mode, visibility, profile text |
| `embeddings` | per user + model: vector, dimension, text hash, template version |
| `projects` | settings, requirements, members, `open_positions`, vacant roles, rules, history, `version`, cached project embedding |
| `invitations` | kind, from, candidate, role, message, status, reason |
| `conversations` | direct/team, participants, last message, `reads` per user |
| `messages` | conversation, sender, body, `client_id` |
| `research_scenarios` | raw scenario JSON, provenance, rating packet, packet key (label → candidate; never sent to raters) |
| `judgments` | scenario, candidate, rater, rating 0–3 |
| `evaluation_runs` | state, full report JSON, Markdown, `is_research_evidence` |

All times are stored in UTC and displayed in the viewer's local time.

---

## 8. What is real and what is synthetic

| Thing | Real or synthetic | Details |
|---|---|---|
| Sentence-BERT model | **Real** | `sentence-transformers/all-MiniLM-L6-v2`, pretrained, used as provided (no fine-tuning), 384-dimensional |
| Hashing encoder (`EMBEDDING_BACKEND=hashing`) | **Fake, not semantic** | Bag-of-words feature hashing, for tests and offline demos. Its `model_id` says "NOT semantic", and reports record which encoder was used. |
| Scoring engine, metrics, statistics | **Real** | Implement the paper's equations exactly; verified against hand calculations |
| Demo accounts and demo project (`SEED_DEMO=1`, `python -m app.seed`) | **Synthetic** | 24 generated students; names end in "(demo)"; e-mails at `demo.assembl.example`; documents marked `demo: true`. Refuses to run in production. |
| `research/scenarios/synthetic/synthetic_scenarios.json` | **Synthetic, with SIMULATED ratings** | 30 scenarios: 6 base projects (placement prep, health hackathon, fintech app, smart-campus IoT, NLP paper, cloud toolkit) × 5 team variants, with team sizes 1,1,2,2,3. Variants 2 and 4 meet synchronously; variant 4 restricts years to 2–4; variant 5 makes one requirement mandatory. Each has a pool of 24 drawn from 160 generated students. |
| Simulated ratings | **Synthetic, and circular** | 3 "simulated raters" per scenario, from a rule over hidden variables (how much a candidate truly fills gaps, role match, availability, archetype relevance), plus rater bias and noise. The rule overlaps with Assembl's own signals, so results on it **cannot** show Assembl is better. |
| `research/reports/20261026T153223Z-174891/` | **Pipeline demonstration** | Real SBERT on synthetic scenarios with simulated ratings. Labelled "PIPELINE DEMONSTRATION – NOT RESEARCH EVIDENCE". |
| Real scenarios and human ratings | **Do not exist yet** | `research/scenarios/real/` is empty; the app shows "Evaluation pending" |
| Weights | **The paper's initial design values** | 0.30 / 0.35 / 0.15 / 0.10 / 0.10. The demo run's "calibrated" weights were fitted to simulated ratings and **must not** be adopted. |
| "Projects related to your profile" on the dashboard | **Real data, simpler method** | Semantic relevance only, labelled as such |

### What the demo report shows (pipeline output only, not evidence)

On the 15 test scenarios with simulated ratings: NDCG@5 was M1 0.751, M2 0.744, M3 0.818, M4 0.835, M5 0.911 (initial weights 0.903). Mandatory violations were 0 for every method.

These numbers show **the pipeline runs end to end**. Because the ratings were generated by a rule resembling Assembl's own signals, they say nothing about real students.

The integrity checks are meaningful, however:
- **Changed membership:** M1–M3 rankings unchanged (τ = 1.00), while M4 and M5 change (τ ≈ 0.93 / 0.92).
- **Already-covered teams:** 15/15 handled correctly.
- **Alias rewriting:** 15/15 rankings identical; distinct technologies kept separate.

---

## 9. The research pipeline, and how to run the real study

**Code:** `backend/app/research/`. **CLI:** `python -m app.research.cli` (run from `backend/`).

### What one evaluation run does (`runner.py`)
1. **Load scenarios** and record their provenance. Warn if anything is synthetic or simulated, if there are no human ratings, or if fewer than 3 raters per scenario.
2. **Split** into development and test sets (default 50/50, seed 13). Scenarios sharing a base project **or any team member** are grouped together, so a near-duplicate can't leak into the test set. The split manifest is saved.
3. **Apply the mandatory filter once per scenario.** All five methods rank **the same eligible pool**.
4. **Compute semantic scores** with the configured encoder, caching by text.
5. **Calibrate on development scenarios only:**
   - grid search over weight vectors that sum to 1 (step 0.1), maximising mean development NDCG@5
   - repeated separately for each ablation
   - the paper's initial weights are kept as their own baseline, "M5 (initial weights)"
   - with no rated development scenarios, initial weights are used and the run says so
6. **Evaluate on test scenarios:**
   - **M1** skill overlap
   - **M2** TF-IDF
   - **M3** semantic only
   - **M4** semantic + gap
   - **M5** full Assembl
   - five ablations (M5 without each signal)
7. **Metrics** for each scenario, then macro-averaged:
   - **NDCG@5:** linear gain (mean rating), log2 discount; the ideal ordering uses all rated *eligible* candidates; candidates without ratings are skipped, never scored 0.
   - **Precision@5:** relevant if the mean rating is at least 2; the denominator is min(5, rated candidates ranked).
   - **Added coverage@5:** the mean gain `G` the top 5 would bring.
   - **Soft constraint violations@5:** zero shared slots, online versus offline, or a stated role preference matching no vacant role.
   - **Mandatory violations:** must be 0.
   - **Median response time:** warm and cold, with the hardware recorded.
8. **Statistics:**
   - Wilcoxon signed-rank tests on per-scenario NDCG@5: M3 vs M4 (RQ2), M4 vs M5 (RQ3), each baseline vs M5, and M5 vs each ablation.
   - Rank-biserial effect sizes, with warnings when fewer than 10 pairs differ.
   - Krippendorff's α (ordinal) for agreement between raters.
9. **Robustness checks:**
   - hiding 20% and 40% of profile information
   - rewriting skills with aliases
   - limited-availability scenarios
   - already-covered teams
   - changed membership (M1–M3 must not move)
10. **Write** `report.md`, `run.json` and `split_manifest.json`. Unmeasured values print "not measured". Synthetic or simulated runs are marked `pipeline-demonstration`.

### Running the real study (paper §4.6), step by step
1. **Ethics and consent.** Collect consent-based profiles and team scenarios at your college; the paper targets 30, covering both single-member and multi-member teams.
2. **Write each scenario** as JSON in the format in `research/README.md`, with `provenance: "real"`:
   - include the project, requirements (importance, desired level, mandatory flag), team members' profiles, the candidate pool and the rules
   - write `null` for availability that wasn't stated, and use `declared_absent` only for an explicit "none"
3. **Import** them, either:
   - by API (as admin): `POST /api/v1/research/scenarios/import` with the JSON list, or
   - offline: put the files in `research/scenarios/real/`.
4. **Build rating packets** for each scenario, either:
   - `POST /api/v1/research/scenarios/{id}/packet`, or
   - offline: `python -m app.research.cli pool --scenarios ../research/scenarios/real --out ../research/judging`, which writes `*.packet.json` (the rater view) and `*.key.json` (coordinator only).
5. **Recruit at least 3 raters per scenario.** Senior students with project or hackathon experience are preferred.
   - Each registers an account.
   - An admin grants the role: `POST /api/v1/research/raters/{user_id}`.
   - Raters then rate from **Research → Rating tasks**.
6. **Run the evaluation**, either:
   - **Research → Run evaluation** (admin), or
   - `python -m app.research.cli evaluate --scenarios ../research/scenarios/real --out ../research/reports`.
   - Use the real encoder (the default), not `--encoder hashing`.
7. A run counts as evidence only when every scenario is `real` and every rating is `human`. The run is then marked `measured` / `is_research_evidence: true`, and the dashboard switches from "Evaluation pending".
8. **Report the results honestly:** sample size, α, effect sizes, and the single-college limitation (paper §6.2).

**How human ratings combine with files:** if a scenario has human ratings in the database, the evaluation uses **only** those and labels them `human`. Simulated ratings are never mixed in.

---

## 10. Configuration reference (every environment variable)

Backend settings are read from the environment or `backend/.env`. Frontend settings are read at **build time** by Vite. The template is `.env.example`.

| Variable | Default | Meaning |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` / `test` / `production`. Production enables the startup safety checks. |
| `MONGODB_URL` | `memory://` | `memory://` = in-process mock (data lost on restart). Production: `mongodb+srv://…` |
| `MONGODB_DB` | `assembl` | Database name |
| `REDIS_URL` | empty | Optional. Shared rate limits, and Socket.IO across several instances. |
| `SESSION_COOKIE_NAME` | `assembl_session` | |
| `SESSION_TTL_HOURS` | `168` | Absolute session lifetime |
| `COOKIE_SECURE` | `false` | **Must be `true` in production** (HTTPS only) |
| `COOKIE_SAMESITE` | `lax` | `lax` / `strict` / `none`. Keep `lax` with the set-ups in §11. |
| `COOKIE_DOMAIN` | empty | e.g. `.example.com` for set-up B in §11 |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated frontend origins, also used for Socket.IO and the Origin check |
| `ADMIN_EMAILS` | empty | Accounts **registered** with these e-mails become admins |
| `EMBEDDING_BACKEND` | `sbert` | `sbert` (real) or `hashing` (tests only) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Any Sentence-Transformers model id |
| `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW_S` | `10` / `300` | |
| `MESSAGE_RATE_LIMIT` / `MESSAGE_RATE_WINDOW_S` | `30` / `60` | |
| `MAX_MESSAGE_CHARS` | `4000` | |
| `RECOMMENDATION_TIMEOUT_S` | `30` | |
| `SEED_DEMO` | `0` | `1` = add the synthetic demo data at startup (ignored in production) |
| `ASSEMBL_TEST_SBERT` | unset | `1` = also run the test that loads the real model |
| `VITE_API_BASE` | empty | Frontend: API origin. Empty = same origin (dev proxy or Vercel rewrite). |
| `VITE_SOCKET_URL` | empty | Frontend: Socket.IO origin. Empty = same origin. |
| `VITE_SOCKET_TRANSPORTS` | `websocket,polling` | Set `polling` when behind Vercel rewrites |
| `VITE_DEV_BACKEND` | `http://127.0.0.1:8000` | Dev proxy target |

---

## 11. What needs to be connected to go live

None of this has been done yet. Follow it in order and tick each item off.

### 11.1 Accounts and services you need
- [ ] **MongoDB Atlas** (any MongoDB-compatible managed service works). **Not Neon:** Neon is PostgreSQL.
- [ ] **Render** account for the backend: Docker web service, at least 1 GB RAM, because torch + MiniLM needs about 500–700 MB.
- [ ] **Vercel** account for the frontend.
- [ ] *Optional:* a managed Redis (Render Redis, Upstash, ...). Only needed for more than one backend instance or shared rate limits.
- [ ] *Optional but recommended:* a domain you control, such as `example.com` (set-up B below).
- [ ] A Git host (GitHub) that Render and Vercel deploy from. Nothing has been committed yet.

### 11.2 MongoDB Atlas
1. Create a cluster and a database user with a long random password.
2. Network access: allow Render's outbound IPs, or `0.0.0.0/0` together with the strong password.
3. Copy the connection string `mongodb+srv://USER:PASS@cluster…/`. It becomes `MONGODB_URL`.
4. The first backend start creates every index. Afterwards, check in Atlas that the partial index `one_pending_per_candidate` on `invitations` exists, along with the TTL index on `sessions.expires_at`.

### 11.3 Backend on Render
1. New → Blueprint → select the repo. It reads `render.yaml`: Docker, `rootDir: backend`, health check `/api/v1/health/ready`, one instance.
2. Fill in the secret variables:
   - `MONGODB_URL`
   - `CORS_ORIGINS` (your exact frontend origin, e.g. `https://assembl.vercel.app`, no trailing slash)
   - `ADMIN_EMAILS`
   - optionally `REDIS_URL`
3. The blueprint already sets `ENVIRONMENT=production`, `COOKIE_SECURE=true` and `COOKIE_SAMESITE=lax`. Add `COOKIE_DOMAIN` only for set-up B.
4. Deploy, then check `https://<service>.onrender.com/api/v1/health/ready`: it should return `"database": true`. `encoder_loaded` becomes true after warm-up.

### 11.4 Frontend on Vercel
1. Import the repo with Root Directory `frontend`, build command `npm run build`, output `dist`.
2. Pick **one** cookie set-up:

**Set-up A: proxy through Vercel (no custom domain)**
- Edit `frontend/vercel.json`: replace **both** occurrences of `assembl-api.onrender.com` with your Render host.
- Vercel variables: leave `VITE_API_BASE` and `VITE_SOCKET_URL` empty, and set `VITE_SOCKET_TRANSPORTS=polling`. Vercel rewrites can't carry WebSockets, so chat uses HTTP long-polling, which is slightly slower.
- Render: `CORS_ORIGINS=https://<project>.vercel.app`, with no `COOKIE_DOMAIN`.
- The browser only ever talks to the Vercel origin, so the cookie is first-party and `SameSite=Lax` works.

**Set-up B: same-site custom domains (recommended for production)**
- DNS: point `app.example.com` at Vercel and `api.example.com` at Render.
- Render: `CORS_ORIGINS=https://app.example.com` and `COOKIE_DOMAIN=.example.com`.
- Vercel: `VITE_API_BASE=https://api.example.com` and `VITE_SOCKET_URL=https://api.example.com`. Leave the transports at the default, so real WebSockets work. The `/api` rewrite in `vercel.json` can then be removed.

**Do not** use `*.vercel.app` with `*.onrender.com` and `SameSite=None`. That is a third-party cookie, blocked by Safari and increasingly by Chrome, and sign-in would silently fail.

### 11.5 First-run checks after deploying (in a real browser)
- [ ] Register the admin account **immediately**, using an e-mail in `ADMIN_EMAILS` (see §12, item A3 for why).
- [ ] Reload the page: you should stay signed in. That confirms the cookie works under your origins.
- [ ] Edit your profile, which tests CSRF and the database.
- [ ] Create a project and open Find members. The first request may take about 10 s while the model loads.
- [ ] From a second browser, sign up, accept an invitation, and exchange a chat message. This confirms sockets work.
- [ ] Never set `SEED_DEMO=1` in production.

### 11.6 Files you will edit to go live

| File | Change |
|---|---|
| `frontend/vercel.json` | Render host (set-up A), or remove the `/api` rewrite (set-up B) |
| `render.yaml` | Service name/region if desired; `numInstances` > 1 only with Redis |
| Render and Vercel dashboards | The environment variables above |
| `backend/app/domain/skill_aliases.json` | Add skills and aliases your students use |
| `frontend/src/pages/PrivacyPage.tsx` | Your institution's contact, retention period and the ethics approval reference |

---

## 12. Known gaps and changes to make

Ordered by priority, each with where to make the change.

### A. Must fix before real users

| # | Gap | Why it matters | Where / how |
|---|---|---|---|
| A1 | Never tested against a real MongoDB | The mock skips partial indexes, and atomic and TTL behaviour should be confirmed on a real server | Add a CI job running `pytest` with a `mongo:7` service and `MONGODB_URL` pointing at it; the test fixture currently always uses the mock (`tests/integration/conftest.py`) |
| A2 | Not deployed | The cookie and socket set-up is untested in production | §11 |
| A3 | **No e-mail verification, and admin is granted by e-mail at registration** | Anyone could register an e-mail they don't own, and **whoever registers an `ADMIN_EMAILS` address first becomes admin**. Adding an e-mail to `ADMIN_EMAILS` later doesn't promote an existing account. | Short term: register admin accounts yourself immediately after deploying. Proper fix: an e-mail verification flow (needs an e-mail provider), and grant admin only to verified addresses, via a startup sync or CLI (`services/auth.py`). |
| A4 | No password reset and no password change | Locked-out users can't recover; no session rotation on password change | New endpoints and an e-mail flow; on change, call the existing, unused `destroy_all_sessions()` |
| A5 | An invitation can stay stuck in `accepting` | If the server crashes between the claim and the finish (§3.8), the invitation never returns to `pending` | A periodic job, or a check on read, that resets `accepting` invitations older than about 1 minute (`services/teams.py`) |
| A6 | No abuse controls | No blocking or reporting users, and no message moderation | Block list per user, checked in `messaging.get_or_create_direct` / `send_message`; a report endpoint |

### B. Should fix (product completeness)

| # | Gap | Where / how |
|---|---|---|
| B1 | Research admin actions are API-only (import real scenarios, build packets, grant rater) | Add buttons and forms to `features/research/ResearchPage.tsx`; the endpoints already exist |
| B2 | The research-participation consent is stored but not enforced | Scenarios are imported as separate JSON, so nothing ties them to app profiles. If scenarios are ever built from app profiles, filter on `consent.research_participation`, and record consent in the scenario provenance. |
| B3 | Sessions: no idle timeout (`last_seen` never updated) and no "sign out of all devices" | Update `last_seen` in `session_user` at most every few minutes and expire idle sessions; add a button that calls `destroy_all_sessions` |
| B4 | No persistent notification list | Live socket events only, plus the invitation inbox and unread counts. Add a `notifications` collection written next to each `notifier.to_users` call, and a bell menu. |
| B5 | Display name and handle can't be changed after registration | New profile endpoints |
| B6 | Messages can't be edited or deleted; no per-message read receipts or typing indicator | `services/messaging.py`, `MessagesPage.tsx` |
| B7 | The research page doesn't auto-refresh while a run is going | Poll `/research/runs` while any run is `running` |
| B8 | Closing a project doesn't expire its pending invitations (accepting later still fails safely with 409) | In `update_project`, when the status becomes `closed`, call `_expire_pending` |
| B9 | No security headers (CSP, HSTS) on the API itself | Small middleware in `main.py`; HSTS once on HTTPS |
| B10 | The alias table has no admin screen | Move it into a collection with an admin editor, or keep the JSON and document a review process for unrecognised labels (the UI already reports them) |
| B11 | No CI pipeline | GitHub Actions: backend pytest (+ real Mongo, A1), frontend `npm test`, `tsc`, `eslint`, build; optionally Playwright |

### C. Scale and performance (fine for a pilot; measure before changing)

| # | Item | Notes |
|---|---|---|
| C1 | Rate-limit counters and the per-user socket connection count live in the process when Redis is absent | Correct for one instance. With more, set `REDIS_URL`; the connection counter would also need moving to Redis. |
| C2 | Unread counts cost one query per conversation | Fine for dozens of conversations; could become an aggregation later |
| C3 | The recommendation pool is capped at 2,000 visible profiles, scored on every request | About 9 ms warm for 24 candidates. Measure at real scale before considering a vector index. |
| C4 | Cold start: the first recommendation after boot is about 10 s | The model is loaded at startup in the background, but profiles are embedded only when first needed. Could pre-compute embeddings when a profile is saved. |
| C5 | `history` on a project grows without limit; conversation list capped at 50, invitations at 100, with no pagination | Fine for student teams; add pagination if needed |
| C6 | The model is identified by name only | Pin a Hugging Face revision hash in `EMBEDDING_MODEL` handling, so results stay reproducible |
| C7 | The dashboard's project suggestions embed up to 30 project texts on first view | Cached afterwards; could be pre-computed when a project is created |

### D. Research and method improvements (paper §6.3)

- **Collect the real data and run the evaluation** (§9). This is the most important remaining task. Until then, the paper's claims are untested.
- Replace the initial weights only with weights calibrated on **real** development data. Never use the demo run's weights.
- **Optional learned ranker** (a regularised pairwise logistic model over the five signals) once enough rated pairs exist. Not implemented.
- **Experimental variant for unstated skills:** `team_coverage(..., unknown_value=x)` already exists, but isn't exposed in the CLI. Add a flag if you want to report it.
- **Workload and multiple specialists:** count required headcount per skill, not just the best member.
- **Two-sided recommendation:** also model whether the candidate wants to join.
- **Joint selection** of several members, or whole teams.
- **Vacant roles are a set:** two openings for the same role can't be represented yet.
- **Outcome evaluation:** follow formed teams through a semester.

### E. Small clean-ups
- `frontend/README.md` is the leftover Vite template; delete or replace it.
- 6 lint warnings about React fast refresh: helper functions exported from component files. They're harmless; to silence them, move the helpers to their own files.
- No dark mode; English only.

---

## 13. Tests

| Suite | Command | Count | Covers |
|---|---|---|---|
| Backend: all | `cd backend && python -m pytest` | 164 passed + 1 opt-in | everything below |
| Backend: maths (`tests/unit`) | `python -m pytest tests/unit` | 102 + 1 opt-in | aliases; coverage, gain and `f_gap` with hand values; every signal; eligibility codes; weights and renormalisation; tie-breaking; Scenario A and C rankings; explanations matching the inputs; determinism under reordering; properties (adding a member never lowers coverage; unrequired skills don't change gain; ...); password hashing; tokens; Redis fallback |
| Backend: real model | `ASSEMBL_TEST_SBERT=1 python -m pytest -m sbert` | 1 | Real MiniLM: 384 dimensions, related texts more similar than unrelated, deterministic |
| Backend: research (`tests/research`) | `python -m pytest tests/research` | 23 | NDCG/Precision hand values; unrated ≠ 0; Krippendorff's α hand value; Wilcoxon; Kendall τ; fast scoring table = engine; same pool for every method; M1–M3 ignore membership; pooling reproducible and anonymised; splits keep leakage groups together; calibration sees development scenarios only (spied); unmeasured shown as "not measured"; provenance enforced |
| Backend: API (`tests/integration`) | `python -m pytest tests/integration` | 39 | Auth, CSRF, Origin, rate limits, profiles, projects, invitations, **concurrent acceptance**, event rule, recommendations, embedding cache, messaging, research rating flow, account deletion, health, **real Socket.IO server** |
| Frontend: components and journeys | `cd frontend && npm test` | 11 | CSRF header handling; compare logic; coverage chart values; candidate card (no probability wording, explanation, invite); availability grid (unknown ≠ none, keyboard); "not measured" cells; sign-in redirect and error; honest empty dashboard; recommendations → invite |
| Frontend: types and lint | `npx tsc -b`, `npx eslint .` | – | 0 type errors; 0 lint errors (6 warnings) |
| Browser end-to-end | `cd frontend && npx playwright install chromium && npx playwright test` | 2 | Register → profile → create team → recommendations → explanation → invite → second user signs in and accepts → team updates → live chat between both browsers → research shows "Evaluation pending"; plus no horizontal scrolling at 390 px. Starts or reuses both servers; needs the demo seed. Set `E2E_SCREENSHOTS=<dir>` to save screenshots. |

All backend tests use an **isolated in-memory database** and never touch real data.

---

## 14. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| All data gone after restarting the backend | `MONGODB_URL=memory://` is in-memory. Use a real MongoDB (§2). |
| First "Find members" takes about 10 s | The model is loading and every profile is being embedded for the first time. Later requests are fast. |
| Signed in, but reload signs you out (deployed) | Cookie blocked as third-party, or `COOKIE_SECURE` mismatched with HTTP/HTTPS. Use set-up A or B in §11. |
| `403 Missing or invalid CSRF token` | A state-changing call was sent without `X-CSRF-Token`. The frontend handles this; custom scripts must call `/auth/me` first and send the token. |
| `403 Cross-origin request rejected` | The page's origin isn't in `CORS_ORIGINS` (check for an exact match, no trailing slash). |
| Header dot is grey / "live updates offline" | Socket blocked (Origin not allowed, or WebSockets not proxied). Messages still send over HTTP; set `VITE_SOCKET_TRANSPORTS=polling` behind Vercel rewrites. |
| Can't sign in as a demo user | Demo e-mails end in `@demo.assembl.example` and the password is `demo-password-123`; the backend must have been started with `SEED_DEMO=1`. |
| Backend refuses to start: "unsafe production configuration" | In production you must set `COOKIE_SECURE=true` and a real `MONGODB_URL`. |
| Recommendations page says "No eligible candidates" | Check the **Candidate pool** box for exclusion reasons. Often other students haven't made their profiles visible yet, or a mandatory rule is too strict. |
| No Research admin buttons | Your account wasn't registered with an e-mail in `ADMIN_EMAILS` (§12, item A3). |

---

### More documentation
- `docs/research-methodology.md`: each equation mapped to code, every ambiguity in the paper and how it was resolved, metric conventions
- `docs/architecture.md`: components, indexes, concurrency design
- `docs/security.md`: the security model in brief
- `docs/deployment.md`: deployment notes (summarised in §11)
- `docs/api.md` and the live OpenAPI document at `/api/docs`: every endpoint
- `research/README.md`: scenario JSON format and CLI
