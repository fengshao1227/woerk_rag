/**
 * 删除知识工具
 */

import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { deleteKnowledge as apiDeleteKnowledge, ApiError } from '../api-client.js';

/** 输入参数 Schema */
export const deleteKnowledgeInputSchema = {
  qdrant_id: z.string().describe('条目 ID（通过 search 获取）'),
};

/**
 * 注册 delete_knowledge 工具
 */
export function registerDeleteKnowledgeTool(server: McpServer): void {
  server.tool(
    'delete_knowledge',
    `删除知识 - 移除指定条目

通过 search 工具获取的 qdrant_id 来删除知识条目。`,
    deleteKnowledgeInputSchema,
    async ({ qdrant_id }) => {
      try {
        await apiDeleteKnowledge(qdrant_id);

        return {
          content: [{
            type: 'text',
            text: `## 删除成功\n\n已删除知识条目 \`${qdrant_id}\``,
          }],
        };
      } catch (error) {
        if (error instanceof ApiError) {
          if (error.isNotFound()) {
            return {
              content: [{
                type: 'text',
                text: `## 未找到\n\n知识条目 \`${qdrant_id}\` 不存在`,
              }],
              isError: true,
            };
          }
          return {
            content: [{ type: 'text', text: `## 错误\n\n${error.formatMessage()}` }],
            isError: true,
          };
        }

        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: 'text', text: `## 错误\n\n删除失败: ${message}` }],
          isError: true,
        };
      }
    }
  );
}
