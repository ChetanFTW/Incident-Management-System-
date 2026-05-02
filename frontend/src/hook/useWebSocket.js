import { useEffect, useRef, useState, useCallback } from "react";

export function useWebSocket(onMessage) {
  const ws = useRef(null);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    const url = (import.meta.env.VITE_WS_URL || "ws://localhost:8000") + "/ws/feed";
    ws.current = new WebSocket(url);

    ws.current.onopen = () => setConnected(true);
    ws.current.onclose = () => {
      setConnected(false);
      // Auto-reconnect after 3s
      setTimeout(connect, 3000);
    };
    ws.current.onerror = () => ws.current.close();
    ws.current.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)); } catch {}
    };
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => ws.current?.close();
  }, []);

  return connected;
}
