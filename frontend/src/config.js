// In production the dashboard is served by FastAPI itself, so API calls
// use the same origin (""). During `npm run dev` they go to port 8000.
// Override either way with VITE_API_BASE_URL in frontend/.env.
const fallbackBase = import.meta.env.DEV ? "http://localhost:8000" : "";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? fallbackBase
).replace(/\/$/, "");

export const POLL_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS || 1000);

// Fallbacks used until /api/v1/config answers.
export const DEFAULT_CONFIG = {
  speed_limit_kmh: 60,
  max_upload_size_mb: 500,
  allowed_video_extensions: ".avi,.mkv,.mov,.mp4",
};
