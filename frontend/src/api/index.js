import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 600000,
});

export function getHealth() {
  return api.get("/health");
}

export function getStyles() {
  return api.get("/styles");
}

export function uploadAudio(file) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/upload", formData);
}

export function startConvert(fileId, style, params = {}) {
  return api.post("/convert", { file_id: fileId, style, params });
}

export function getNeuralStatus() {
  return api.get("/neural/status");
}

export function startNeuralConvert(fileId, payload = {}) {
  return api.post("/neural/convert", { file_id: fileId, ...payload });
}

export function getRealtimeStatus() {
  return api.get("/realtime/status");
}

export function startRealtime(payload = {}) {
  return api.post("/realtime/start", payload);
}

export function stopRealtime() {
  return api.post("/realtime/stop");
}

export function getTaskStatus(taskId) {
  return api.get(`/status/${taskId}`);
}

export function cancelTask(taskId) {
  return api.post(`/cancel/${taskId}`);
}

export function getDownloadUrl(filename) {
  return `/api/download/${encodeURIComponent(filename)}`;
}

export function getHistory(limit = 20) {
  return api.get("/history", { params: { limit } });
}

export function getReport() {
  return api.get("/report");
}

export default api;
