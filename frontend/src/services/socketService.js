import { getAccessToken } from "./auth";

/**
 * WebSocket service for real-time updates.
 *
 * Endpoints:
 *   ws(s)://host/ws/admin/
 *   ws(s)://host/ws/director/
 *   ws(s)://host/ws/super-admin/
 *
 * Auth: token sent as query param ?token=<access>
 */

function getWsBase() {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  // Derive from API URL: https://host/api/v1 → wss://host
  const apiUrl = import.meta.env.VITE_API_URL;
  if (apiUrl) {
    try {
      const url = new URL(apiUrl);
      const protocol = url.protocol === "https:" ? "wss:" : "ws:";
      return `${protocol}//${url.host}`;
    } catch {
      // fall through to default
    }
  }
  return "ws://localhost:8000";
}

const WS_BASE = getWsBase();

// Active connections keyed by path (e.g. "/ws/admin/")
const connections = {};

// Subscriber maps keyed by path → event → Set<callback>
const subscribers = {};

// Reconnect timers keyed by path
const reconnectTimers = {};

const RECONNECT_DELAY = 3000; // ms
const MAX_RECONNECT_ATTEMPTS = 10;
const reconnectAttempts = {};

/**
 * Connect to a WebSocket channel.
 * @param {string} channel - "admin" | "director" | "super-admin"
 * @returns {WebSocket|null}
 */
export function connect(channel) {
  const path = `/ws/${channel}/`;

  // Prevent duplicate connections
  if (connections[path]?.readyState === WebSocket.OPEN ||
      connections[path]?.readyState === WebSocket.CONNECTING) {
    return connections[path];
  }

  const token = getAccessToken();
  if (!token) {
    return null;
  }

  const url = `${WS_BASE}${path}?token=${encodeURIComponent(token)}`;

  try {
    const ws = new WebSocket(url);
    connections[path] = ws;
    reconnectAttempts[path] = 0;

    ws.onopen = () => {
      reconnectAttempts[path] = 0;
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const eventType = message.type || message.event;
        if (!eventType) return;

        const pathSubs = subscribers[path];
        if (!pathSubs) return;

        // Notify exact event subscribers
        const handlers = pathSubs[eventType];
        if (handlers) {
          handlers.forEach((cb) => cb(message.data ?? message.payload ?? message));
        }

        // Notify wildcard subscribers
        const wildcardHandlers = pathSubs["*"];
        if (wildcardHandlers) {
          wildcardHandlers.forEach((cb) => cb(eventType, message.data ?? message.payload ?? message));
        }
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = (event) => {
      delete connections[path];

      // Auto-reconnect unless intentional close (code 1000) or max attempts
      if (event.code !== 1000 && (reconnectAttempts[path] ?? 0) < MAX_RECONNECT_ATTEMPTS) {
        scheduleReconnect(channel, path);
      }
    };

    ws.onerror = () => {
      // Error will trigger onclose, so reconnect is handled there
    };

    return ws;
  } catch {
    return null;
  }
}

/**
 * Schedule a reconnection attempt.
 */
function scheduleReconnect(channel, path) {
  if (reconnectTimers[path]) return;

  reconnectAttempts[path] = (reconnectAttempts[path] ?? 0) + 1;
  const delay = RECONNECT_DELAY * Math.min(reconnectAttempts[path], 5);

  reconnectTimers[path] = setTimeout(() => {
    delete reconnectTimers[path];
    connect(channel);
  }, delay);
}

/**
 * Subscribe to a specific event on a channel.
 * @param {string} channel - "admin" | "director" | "super-admin"
 * @param {string} eventType - e.g. "booking_created", "cleaning_task_updated", or "*" for all
 * @param {Function} callback - (data) => void  (or (eventType, data) for wildcard)
 * @returns {Function} unsubscribe function
 */
export function subscribe(channel, eventType, callback) {
  const path = `/ws/${channel}/`;

  if (!subscribers[path]) {
    subscribers[path] = {};
  }
  if (!subscribers[path][eventType]) {
    subscribers[path][eventType] = new Set();
  }

  subscribers[path][eventType].add(callback);

  // Return unsubscribe function
  return () => {
    subscribers[path]?.[eventType]?.delete(callback);
    if (subscribers[path]?.[eventType]?.size === 0) {
      delete subscribers[path][eventType];
    }
  };
}

/**
 * Disconnect from a WebSocket channel.
 * @param {string} channel - "admin" | "director" | "super-admin"
 */
export function disconnect(channel) {
  const path = `/ws/${channel}/`;

  // Clear reconnect timer
  if (reconnectTimers[path]) {
    clearTimeout(reconnectTimers[path]);
    delete reconnectTimers[path];
  }

  // Reset attempts
  delete reconnectAttempts[path];

  // Close connection
  const ws = connections[path];
  if (ws) {
    ws.close(1000, "Client disconnect");
    delete connections[path];
  }

  // Clear subscribers
  delete subscribers[path];
}

/**
 * Disconnect all channels.
 */
export function disconnectAll() {
  Object.keys(connections).forEach((path) => {
    const channel = path.replace("/ws/", "").replace("/", "");
    disconnect(channel);
  });
}
