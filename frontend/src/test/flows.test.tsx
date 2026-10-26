import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../app/AuthContext";
import { App } from "../app/App";
import { api, setCsrfToken } from "../api/client";
import { RecommendationsPage } from "../features/recommendations/RecommendationsPage";
import { candidate, recommendations } from "./fixtures";

vi.mock("socket.io-client", () => ({ io: () => ({ on: vi.fn(), off: vi.fn(), disconnect: vi.fn(), timeout: vi.fn() }) }));

type Handler = (url: string, init: RequestInit) => { status: number; body?: unknown };

function mockFetch(handler: Handler) {
  const fn = vi.fn(async (url: string, init: RequestInit = {}) => {
    const { status, body } = handler(url, init);
    return new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

const USER = { id: "u1", email: "a@x.edu", display_name: "Asha", handle: "asha", role: "student", created_at: "2026-01-01T00:00:00Z", consent: {}, profile_complete: true };

beforeEach(() => setCsrfToken(null));
afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("sends the CSRF token on state-changing requests only, with credentials", async () => {
    const f = mockFetch(() => ({ status: 200, body: {} }));
    setCsrfToken("tok");
    await api.get("/x");
    await api.post("/y", { a: 1 });
    const [getCall, postCall] = f.mock.calls;
    expect((getCall[1] as RequestInit).headers).not.toHaveProperty("X-CSRF-Token");
    expect((postCall[1] as RequestInit).headers).toMatchObject({ "X-CSRF-Token": "tok" });
    expect((postCall[1] as RequestInit).credentials).toBe("include");
  });
});

describe("login journey", () => {
  it("redirects anonymous users to sign in, then shows the error from the server", async () => {
    mockFetch((url) => {
      if (url.endsWith("/auth/me")) return { status: 401, body: { detail: "Not signed in" } };
      if (url.endsWith("/auth/login")) return { status: 401, body: { detail: "Incorrect e-mail or password" } };
      return { status: 404, body: {} };
    });
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("E-mail"), "a@x.edu");
    await userEvent.type(screen.getByLabelText("Password"), "wrongpassword");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect e-mail or password");
  });

  it("shows an honest empty dashboard for a new user", async () => {
    mockFetch((url) => {
      if (url.endsWith("/auth/me")) return { status: 200, body: { user: USER, csrf_token: "t" } };
      if (url.endsWith("/dashboard"))
        return {
          status: 200,
          body: {
            profile_completion: { percent: 0, missing: ["Skills with proficiency"], ready_for_matching: false },
            profile_visible: false,
            my_projects: [],
            pending_received: [],
            recent_sent: [],
            recent_conversations: [],
            suggested_projects: [],
          },
        };
      return { status: 404, body: {} };
    });
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByText("You are not on a team yet")).toBeInTheDocument();
    expect(screen.getByText("Add your skills to be found")).toBeInTheDocument();
    expect(screen.getByText("Nothing pending.")).toBeInTheDocument();
  });
});

describe("recommendations journey", () => {
  it("lists ranked candidates, shows weights, and sends an invitation", async () => {
    const recs = recommendations([
      candidate({ id: "b", name: "Bea", score: 0.85, contributions: { sem: 0.2, gap: 0.45, role: 0.2 } }),
      candidate({ id: "f", name: "Fred", score: 0.34, contributions: { sem: 0.34 }, rank: 2 }),
    ]);
    const posted: unknown[] = [];
    mockFetch((url, init) => {
      if (url.includes("/recommendations")) return { status: 200, body: recs };
      if (url.endsWith("/projects/p1"))
        return { status: 200, body: { id: "p1", title: "Placement prep", vacant_roles: ["Backend"], viewer: { is_owner: true } } };
      if (url.endsWith("/projects/p1/invitations") && init.method === "POST") {
        posted.push(JSON.parse(init.body as string));
        return { status: 201, body: {} };
      }
      return { status: 404, body: {} };
    });
    render(
      <MemoryRouter initialEntries={["/projects/p1/recommendations"]}>
        <Routes>
          <Route path="/projects/:projectId/recommendations" element={<RecommendationsPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Find members for Placement prep" })).toBeInTheDocument();
    const names = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(names[0]).toContain("Bea");
    expect(screen.getByText(/Not used for this request/)).toHaveTextContent("the team does not work synchronously");
    expect(screen.getByText(/3 visible · 2 eligible · 1 excluded/)).toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: "Invite" })[0]);
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0]).toMatchObject({ candidate_id: "b", role: "Backend" });
    expect(await screen.findByText(/Invitation sent to Bea/)).toBeInTheDocument();
  });
});
