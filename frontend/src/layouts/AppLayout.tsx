import { useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../app/AuthContext";
import { useSocket } from "../app/SocketContext";

const nav = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/projects", label: "Discover" },
  { to: "/invitations", label: "Invitations" },
  { to: "/messages", label: "Messages" },
  { to: "/research", label: "Research" },
];

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight text-ink">
      <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden>
        <circle cx="8" cy="9" r="4" fill="#1f6f5c" />
        <circle cx="16" cy="9" r="4" fill="#2f8a74" opacity=".75" />
        <circle cx="12" cy="16" r="4" fill="#b4541a" opacity=".85" />
      </svg>
      Assembl
    </Link>
  );
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const { connected } = useSocket();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-paper-sunk font-medium text-ink" : "text-ink-soft hover:text-ink"}`;

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-20 border-b border-line bg-paper/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
          <Logo />
          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            {nav.map((n) => (
              <NavLink key={n.to} to={n.to} className={linkClass}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="hidden items-center gap-3 md:flex">
            <span
              className={`h-2 w-2 rounded-full ${connected ? "bg-brand-500" : "bg-line"}`}
              title={connected ? "Live updates connected" : "Live updates offline"}
              aria-label={connected ? "Live updates connected" : "Live updates offline"}
            />
            <NavLink to="/profile" className={linkClass}>
              {user?.display_name}
            </NavLink>
            <button
              className="text-sm text-ink-soft hover:text-ink"
              onClick={async () => {
                await logout();
                navigate("/");
              }}
            >
              Sign out
            </button>
          </div>
          <button className="rounded p-2 md:hidden" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen(!open)}>
            <span className="sr-only">Menu</span>
            <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
              <path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="1.6" />
            </svg>
          </button>
        </div>
        {open && (
          <nav id="mobile-nav" aria-label="Mobile" className="border-t border-line px-4 py-2 md:hidden">
            {[...nav, { to: "/profile", label: "My profile" }, { to: "/settings", label: "Privacy & account" }].map((n) => (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => `block rounded px-2 py-2 text-sm ${isActive ? "bg-paper-sunk" : ""}`} onClick={() => setOpen(false)}>
                {n.label}
              </NavLink>
            ))}
            <button className="block w-full rounded px-2 py-2 text-left text-sm" onClick={() => logout().then(() => navigate("/"))}>
              Sign out
            </button>
          </nav>
        )}
      </header>
      <main id="main" className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

export function Footer({ children }: { children?: ReactNode }) {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-wrap justify-between gap-2 px-4 py-6 text-xs text-ink-soft">
        <span>Assembl · a research prototype for team-aware teammate recommendation</span>
        <span className="flex gap-4">
          <Link to="/how-it-works" className="hover:text-ink">
            How ranking works
          </Link>
          <Link to="/privacy" className="hover:text-ink">
            Privacy
          </Link>
          {children}
        </span>
      </div>
    </footer>
  );
}

export function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <Logo />
          <nav className="flex items-center gap-4 text-sm">
            <Link to="/how-it-works" className="text-ink-soft hover:text-ink">
              How it works
            </Link>
            <Link to="/login" className="text-ink-soft hover:text-ink">
              Sign in
            </Link>
          </nav>
        </div>
      </header>
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
