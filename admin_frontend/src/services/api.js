import axios from 'axios';

const API_BASE = 'https://rag.litxczv.shop/admin/api';
const RAG_API_BASE = 'https://rag.litxczv.shop';

// Token 管理
const TokenManager = {
  getAccessToken: () => localStorage.getItem('token'),
  getRefreshToken: () => localStorage.getItem('refreshToken'),
  getTokenExpiry: () => parseInt(localStorage.getItem('tokenExpiry') || '0'),

  setTokens: (accessToken, refreshToken, expiresIn) => {
    localStorage.setItem('token', accessToken);
    if (refreshToken) {
      localStorage.setItem('refreshToken', refreshToken);
    }
    // 设置过期时间（提前5分钟刷新）
    const expiry = Date.now() + (expiresIn - 300) * 1000;
    localStorage.setItem('tokenExpiry', expiry.toString());
  },

  clearTokens: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('tokenExpiry');
    localStorage.removeItem('user');
  },

  isTokenExpired: () => {
    const expiry = TokenManager.getTokenExpiry();
    return Date.now() >= expiry;
  },

  shouldRefresh: () => {
    const expiry = TokenManager.getTokenExpiry();
    // 提前5分钟刷新
    return Date.now() >= expiry - 300000;
  }
};

// 刷新 Token 的 Promise（防止并发刷新）
let refreshPromise = null;

const refreshAccessToken = async () => {
  if (refreshPromise) {
    return refreshPromise;
  }

  const refreshToken = TokenManager.getRefreshToken();
  if (!refreshToken) {
    throw new Error('No refresh token');
  }

  refreshPromise = axios.post(`${API_BASE}/auth/refresh`, {
    refresh_token: refreshToken
  }).then(response => {
    const { access_token, expires_in } = response.data;
    TokenManager.setTokens(access_token, null, expires_in);
    refreshPromise = null;
    return access_token;
  }).catch(error => {
    refreshPromise = null;
    TokenManager.clearTokens();
    throw error;
  });

  return refreshPromise;
};

// 共享的请求拦截器
const addAuthToken = async (config) => {
  // 跳过刷新请求本身
  if (config.url?.includes('/auth/refresh') || config.url?.includes('/auth/login')) {
    return config;
  }

  let token = TokenManager.getAccessToken();

  // 检查是否需要刷新
  if (token && TokenManager.shouldRefresh()) {
    try {
      token = await refreshAccessToken();
    } catch (error) {
      // 刷新失败，继续使用旧 token（可能已过期）
      console.warn('Token refresh failed:', error);
    }
  }

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

// 响应拦截器 - 处理 401 错误并尝试刷新
const handleResponseError = async (error) => {
  const originalRequest = error.config;

  // 排除登录和刷新接口
  const isAuthRequest = originalRequest?.url?.includes('/auth/login') ||
                        originalRequest?.url?.includes('/auth/refresh');

  if (error.response?.status === 401 && !isAuthRequest && !originalRequest._retry) {
    originalRequest._retry = true;

    try {
      const newToken = await refreshAccessToken();
      originalRequest.headers.Authorization = `Bearer ${newToken}`;
      return axios(originalRequest);
    } catch (refreshError) {
      TokenManager.clearTokens();
      window.location.href = '/login';
      return Promise.reject(refreshError);
    }
  }

  // 其他 401 错误直接跳转登录
  if (error.response?.status === 401 && !isAuthRequest) {
    TokenManager.clearTokens();
    window.location.href = '/login';
  }

  return Promise.reject(error);
};

api.interceptors.response.use(response => response, handleResponseError);
ragApi.interceptors.response.use(response => response, handleResponseError);

export const authAPI = {
  login: async (username, password) => {
    const response = await api.post('/auth/login', { username, password });
    const { access_token, refresh_token, expires_in, user } = response.data;
    TokenManager.setTokens(access_token, refresh_token, expires_in);
    localStorage.setItem('user', JSON.stringify(user));
    return response;
  },
  getMe: () => api.get('/auth/me'),
  logout: () => {
    TokenManager.clearTokens();
    window.location.href = '/login';
  },
  changePassword: (oldPassword, newPassword) =>
    api.post('/auth/change-password', null, {
      params: { old_password: oldPassword, new_password: newPassword }
    })
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
  list: (page, pageSize, category, search, groupId) =>
    api.get('/knowledge', { params: { page, page_size: pageSize, category, search, group_id: groupId } }),
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
  removeItem: (id, qdrantId) => api.delete(`/groups/${id}/items`, { data: { qdrant_ids: [qdrantId] } }),
  // 分组共享管理
  listShares: id => api.get(`/groups/${id}/shares`),
  createShare: (id, userId, permission) => api.post(`/groups/${id}/shares`, { shared_with_user_id: userId, permission }),
  updateShare: (groupId, shareId, permission) => api.put(`/groups/${groupId}/shares/${shareId}`, { permission }),
  deleteShare: (groupId, shareId) => api.delete(`/groups/${groupId}/shares/${shareId}`),
  // 获取共享给我的分组
  listSharedWithMe: () => api.get('/my-shared-groups')
};

// 用户 API
export const userAPI = {
  list: () => api.get('/users'),
  create: (data) => api.post('/users', data),
  get: (id) => api.get(`/users/${id}`),
  update: (id, data) => api.put(`/users/${id}`, data),
  delete: (id) => api.delete(`/users/${id}`),
  listForShare: () => api.get('/users/list')
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
  query: (question, top_k = 5, use_history = true, group_names = null) =>
    ragApi.post('/query', { question, top_k, use_history, group_names }),
  queryStream: async function* (question, top_k = 5, use_history = true, group_names = null) {
    const token = TokenManager.getAccessToken();
    const response = await fetch(`${RAG_API_BASE}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ question, top_k, use_history, group_names })
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

export const embeddingProviderAPI = {
  list: () => api.get('/embedding-providers'),
  create: (data) => api.post('/embedding-providers', data),
  get: (id) => api.get(`/embedding-providers/${id}`),
  update: (id, data) => api.put(`/embedding-providers/${id}`, data),
  delete: (id) => api.delete(`/embedding-providers/${id}`),
  setDefault: (id) => api.post(`/embedding-providers/${id}/set-default`),
  test: (id, text) => api.post(`/embedding-providers/${id}/test`, { text })
};

export const apiKeysAPI = {
  list: () => api.get('/api-keys'),
  create: (data) => api.post('/api-keys', data),
  get: (id) => api.get(`/api-keys/${id}`),
  update: (id, data) => api.put(`/api-keys/${id}`, data),
  delete: (id) => api.delete(`/api-keys/${id}`)
};

export { ragApi, TokenManager };
export default api;
