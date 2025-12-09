# 前端管理模块

**导航**: [← 返回根目录](../CLAUDE.md) / **admin_frontend/**

> React 管理后台前端，基于 Ant Design 构建
>
> **最后更新**: 2025-12-08 23:06:35

## 模块概述

`admin_frontend/` 是一个现代化的 React 单页应用，提供：
- 用户登录和认证
- 仪表板统计
- LLM 供应商/模型管理
- 知识库管理
- 使用统计和日志查看
- RAG 问答聊天界面

## 技术栈

- **框架**: React 19
- **构建工具**: Vite
- **UI 组件库**: Ant Design (antd)
- **样式**: TailwindCSS
- **HTTP 客户端**: Axios
- **路由**: React Router DOM v6

## 目录结构

```
admin_frontend/
├── src/
│   ├── App.jsx               # 主应用组件（路由配置）
│   ├── main.jsx              # 应用入口
│   ├── components/           # 公共组件
│   │   ├── Layout.jsx        # 布局组件（侧边栏、顶栏）
│   │   └── ModelTestModal.jsx # 模型测试弹窗
│   ├── pages/                # 页面组件
│   │   ├── Dashboard.jsx     # 仪表板
│   │   ├── Providers.jsx     # 供应商管理
│   │   ├── Models.jsx        # 模型管理
│   │   ├── Knowledge.jsx     # 知识库管理
│   │   ├── UsageStats.jsx    # 使用统计
│   │   ├── Chat.jsx          # RAG 问答聊天
│   │   └── Login.jsx         # 登录页
│   ├── services/
│   │   └── api.js            # API 调用封装
│   └── assets/               # 静态资源
├── package.json
├── vite.config.js
└── README.md
```

## 核心组件

### 1. App.jsx (路由配置)
```jsx
路由结构：
- /login → 登录页（公开）
- / → Layout 布局（需认证）
  ├── /dashboard → 仪表板
  ├── /providers → 供应商管理
  ├── /models → 模型管理
  ├── /knowledge → 知识库管理
  ├── /usage → 使用统计
  └── /chat → RAG 问答聊天
```

**认证守卫**: 检查 `localStorage` 中的 `token`，未登录则重定向到 `/login`。

### 2. Layout.jsx (布局组件)
```jsx
组件结构：
- 侧边栏（Sider）
  ├── Logo
  ├── 菜单（Menu）
  │   ├── 仪表板
  │   ├── 供应商管理
  │   ├── 模型管理
  │   ├── 知识库管理
  │   ├── 使用统计
  │   └── RAG 问答
  └── 折叠按钮
- 主内容区（Content）
  ├── 顶栏（Header）
  │   ├── 当前用户
  │   └── 登出按钮
  └── 页面内容（Outlet）
```

### 3. services/api.js (API 封装)
```javascript
核心功能：
- 创建 Axios 实例（baseURL, timeout）
- 请求拦截器（自动添加 Authorization 头）
- 响应拦截器（统一错误处理，401 自动跳转登录）
- API 方法：
  - auth.login()
  - auth.getCurrentUser()
  - stats.getStats()
  - providers.list() / create() / update() / delete()
  - models.list() / create() / update() / delete() / test()
  - knowledge.list() / get() / update() / delete()
  - usage.getLogs() / getStats()
```

## 页面功能

### 1. Dashboard (仪表板)
- 显示系统统计数据（供应商数、模型数、知识条目数、总调用次数）
- 卡片式布局，图标 + 数字

### 2. Providers (供应商管理)
- 列表展示所有供应商（表格）
- 创建/编辑供应商（模态框）
- 删除供应商（确认弹窗）
- 设为默认供应商
- API Key 脱敏显示

### 3. Models (模型管理)
- 列表展示所有模型（表格）
- 创建/编辑模型（模态框）
- 删除模型（确认弹窗）
- 设为默认模型
- 测试模型（ModelTestModal 组件）

### 4. Knowledge (知识库管理)
- 分页列表展示知识条目
- 查看详情（模态框，显示完整内容）
- 编辑元数据（标题、分类、摘要、关键词）
- 删除条目

### 5. UsageStats (使用统计)
- 使用日志列表（分页表格）
- 统计概览（总调用次数、总 Tokens、平均延迟）
- 按时间范围筛选

### 6. Chat (RAG 问答聊天)
- 聊天界面（消息气泡）
- 输入框 + 发送按钮
- 调用 `/query` 接口
- 显示参考来源
- 清空历史记录

## 构建与部署

### 开发模式
```bash
cd admin_frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### 生产构建
```bash
npm run build
# 输出到 dist/ 目录
```

### 部署到后端
```bash
# 构建后复制到后端静态文件目录
./scripts/deploy-admin.sh

# 或手动复制
cp -r admin_frontend/dist/* /path/to/backend/static/admin/
```

**访问**: `http://localhost:8000/` （FastAPI 自动服务 `dist/` 目录）

## 环境变量

### 开发环境 (.env.development)
```env
VITE_API_BASE_URL=http://localhost:8000
```

### 生产环境 (.env.production)
```env
VITE_API_BASE_URL=https://rag.litxczv.shop
```

## 依赖关系

### 上游依赖
- 后端 API (`api/server.py` + `admin/routes.py`)
- Ant Design 组件库
- Axios HTTP 客户端

### 核心依赖包
```json
{
  "react": "^19.0.0",
  "react-dom": "^19.0.0",
  "react-router-dom": "^6.x",
  "antd": "^5.x",
  "axios": "^1.x",
  "tailwindcss": "^3.x"
}
```

## 常见问题

### 1. 开发时跨域问题？
在 `vite.config.js` 中配置代理：
```javascript
export default defineConfig({
  server: {
    proxy: {
      '/admin/api': 'http://localhost:8000'
    }
  }
})
```

### 2. 生产构建后 404？
确保后端正确配置静态文件服务：
```python
app.mount("/", StaticFiles(directory="admin_frontend/dist", html=True), name="admin")
```

### 3. Token 过期后无法自动跳转？
检查 `api.js` 中的响应拦截器是否正确处理 401 状态码。

## 后续改进

- [ ] 添加国际化支持（i18n）
- [ ] 实现暗黑模式
- [ ] 优化移动端适配
- [ ] 添加更多图表（使用日志趋势图）
- [ ] 实现 WebSocket 实时通知
- [ ] 知识库条目支持在线编辑和预览
