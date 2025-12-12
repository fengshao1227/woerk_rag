-- MCP API Keys 用户绑定迁移
-- 为 mcp_api_keys 表添加 user_id 字段，实现卡密与用户绑定

-- 1. 添加 user_id 字段
ALTER TABLE mcp_api_keys
ADD COLUMN user_id INT NULL COMMENT '绑定用户ID，NULL表示管理员级卡密';

-- 2. 添加索引
ALTER TABLE mcp_api_keys
ADD INDEX idx_mcp_api_keys_user_id (user_id);

-- 3. 添加外键约束（可选，删除用户时卡密的 user_id 设为 NULL）
ALTER TABLE mcp_api_keys
ADD CONSTRAINT fk_mcp_api_keys_user
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;

-- 验证
DESCRIBE mcp_api_keys;
