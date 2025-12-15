/**
 * 列出分组工具
 */

import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { listGroups as apiListGroups, ApiError } from '../api-client.js';

/**
 * 注册 list_groups 工具
 */
export function registerListGroupsTool(server: McpServer): void {
  server.tool(
    'list_groups',
    `列出分组 - 查看所有知识分组

返回知识库中所有分组的名称、描述和条目数量。`,
    {},
    async () => {
      try {
        const result = await apiListGroups();
        const groups = result.groups || [];

        if (groups.length === 0) {
          return {
            content: [{
              type: 'text',
              text: '## 暂无分组\n\n知识库中尚未创建任何分组。',
            }],
          };
        }

        let output = `## 知识库分组（共 ${groups.length} 个）\n\n`;

        groups.forEach((group) => {
          const name = group.name || '未命名';
          const description = group.description || '';
          const count = group.items_count ?? group.item_count ?? group.count ?? 0;

          output += `### ${name}\n`;
          if (description) {
            output += `- **描述**: ${description}\n`;
          }
          output += `- **条目数**: ${count}\n\n`;
        });

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
          content: [{ type: 'text', text: `## 错误\n\n获取分组列表失败: ${message}` }],
          isError: true,
        };
      }
    }
  );
}
