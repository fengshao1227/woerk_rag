/**
 * 统计信息工具
 */

import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getStats as apiGetStats, ApiError } from '../api-client.js';

/**
 * 注册 stats 工具
 */
export function registerStatsTool(server: McpServer): void {
  server.tool(
    'stats',
    `统计信息 - 知识库概览

返回知识库的总体统计信息，包括总条目数、分组数、分类分布等。`,
    {},
    async () => {
      try {
        const data = await apiGetStats();

        let output = '## 知识库统计\n\n';

        // 总条目数
        const total = data.total_knowledge ?? data.knowledge_count ?? 0;
        output += `**总条目数**: ${total}\n\n`;

        // 分组数
        const groupCount = data.total_groups ?? data.group_count ?? 0;
        output += `**分组数**: ${groupCount}\n\n`;

        // 分类分布
        const categories = data.categories ?? data.category_stats ?? {};
        if (Object.keys(categories).length > 0) {
          output += '**分类分布**:\n';
          for (const [cat, count] of Object.entries(categories)) {
            output += `- ${cat}: ${count}\n`;
          }
          output += '\n';
        }

        // 用户数
        if (data.total_users) {
          output += `**用户数**: ${data.total_users}\n\n`;
        }

        // 模型数
        if (data.total_models) {
          output += `**LLM 模型数**: ${data.total_models}\n`;
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
          content: [{ type: 'text', text: `## 错误\n\n获取统计信息失败: ${message}` }],
          isError: true,
        };
      }
    }
  );
}
