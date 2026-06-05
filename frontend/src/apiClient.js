import axios from 'axios';

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3001';
export const UPLOADS_BASE = `${API_BASE}/uploads`;

const AUTH_KEY = 'me_auth_token';

export function getAuthToken() {
  return sessionStorage.getItem(AUTH_KEY);
}

export function setAuthToken(token) {
  sessionStorage.setItem(AUTH_KEY, token);
  api.defaults.headers.common['x-auth-token'] = token;
}

export function clearAuthToken() {
  sessionStorage.removeItem(AUTH_KEY);
  delete api.defaults.headers.common['x-auth-token'];
}

export const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers['x-auth-token'] = token;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && getAuthToken()) {
      clearAuthToken();
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

const existing = getAuthToken();
if (existing) {
  api.defaults.headers.common['x-auth-token'] = existing;
}
