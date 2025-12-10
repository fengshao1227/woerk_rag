import axios from 'axios';

const API_BASE = 'https://rag.litxczv.shop/admin/api';
const RAG_API_BASE = 'https://rag.litxczv.shop';

// 共享的请求拦截器
const addAuthToken = (config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
};

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' }
});

// RAG 问答 API（根路径，需要认证）
const ragApi = axios.create({
  baseURL: RAG_API_BASE,
  headers: { 'Content-Type': 'application/json' }
});

// 两个实例都添加 token 拦截器
api.interceptors.request.use(addAuthToken);
ragApi.interceptors.request.use(addAuthToken);

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
  delete: id => api.delete(`/providers/${id}`),
  // 渠道管理新增
  getRemoteModels: id => api.get(`/providers/${id}/remote-models`),
  getBalance: id => api.get(`/providers/${id}/balance`),
  batchCreateModels: (id, models) => api.post(`/providers/${id}/models/batch`, { models }),
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

// 知识分组 API
export const groupAPI = {
  list: (includeItems = true) => api.get('/groups', { params: { include_items: includeItems } }),
  create: data => api.post('/groups', data),
  get: id => api.get(`/groups/${id}`),
  update: (id, data) => api.put(`/groups/${id}`, data),
  delete: id => api.delete(`/groups/${id}`),
  // 分组内知识条目管理
  listItems: id => api.get(`/groups/${id}/items`),
  addItems: (id, qdrantIds) => api.post(`/groups/${id}/items`, { qdrant_ids: qdrantIds }),
  removeItem: (id, qdrantId) => api.delete(`/groups/${id}/items/${qdrantId}`)
};

// 版本追踪 API
export const versionAPI = {
  list: (qdrantId) => api.get(`/knowledge/${qdrantId}/versions`),
  getDetail: (qdrantId, version) => api.get(`/knowledge/${qdrantId}/versions/${version}`),
  rollback: (qdrantId, targetVersion, reason) =>
    api.post(`/knowledge/${qdrantId}/rollback`, { target_version: targetVersion, reason })
};

export const usageAPI = {
  getLogs: (modelId, providerId, status, days, limit) =>
    api.get('/usage/logs', { params: { model_id: modelId, provider_id: providerId, status, days, limit } }),
  getStats: days => api.get('/usage/stats', { params: { days } })
};

export const testAPI = {
  testModel: data => api.post('/models/test', data)
};

export const chatAPI = {
  query: (question, top_k = 5, use_history = true) =>
    ragApi.post('/query', { question, top_k, use_history }),
  queryStream: async function* (question, top_k = 5, use_history = true) {
    const token = localStorage.getItem('token');
    const response = await fetch(`${RAG_API_BASE}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ question, top_k, use_history })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            yield data;
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  },
  clearHistory: () => ragApi.post('/clear-history')
};

export const evalAPI = {
  listTestCases: (category) => api.get('/eval/test-cases', { params: { category } }),
  createTestCase: (data) => api.post('/eval/test-cases', data),
  updateTestCase: (id, data) => api.put(`/eval/test-cases/${id}`, data),
  deleteTestCase: (id) => api.delete(`/eval/test-cases/${id}`),
  runEvaluation: (testCaseIds, topK = 5) => api.post('/eval/run', { test_case_ids: testCaseIds, top_k: topK }),
  getStats: () => api.get('/eval/stats')
};

export const cacheAPI = {
  getStats: () => api.get('/cache/stats'),
  clear: () => api.post('/cache/clear')
};

export const agentAPI = {
  query: (question) => ragApi.post('/agent', { question }, { timeout: 120000 })
};

export { ragApi };
export default api;
