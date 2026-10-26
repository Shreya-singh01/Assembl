import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, setCsrfToken } from "../api/client";
import type { User } from "../api/types";

interface SessionResponse {
  user: User;
  csrf_token: string;
}

interface AuthValue {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: { email: string; password: string; display_name: string; handle: string; accept_terms: boolean }) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setUser: (u: User | null) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const accept = (s: SessionResponse) => {
    setCsrfToken(s.csrf_token);
    setUser(s.user);
    return s.user;
  };

  const refresh = useCallback(async () => {
    try {
      accept(await api.get<SessionResponse>("/auth/me"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setCsrfToken(null);
        setUser(null);
      } else throw e;
    }
  }, []);

  useEffect(() => {
    refresh()
      .catch(() => setUser(null))
      .finally(() => setReady(true));
  }, [refresh]);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      ready,
      setUser,
      refresh,
      login: async (email, password) => accept(await api.post<SessionResponse>("/auth/login", { email, password })),
      register: async (data) => accept(await api.post<SessionResponse>("/auth/register", data)),
      logout: async () => {
        try {
          await api.post("/auth/logout");
        } finally {
          setCsrfToken(null);
          setUser(null);
        }
      },
    }),
    [user, ready, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
