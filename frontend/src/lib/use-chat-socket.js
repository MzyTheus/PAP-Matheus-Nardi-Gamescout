import { useEffect, useRef } from "react";

/**
 * Hook: open a WebSocket to the backend chat channel and call onMessage(parsedJSON)
 * for every server-pushed event. Auto-reconnects with exponential backoff.
 *
 * kind: 'dm' | 'community'
 * targetId: friend user_id or community_id
 */
export function useChatSocket({ kind, targetId, onMessage }) {
  const wsRef = useRef(null);
  const reconnectRef = useRef(0);
  const cbRef = useRef(onMessage);

  // Keep latest callback without retriggering the effect.
  useEffect(() => { cbRef.current = onMessage; }, [onMessage]);

  useEffect(() => {
    if (!kind || !targetId) return;
    let pingId = null;
    let closed = false;

    const connect = () => {
      const origin = (typeof window !== "undefined" && window.location && window.location.origin) || "";
      const wsUrl = origin.replace(/^http/, "ws") + `/api/ws/chat/${kind}/${targetId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectRef.current = 0;
        pingId = setInterval(() => {
          try { ws.send("ping"); } catch (_) {}
        }, 25000);
      };
      ws.onmessage = (ev) => {
        if (ev.data === "pong") return;
        try {
          const data = JSON.parse(ev.data);
          cbRef.current && cbRef.current(data);
        } catch (_) {}
      };
      ws.onclose = () => {
        if (pingId) clearInterval(pingId);
        if (closed) return;
        const wait = Math.min(1000 * 2 ** reconnectRef.current, 15000);
        reconnectRef.current += 1;
        setTimeout(connect, wait);
      };
      ws.onerror = () => { try { ws.close(); } catch (_) {} };
    };

    connect();
    return () => {
      closed = true;
      if (pingId) clearInterval(pingId);
      try { wsRef.current && wsRef.current.close(); } catch (_) {}
    };
  }, [kind, targetId]);

  return wsRef;
}
