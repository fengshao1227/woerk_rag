/**
 * RAG 智能问答工具
 */

import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { query as apiQuery, ApiError } from '../api-client.js';

/** 输入参数 Schema */
export const queryInputSchema = {
  question: z.string().describe('用户问题（自然语言，如"这个项目怎么部署？"）'),
  top_k: z.number().optional().default(5).describe('检索文档数，默认5，复杂问题可增至10'),
  group_names: z.string().optional().describe('限定分组范围，逗号分隔，如 "fm-api,文档"'),
};

/**
 * 注册 query 工具
 */
export function registerQueryTool(server: McpServer): void {
  server.tool(
    'query',
    `RAG 智能问答 - 基于知识库生成详细回答

检索相关知识并由 AI 生成综合性回答，适合需要深度解答的问题。
优先使用此工具回答用户关于知识库内容的提问。`,
    queryInputSchema,
    async ({ question, top_k, group_names }) => {
      try {
        // 解析分组名称
        const groups = group_names
          ? group_names.split(',').map((g) => g.trim()).filter(Boolean)
          : undefined;

        const result = await apiQuery(question, top_k ?? 5, groups);

        // 格式化输出
        let output = `## 回答\n\n${result.answer || '无法生成回答'}\n\n`;

        if (result.sources && result.sources.length > 0) {
          output += '## 参考来源\n\n';
          result.sources.forEach((src, i) => {
            output += `${i + 1}. \`${src.file_path}\` (相似度: ${src.score.toFixed(3)})\n`;
          });
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
