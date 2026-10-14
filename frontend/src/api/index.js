import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 300000, // 5 分钟超时（转换可能较慢）
});

export function getHealth() {
  return api.get("/health");
}

export function getStyles() {
  return api.get("/styles");
}

export function uploadAudio(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: onProgress,
  });
}

export function startConvert(fileId, style) {
  return api.post("/convert", { file_id: fileId, style });
}

export function getTaskStatus(taskId) {
  return api.get(`/status/${taskId}`);
}

export function getDownloadUrl(filename) {
  return `/api/download/${filename}`;
}

export function getHistory(limit = 20) {
  return api.get("/history", { params: { limit } });
}

export function getReport() {
  return api.get("/report");
}

export default api;
