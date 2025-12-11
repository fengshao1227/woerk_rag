# Agent 智能问答使用指南

> ReAct 模式的智能 Agent,支持多步推理和工具调用
>
> **最后更新**: 2025-12-11

## 🎯 功能概述

Agent 模块基于 **ReAct (Reasoning + Acting)** 模式,能够:
- 🧠 **多步推理** - 将复杂问题分解为多个步骤
- 🔧 **工具调用** - 动态调用外部工具获取信息
- 🔄 **迭代优化** - 根据观察结果调整策略
- 📝 **思考过程可视化** - 返回完整的推理链路

## 🚀 快速开始

### API 端点

```http
POST /agent
Content-Type: application/json
Authorization: Bearer <your_token>
```

### 请求示例

```json
{
  "question": "帮我搜索RAG相关的知识并总结",
  "context": {},
  "max_iterations": 5
}
```

### 响应示例

```json
{
  "success": true,
  "answer": "根据搜索结果,RAG(检索增强生成)主要包含...",
  "thought_process": [
    {
      "thought": "我需要先搜索知识库中关于RAG的内容",
      "action": "search",
      "action_input": "RAG 检索增强生成",
      "observation": "找到5条相关知识..."
    },
    {
      "thought": "现在我可以总结这些内容",
      "action": null
    }
  ],
  "iterations": 2
}
```

## 🔧 可用工具

### 1. search - 知识库搜索
**功能**: 在向量数据库中检索相关知识

```python
{
  "action": "search",
  "action_input": "搜索关键词"
}
```

### 2. calculator - 数学计算
**功能**: 执行数学表达式计算

```python
{
  "action": "calculator",
  "action_input": "2 + 2 * 3"
}
```

### 3. code_executor - Python 代码执行
**功能**: 执行 Python 代码片段(沙盒环境)

```python
{
  "action": "code_executor",
  "action_input": "print([x**2 for x in range(5)])"
}
```

### 4. datetime - 日期时间
**功能**: 获取当前日期时间

```python
{
  "action": "datetime",
  "action_input": ""
}
```

### 5. json - JSON 处理
**功能**: 解析和格式化 JSON 数据

```python
{
  "action": "json",
  "action_input": "{\"key\": \"value\"}"
}
```

## 📊 使用场景

### 场景 1: 复杂问题推理

**问题**: "RAG系统的平均响应时间是多少毫秒?"

**Agent 思考过程**:
1. 搜索 RAG 性能相关的知识
2. 提取响应时间数据
3. 使用 calculator 计算平均值
4. 返回结果

### 场景 2: 数据分析

**问题**: "分析最近7天的LLM使用量趋势"

**Agent 思考过程**:
1. 搜索使用统计数据
2. 使用 code_executor 进行数据处理
3. 生成趋势分析报告

### 场景 3: 实时信息查询

**问题**: "现在是什么时间?距离项目截止日期还有多久?"

**Agent 思考过程**:
1. 使用 datetime 工具获取当前时间
2. 搜索项目截止日期
3. 计算时间差

## 🛠️ 配置参数

### max_iterations
- **说明**: 最大迭代次数
- **默认值**: 5
- **范围**: 1-10
- **建议**: 简单问题用2-3,复杂问题用5-8

### context
- **说明**: 额外上下文信息
- **类型**: Dict
- **示例**: `{"user_id": 123, "session_id": "abc"}`

## 📝 最佳实践

### 1. 问题描述清晰
❌ **不好**: "帮我查一下"
✅ **好**: "帮我搜索RAG系统的性能优化方法并总结"

### 2. 合理设置迭代次数
- 简单查询: `max_iterations=2`
- 中等复杂度: `max_iterations=5`
- 复杂推理: `max_iterations=8`

### 3. 利用 thought_process
返回的推理过程可用于:
- 调试 Agent 行为
- 理解 AI 决策逻辑
- 审计工具调用链

## ⚠️ 注意事项

1. **Token 消耗**: Agent 会进行多轮 LLM 调用,Token 消耗较高
2. **响应时间**: 复杂问题可能需要10-30秒
3. **工具限制**: code_executor 运行在沙盒环境,部分功能受限
4. **认证要求**: 需要登录才能使用

## 🔍 错误处理

### 常见错误

**503 Service Unavailable**
```json
{"detail": "Agent 服务未初始化"}
```
**原因**: Agent 模块导入失败
**解决**: 检查 agent/ 模块是否完整

**500 Internal Server Error**
```json
{"detail": "执行失败: ..."}
```
**原因**: 工具调用异常或 LLM 调用失败
**解决**: 查看错误详情,检查工具参数

## 🔗 相关文档

- [API 服务模块](./api/CLAUDE.md)
- [QA 问答模块](./qa/CLAUDE.md)
- [Agent 核心实现](./agent/CLAUDE.md)

---

**更新时间**: 2025-12-11
**维护者**: RAG 项目团队
