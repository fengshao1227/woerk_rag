/**
 * 添加知识工具
 */

import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { addKnowledge as apiAddKnowledge, getAddKnowledgeStatus, ApiError } from '../api-client.js';
import { config } from '../config.js';

/** 输入参数 Schema */
export const addKnowledgeInputSchema = {
  content: z.string().min(10).describe('知识内容（至少10字符，建议结构化描述）'),
  title: z.string().optional().describe('可选标题，留空则 AI 自动生成'),
  category: z
    .enum(['project', 'skill', 'experience', 'note', 'general'])
    .optional()
    .default('general')
    .describe('分类: project(项目)/skill(技能)/experience(经验)/note(笔记)/general(通用)'),
  group_names: z.string().optional().describe('添加到分组，逗号分隔'),
};

/**
 * 等待指定毫秒
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * 格式化添加结果
 */
function formatAddResult(
  result: {
    title?: string;
    summary?: string;
    keywords?: string[];
    tech_stack?: string[];
    category?: string;
    qdrant_id?: string;
    id?: string;
    result_id?: string;
  },
  category: string,
  groups?: string[]
): string {
  let output = '## 知识添加成功\n\n';

  const title = result.title;
  if (title && title !== '未命名' && title !== '未命名知识') {
    output += `**标题**: ${title}\n\n`;
  } else {
    output += '**标题**: （AI 自动生成中...）\n\n';
  }

  if (result.summary) {
    output += `**摘要**: ${result.summary}\n\n`;
  }

  if (result.keywords && result.keywords.length > 0) {
    output += `**关键词**: ${result.keywords.join(', ')}\n\n`;
  }

  if (result.tech_stack && result.tech_stack.length > 0) {
    output += `**技术栈**: ${result.tech_stack.join(', ')}\n\n`;
  }

  output += `**分类**: ${result.category || category}\n\n`;

  if (groups && groups.length > 0) {
    output += `**已添加到分组**: ${groups.join(', ')}\n\n`;
  }

  const qdrantId = result.qdrant_id || result.id || result.result_id;
  if (qdrantId && qdrantId !== 'unknown') {
    output += `**ID**: \`${qdrantId}\`\n`;
  } else {
    output += '**ID**: （处理中）\n';
  }

  return output;
}

/**
 * 注册 add_knowledge 工具
 */
export function registerAddKnowledgeTool(server: McpServer): void {
  server.tool(
    'add_knowledge',
    `添加知识 - 将内容存入知识库

AI 自动提取标题、摘要、关键词。支持各类内容：
- 项目经历、技术方案、问题解决记录
- 学习笔记、代码片段、配置说明`,
    addKnowledgeInputSchema,
    async ({ content, title, category, group_names }) => {
      try {
        // 解析分组名称
        const groups = group_names
          ? group_names.split(',').map((g) => g.trim()).filter(Boolean)
          : undefined;

        // Step 1: 提交添加任务
        const result = await apiAddKnowledge(content, title, category ?? 'general', groups);

        const taskId = result.task_id;
        if (!taskId) {
          // 旧版 API 直接返回结果
          return {
            content: [{ type: 'text', text: formatAddResult(result, category ?? 'general', groups) }],
          };
        }

        // Step 2: 轮询任务状态
        const startTime = Date.now();
        const maxWaitMs = config.ADD_KNOWLEDGE_MAX_WAIT * 1000;
        const pollIntervalMs = config.ADD_KNOWLEDGE_POLL_INTERVAL * 1000;

        while (Date.now() - startTime < maxWaitMs) {
          await sleep(pollIntervalMs);

          const statusData = await getAddKnowledgeStatus(taskId);
          const status = statusData.status || '';

          if (status === 'completed') {
            const resultId = statusData.result_id;
            if (resultId) {
              return {
                content: [{
                  type: 'text',
                  text: formatAddResult({ qdrant_id: resultId }, category ?? 'general', groups),
                }],
              };
            }
            return {
              content: [{ type: 'text', text: '## 知识添加成功\n\n内容已成功存入知识库。' }],
            };
          }

          if (status === 'failed') {
            const errorMsg = statusData.message || '未知错误';
            return {
              content: [{ type: 'text', text: `## 添加失败\n\n${errorMsg}` }],
              isError: true,
            };
          }

          // processing 或 pending 继续轮询
        }

        return {
          content: [{
            type: 'text',
            text: '## 处理超时\n\n任务仍在处理中，请稍后使用 search 工具查看是否添加成功。',
          }],
        };
      } catch (error) {
        if (error instanceof ApiError) {
          if (error.statusCode === 400) {
            return {
              content: [{
                type: 'text',
                text: '## 参数错误\n\n内容不能为空或过短（至少需要10个字符）。',
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
          content: [{ type: 'text', text: `## 错误\n\n添加知识失败: ${message}` }],
          isError: true,
        };
      }
    }
  );
}
