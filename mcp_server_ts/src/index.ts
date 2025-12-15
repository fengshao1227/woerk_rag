/**
 * RAG Knowledge Base MCP Server
 *
 * TypeScript 实现，通过 stdio 与 Claude Desktop 通信
 * 调用远程 RAG API 服务
 *
 * 使用方式:
 *   RAG_API_KEY=rag_sk_xxx node dist/index.js
 *
 * Claude Desktop 配置:
 *   {
 *     "mcpServers": {
 *       "rag-knowledge": {
 *         "command": "node",
 *         "args": ["/path/to/dist/index.js"],
 *         "env": { "RAG_API_KEY": "rag_sk_你的卡密" }
 *       }
 *     }
 *   }
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { config, validateConfig } from './config.js';
import {
  registerQueryTool,
  registerSearchTool,
  registerAddKnowledgeTool,
  registerDeleteKnowledgeTool,
  registerListGroupsTool,
  registerStatsTool,
} from './tools/index.js';

/**
 * 主函数
 */
async function main(): Promise<void> {
  // 验证配置（只检查是否设置了 API Key，不验证有效性）
  const configValidation = validateConfig();
  if (!configValidation.valid) {
    console.error(`配置错误: ${configValidation.error}`);
    process.exit(1);
  }

  // 创建 MCP Server
  const server = new McpServer({
    name: 'rag-knowledge',
    version: '1.0.0',
  });

  // 注册所有工具
  registerQueryTool(server);
  registerSearchTool(server);
  registerAddKnowledgeTool(server);
  registerDeleteKnowledgeTool(server);
  registerListGroupsTool(server);
  registerStatsTool(server);

  // 创建 stdio 传输
  const transport = new StdioServerTransport();

  // 连接并启动服务
  await server.connect(transport);

  // 日志输出到 stderr（stdout 用于 MCP 协议通信）
  console.error(`RAG MCP Server 已启动`);
  console.error(`  远程 API: ${config.RAG_API_BASE}`);
  console.error(`  API Key: ${config.RAG_API_KEY.slice(0, 10)}...`);
}

// 启动
main().catch((error) => {
  console.error('MCP Server 启动失败:', error);
  process.exit(1);
});
