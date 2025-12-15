/**
 * 语义搜索工具
 */

import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { search as apiSearch, ApiError } from '../api-client.js';
import { config } from '../config.js';

/** 输入参数 Schema */
export const searchInputSchema = {
  query_text: z.string().describe('搜索词或问题（如"Docker部署"、"API认证"）'),
  top_k: z.number().optional().default(5).describe('返回数量，默认5'),
  group_names: z.string().optional().describe('限定分组，逗号分隔'),
  min_score: z.number().optional().describe('最低相似度（0-1），过滤低质量结果'),
};

/**
 * 获取相似度标签
 */
function getScoreLabel(score: number): string {
  if (score >= 0.7) return '高相关';
  if (score >= 0.5) return '中等相关';
  if (score >= config.SEARCH_SCORE_THRESHOLD) return '低相关';
  return '边缘相关';
}

/**
 * 注册 search 工具
 */
export function registerSearchTool(server: McpServer): void {
  server.tool(
    'search',
    `语义搜索 - 快速查找相关知识条目

基于向量相似度检索，不调用 AI，速度快。
适合：查找特定内容、验证知识是否存在、浏览相关条目。`,
    searchInputSchema,
    async ({ query_text, top_k, group_names, min_score }) => {
      try {
        // 解析分组名称
        const groups = group_names
          ? group_names.split(',').map((g) => g.trim()).filter(Boolean)
          : undefined;

        const result = await apiSearch(query_text, top_k ?? 5, groups);
        const results = result.results || [];

        // 应用相似度阈值过滤
        const scoreThreshold = min_score ?? 0;
        const filteredResults = results.filter((r) => (r.score ?? 0) >= scoreThreshold);
        const lowRelevanceCount = results.length - filteredResults.length;

        if (filteredResults.length === 0) {
          if (lowRelevanceCount > 0) {
            return {
              content: [{
                type: 'text',
                text: `## 未找到高相关内容\n\n有 ${lowRelevanceCount} 条结果相似度低于 ${scoreThreshold.toFixed(2)}，已被过滤。\n\n建议尝试其他关键词或降低 min_score 阈值。`,
              }],
            };
          }
          return {
            content: [{
              type: 'text',
              text: '## 未找到相关内容\n\n知识库中没有匹配的内容，建议尝试其他关键词。',
            }],
          };
        }

        // 格式化输出
        let output = `## 搜索结果（共 ${filteredResults.length} 条）\n\n`;

        filteredResults.forEach((item, i) => {
          const content = item.content || '';
          const filePath = item.file_path || '未知';
          const score = item.score ?? 0;
          const title = item.title || '';
          const category = item.category || '';
          const qdrantId = item.qdrant_id || '';

          const preview = content.length > 300 ? content.slice(0, 300) + '...' : content;
          const scoreLabel = getScoreLabel(score);

          output += `### ${i + 1}. ${title || filePath}\n`;
          if (category) {
            output += `- **分类**: ${category}\n`;
          }
          output += `- **来源**: \`${filePath}\`\n`;
          output += `- **相似度**: ${score.toFixed(3)} (${scoreLabel})\n`;
          if (qdrantId) {
            output += `- **ID**: \`${qdrantId}\`\n`;
          }
          output += `- **内容预览**:\n\`\`\`\n${preview}\n\`\`\`\n\n`;
        });

        if (lowRelevanceCount > 0) {
          output += `\n> 另有 ${lowRelevanceCount} 条低相关结果未显示`;
        }

        return {
          content: [{ type: 'text', text: output }],
        };
      } catch (error) {
        if (error instanceof ApiError) {
          return {
            content: [{ type: 'text', text: `## 错误\n\n${error.formatMessage()}` }],
            isError: true,
          };
        }

        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: 'text', text: `## 错误\n\n调用 RAG API 失败: ${message}` }],
          isError: true,
        };
      }
    }
  );
}
