// Central API configuration — single source of truth for backend URL
const isDev = window.location.hostname === 'localhost';

export const API_BASE = '';

export const WS_URL = import.meta.env.VITE_WS_URL
  || (isDev
    ? `ws://${window.location.hostname}:8000/ws/dashboard`
    : `wss://vaaksetu-x1uf.onrender.com/ws/dashboard`);

/**
 * Ping the /health endpoint.
 * Returns { ok: true, data } on success, { ok: false, error } on failure.
 */
export async function checkHealth() {
  try {
    const res = await fetch(API_BASE + '/health', { signal: AbortSignal.timeout(8000) });
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
    const data = await res.json();
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err.message || 'Network error' };
  }
}
