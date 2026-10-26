import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { io, type Socket } from "socket.io-client";
import { useAuth } from "./AuthContext";

// The socket authenticates with the same HTTP-only session cookie as the API.
// VITE_SOCKET_URL is only needed when the API lives on another (same-site) host;
// VITE_SOCKET_TRANSPORTS=polling forces long-polling, e.g. behind a proxy without WebSocket support.
const SOCKET_URL = (import.meta.env.VITE_SOCKET_URL as string | undefined) || undefined;
const TRANSPORTS = ((import.meta.env.VITE_SOCKET_TRANSPORTS as string | undefined) ?? "websocket,polling").split(",");

interface SocketValue {
  socket: Socket | null;
  connected: boolean;
}

const SocketContext = createContext<SocketValue>({ socket: null, connected: false });

export function SocketProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!user) return;
    const s = io(SOCKET_URL ?? window.location.origin, { withCredentials: true, transports: TRANSPORTS, path: "/socket.io" });
    s.on("connect", () => setConnected(true));
    s.on("disconnect", () => setConnected(false));
    setSocket(s);
    return () => {
      s.disconnect();
      setSocket(null);
      setConnected(false);
    };
  }, [user]);

  return <SocketContext.Provider value={{ socket, connected }}>{children}</SocketContext.Provider>;
}

export function useSocket(): SocketValue {
  return useContext(SocketContext);
}

/** Subscribe to a server event for the lifetime of the component. */
export function useSocketEvent<T>(event: string, handler: (data: T) => void) {
  const { socket } = useSocket();
  useEffect(() => {
    if (!socket) return;
    socket.on(event, handler);
    return () => {
      socket.off(event, handler);
    };
  }, [socket, event, handler]);
}
