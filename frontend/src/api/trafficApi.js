import { API_BASE_URL } from "../config";

const OFFLINE_MESSAGE = () =>
  "Backend se connection nahi ho saka. Make sure FastAPI is running on " +
  (API_BASE_URL || window.location.origin);

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error(OFFLINE_MESSAGE());
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

  /** Upload with real progress (fetch cannot report upload progress). */
  uploadVideo(file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append("file", file);

      xhr.open("POST", `${API_BASE_URL}/api/v1/videos/process`);
      xhr.responseType = "json";

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress((event.loaded / event.total) * 100);
        }
      };

      xhr.onload = () => {
        const data = xhr.response || {};
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data);
          return;
        }
        const error = new Error(data.detail || `Upload failed (${xhr.status})`);
        error.status = xhr.status;
        reject(error);
      };

      xhr.onerror = () => reject(new Error(OFFLINE_MESSAGE()));
      xhr.send(formData);
    });
  },

  jobStatus: (id) => request(`/api/v1/videos/${encodeURIComponent(id)}/status`),
  previewUrl: (id, stamp) =>
    `${API_BASE_URL}/api/v1/videos/${encodeURIComponent(id)}/preview?t=${stamp}`,
  outputUrl: (path) => `${API_BASE_URL}${path}`,
};
