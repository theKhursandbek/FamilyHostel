import { useEffect, useRef } from "react";
import { connect, subscribe, disconnect } from "../services/socketService";

/**
 * React hook for WebSocket real-time updates.
 *
 * @param {string} channel - "admin" | "director" | "super-admin"
 * @param {Object<string, Function>} handlers - { event_name: (data) => void }
 * @param {boolean} [enabled=true] - whether to connect
 *
 * Usage:
 *   useSocket("admin", {
 *     booking_created: (data) => fetchDashboard(),
 *     payment_completed: (data) => fetchDashboard(),
 *   });
 */
export function useSocket(channel, handlers, enabled = true) {
  // Use a ref so the subscribe effect doesn't re-run when the caller passes
  // a fresh handlers object on every render. Refs may not be written during
  // render (React 19 rule), so we sync inside an effect.
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    if (!enabled || !channel) return;

    // Connect to the channel
    connect(channel);

    // Subscribe to each event
    // Subscribe once per event-type; the handler itself is read from the
    // ref at dispatch time so callers always see the latest closure without
    // forcing this effect to re-run.
    const unsubscribers = Object.keys(handlersRef.current).map(
      (eventType) =>
        subscribe(channel, eventType, (data) => {
          // Always call the latest handler via ref
          handlersRef.current[eventType]?.(data);
        })
    );

    return () => {
      // Unsubscribe all handlers
      unsubscribers.forEach((unsub) => unsub());
      // Disconnect the channel
      disconnect(channel);
    };
  }, [channel, enabled]);
}
