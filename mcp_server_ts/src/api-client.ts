/**
 * RAG API Client
 * 封装对远程 RAG API 的调用
 */

import { config } from './config.js';

// API Key 验证缓存
let apiKeyVerified = false;
let apiKeyVerifyTime = 0;

/**
 * 获取认证请求头
 */
function getAuthHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-API-Key': config.RAG_API_KEY,
    'X-MCP-Client': 'true',
  };
}

/**
 * 验证 API Key 是否有效（带缓存）
 */
export async function verifyApiKey(): Promise<boolean> {
  if (!config.RAG_API_KEY) {
    return false;
  }

  // 检查缓存
  const now = Date.now();
  if (apiKeyVerified && (now - apiKeyVerifyTime) < config.API_KEY_CACHE_TTL) {
    return true;
  }

  try {
    const response = await fetch(`${config.RAG_API_BASE}/mcp/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: config.RAG_API_KEY }),
    });

    if (!response.ok) {
      apiKeyVerified = false;
      return false;
    }

    const data = await response.json() as { valid?: boolean };
    if (data.valid) {
      apiKeyVerified = true;
      apiKeyVerifyTime = now;
      return true;
    }

    apiKeyVerified = false;
    return false;
  } catch (error) {
    console.error('API Key 验证失败:', error);
    return false;
  }
}

/**
 * RAG 智能问答
 */
export async function query(
  question: string,
  topK: number = 5,
  groupNames?: string[]
): Promise<{ answer: string; sources: Array<{ file_path: string; score: number }> }> {
  const response = await fetch(`${config.RAG_API_BASE}/query`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      question,
      top_k: topK,
      group_names: groupNames,
    }),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json();
}

/**
 * 语义搜索
 */
export async function search(
  queryText: string,
  topK: number = 5,
  groupNames?: string[]
): Promise<{
  results: Array<{
    content: string;
    file_path: string;
    score: number;
    title?: string;
    category?: string;
    qdrant_id?: string;
  }>;
}> {
  const response = await fetch(`${config.RAG_API_BASE}/search`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      query: queryText,
      top_k: topK,
      group_names: groupNames,
    }),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json();
}

/**
 * 添加知识（异步任务）
 */
export async function addKnowledge(
  content: string,
  title?: string,
  category: string = 'general',
  groupNames?: string[]
): Promise<{ task_id?: string; qdrant_id?: string; title?: string; summary?: string; keywords?: string[] }> {
  const response = await fetch(`${config.RAG_API_BASE}/add_knowledge`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      content,
      title,
      category,
      group_names: groupNames,
    }),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json();
}

/**
 * 查询添加知识任务状态
 */
export async function getAddKnowledgeStatus(
  taskId: string
): Promise<{ status: string; result_id?: string; message?: string }> {
  const response = await fetch(`${config.RAG_API_BASE}/add_knowledge/status/${taskId}`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json();
}

/**
 * 删除知识
 */
export async function deleteKnowledge(qdrantId: string): Promise<{ success: boolean }> {
  const response = await fetch(
    `${config.RAG_API_BASE}/admin/api/knowledge/by-qdrant-id/${qdrantId}`,
    {
      method: 'DELETE',
      headers: getAuthHeaders(),
    }
  );

  if (response.status === 404) {
    throw new ApiError(404, '知识条目不存在');
  }

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return { success: true };
}

/**
 * 列出分组
 */
export async function listGroups(): Promise<{
  groups: Array<{
    name: string;
    description?: string;
    items_count?: number;
    item_count?: number;
    count?: number;
  }>;
}> {
  const response = await fetch(`${config.RAG_API_BASE}/admin/api/groups`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  const data = await response.json();

  // 兼容不同的返回格式
  if (Array.isArray(data)) {
    return { groups: data };
  }
  if (data.items) {
    return { groups: data.items };
  }
  if (data.groups) {
    return { groups: data.groups };
  }

  return { groups: [] };
}

/**
 * 获取统计信息
 */
export async function getStats(): Promise<{
  total_knowledge?: number;
  knowledge_count?: number;
  total_groups?: number;
  group_count?: number;
  categories?: Record<string, number>;
  category_stats?: Record<string, number>;
  total_users?: number;
  total_models?: number;
}> {
  const response = await fetch(`${config.RAG_API_BASE}/admin/api/stats`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json();
}

/**
 * API 错误类
 */
export class ApiError extends Error {
  constructor(
    public statusCode: number,
    public details: string
  ) {
    super(`HTTP ${statusCode}: ${details}`);
    this.name = 'ApiError';
  }

  /** 是否为认证错误 */
  isAuthError(): boolean {
    return this.statusCode === 401 || this.statusCode === 403;
  }

  /** 是否为未找到错误 */
  isNotFound(): boolean {
    return this.statusCode === 404;
  }

  /** 格式化错误消息 */
  formatMessage(): string {
    if (this.statusCode === 401) {
      return '认证失败，请检查 API Key 配置是否正确';
    }
    if (this.statusCode === 403) {
      return '权限不足，当前 API Key 没有访问该资源的权限';
    }
    if (this.statusCode === 404) {
      return '资源不存在';
    }
    return `请求失败 (HTTP ${this.statusCode}): ${this.details}`;
  }
}
