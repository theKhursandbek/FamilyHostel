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
  // Use ref to avoid re-subscribing on every render
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!enabled || !channel) return;

    // Connect to the channel
    connect(channel);

    // Subscribe to each event
    const unsubscribers = Object.entries(handlersRef.current).map(
      ([eventType, _handler]) =>
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
