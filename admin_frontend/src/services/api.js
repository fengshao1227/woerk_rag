import axios from 'axios';

const API_BASE = 'https://rag.litxczv.shop/admin/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' }
});

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  response => response,
  error => {
    // 排除登录接口，避免循环重定向
    const isLoginRequest = error.config?.url?.includes('/auth/login');
    if (error.response?.status === 401 && !isLoginRequest) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  getMe: () => api.get('/auth/me')
};

export const statsAPI = {
  getStats: () => api.get('/stats')
};

export const providerAPI = {
  list: () => api.get('/providers'),
  create: data => api.post('/providers', data),
  get: id => api.get(`/providers/${id}`),
  update: (id, data) => api.put(`/providers/${id}`, data),
  delete: id => api.delete(`/providers/${id}`)
};

export const modelAPI = {
  list: (providerId) => api.get('/models', { params: { provider_id: providerId } }),
  create: data => api.post('/models', data),
  get: id => api.get(`/models/${id}`),
  update: (id, data) => api.put(`/models/${id}`, data),
  delete: id => api.delete(`/models/${id}`),
  setDefault: id => api.post(`/models/${id}/set-default`)
};

export const knowledgeAPI = {
  list: (page, pageSize, category, search) =>
    api.get('/knowledge', { params: { page, page_size: pageSize, category, search } }),
  get: id => api.get(`/knowledge/${id}`),
  update: (id, data) => api.put(`/knowledge/${id}`, data),
  delete: id => api.delete(`/knowledge/${id}`),
  export: category => api.get('/knowledge/export/all', { params: { category } }),
  import: file => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/knowledge/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  }
};

export const usageAPI = {
  getLogs: (modelId, providerId, status, days, limit) =>
    api.get('/usage/logs', { params: { model_id: modelId, provider_id: providerId, status, days, limit } }),
  getStats: days => api.get('/usage/stats', { params: { days } })
};

export const testAPI = {
  testModel: data => api.post('/models/test', data)
};

export default api;
