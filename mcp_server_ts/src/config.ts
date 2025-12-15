/**
 * MCP Server 配置
 * 从环境变量读取配置项
 */

export const config = {
  /** 远程 RAG API 地址 */
  RAG_API_BASE: process.env.RAG_API_BASE || 'https://rag.litxczv.shop',

  /** MCP API Key (卡密) */
  RAG_API_KEY: process.env.RAG_API_KEY || '',

  /** 搜索结果相似度阈值 */
  SEARCH_SCORE_THRESHOLD: parseFloat(process.env.SEARCH_SCORE_THRESHOLD || '0.4'),

  /** 知识添加最大等待时间（秒） */
  ADD_KNOWLEDGE_MAX_WAIT: parseInt(process.env.ADD_KNOWLEDGE_MAX_WAIT || '120', 10),

  /** 知识添加轮询间隔（秒） */
  ADD_KNOWLEDGE_POLL_INTERVAL: 2,

  /** API Key 验证缓存时间（毫秒） */
  API_KEY_CACHE_TTL: 5 * 60 * 1000, // 5 分钟
};

/**
 * 验证配置是否有效
 */
export function validateConfig(): { valid: boolean; error?: string } {
  if (!config.RAG_API_KEY) {
    return {
      valid: false,
      error: '未配置 RAG_API_KEY 环境变量，请设置 MCP API Key',
    };
  }
  return { valid: true };
}
