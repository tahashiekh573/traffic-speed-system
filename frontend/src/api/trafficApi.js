import { API_BASE_URL } from "../config";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error(
      "Backend se connection nahi ho saka. Make sure FastAPI is running on " +
        (API_BASE_URL || window.location.origin)
    );
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join(", ")
      : data.detail;
    const error = new Error(detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }

  return data;
}

export const trafficApi = {
  health: () => request("/health"),
  config: () => request("/api/v1/config"),
  stats: () => request("/api/v1/violations/stats"),
  violations: (limit = 20) => request(`/api/v1/violations?limit=${limit}`),
  uploadVideo(file) {
    const formData = new FormData();
    formData.append("file", file);
    return request("/api/v1/videos/process", { method: "POST", body: formData });
  },
  jobStatus: (id) => request(`/api/v1/videos/${encodeURIComponent(id)}/status`),
  outputUrl: (path) => `${API_BASE_URL}${path}`,
};
