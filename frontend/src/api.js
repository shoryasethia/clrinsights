/**
 * Returns the full URL for a backend API path.
 *
 * In local dev (no VITE_API_URL set):
 *   apiUrl('/api/chat') → '/api/chat'   (Vite proxy strips /api and forwards to localhost:8000)
 *
 * In production (VITE_API_URL = 'https://clrinsights-api.onrender.com'):
 *   apiUrl('/api/chat') → 'https://clrinsights-api.onrender.com/chat'
 */
const API_BASE = import.meta.env.VITE_API_URL || ''

export function apiUrl(path) {
  if (API_BASE) {
    // Strip the /api prefix — the Render backend serves routes at / not /api/
    return `${API_BASE}${path.replace(/^\/api/, '')}`
  }
  return path
}
