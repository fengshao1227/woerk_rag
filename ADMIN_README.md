# RAG 后台管理系统

## 功能概述

- ✅ 用户认证（JWT）
- ✅ LLM供应商管理（支持Claude/OpenAI官方及第三方API）
- ✅ LLM模型配置管理
- ✅ 知识库完整管理（CRUD + 批量导入导出）

## 技术栈

### 后端
- FastAPI + SQLAlchemy + PyMySQL
- JWT认证（python-jose + bcrypt）
- MySQL数据库

### 前端
- React 18 + Vite
- Ant Design
- Axios + React Router

## 快速启动

### 1. 启动后端服务

```bash
# 激活虚拟环境
source venv/bin/activate

# 启动FastAPI服务
python api/server.py
```

后端服务将运行在 `http://localhost:8000`

### 2. 启动前端服务

```bash
# 进入前端目录
cd admin_frontend

# 启动开发服务器
npm run dev
```

前端服务将运行在 `http://localhost:5173`

### 3. 登录后台

- 访问: `http://localhost:5173/login`
- 默认账号: `admin`
- 默认密码: `admin123`

## API文档

后端API文档: `http://localhost:8000/docs`

### 主要API端点

#### 认证
- `POST /admin/api/auth/login` - 登录
- `GET /admin/api/auth/me` - 获取当前用户

#### 统计
- `GET /admin/api/stats` - 获取统计数据

#### 供应商管理
- `GET /admin/api/providers` - 列表
- `POST /admin/api/providers` - 创建
- `GET /admin/api/providers/{id}` - 详情
- `PUT /admin/api/providers/{id}` - 更新
- `DELETE /admin/api/providers/{id}` - 删除

#### 模型管理
- `GET /admin/api/models` - 列表
- `POST /admin/api/models` - 创建
- `GET /admin/api/models/{id}` - 详情
- `PUT /admin/api/models/{id}` - 更新
- `DELETE /admin/api/models/{id}` - 删除
- `POST /admin/api/models/{id}/set-default` - 设为默认

#### 知识库管理
- `GET /admin/api/knowledge` - 列表（分页+搜索）
- `GET /admin/api/knowledge/{id}` - 详情
- `PUT /admin/api/knowledge/{id}` - 更新
- `DELETE /admin/api/knowledge/{id}` - 删除
- `GET /admin/api/knowledge/export/all` - 导出

## 数据库配置

MySQL连接配置在 `.env` 文件中：

```env
MYSQL_HOST=103.96.72.4
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=Your_Very_Strong_Password_123!
MYSQL_DATABASE=rag_admin
```

## 项目结构

```
rag/
├── admin/                    # 后台管理后端模块
│   ├── __init__.py
│   ├── database.py          # 数据库连接
│   ├── models.py            # SQLAlchemy模型
│   ├── schemas.py           # Pydantic模式
│   ├── auth.py              # JWT认证
│   └── routes.py            # API路由
├── admin_frontend/          # React前端
│   ├── src/
│   │   ├── components/      # 组件
│   │   │   └── Layout.jsx
│   │   ├── pages/           # 页面
│   │   │   ├── Login.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Providers.jsx
│   │   │   ├── Models.jsx
│   │   │   └── Knowledge.jsx
│   │   ├── services/        # API服务
│   │   │   └── api.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
├── api/
│   └── server.py            # FastAPI主服务（已集成后台路由）
└── .env                     # 环境配置
```

## 注意事项

1. **首次使用**：数据库表已自动创建，默认管理员账户已创建
2. **API Key安全**：供应商的API Key在列表中会自动脱敏显示
3. **CORS配置**：后端已配置CORS，允许前端跨域访问
4. **JWT过期时间**：默认24小时，可在.env中配置

## 下一步优化建议

1. 添加用户管理功能（创建、编辑、删除用户）
2. 实现知识库批量导入功能
3. 添加LLM使用量统计和费用追踪
4. 实现模型测试功能（在后台直接测试模型响应）
5. 添加操作日志记录
6. 实现更细粒度的权限控制

## 故障排查

### 后端启动失败
- 检查MySQL连接配置是否正确
- 确认所有Python依赖已安装：`pip install -r requirements.txt`
- 查看日志文件：`logs/rag.log`

### 前端无法连接后端
- 确认后端服务已启动
- 检查API_BASE配置：`admin_frontend/src/services/api.js`
- 查看浏览器控制台错误信息

### 登录失败
- 确认数据库中users表有数据
- 检查密码是否正确（默认：admin123）
- 查看后端日志确认错误原因
