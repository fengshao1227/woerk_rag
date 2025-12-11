-- 嵌入模型供应商配置表
-- 执行环境: MySQL 5.7+
-- 数据库: rag_admin

CREATE TABLE IF NOT EXISTS embedding_providers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '供应商名称',

    -- API配置
    api_base_url VARCHAR(500) NOT NULL COMMENT 'API地址',
    api_key VARCHAR(500) NOT NULL COMMENT 'API密钥',
    model_name VARCHAR(100) NOT NULL COMMENT '模型名称',

    -- 配置参数
    embedding_dim INT DEFAULT 1024 COMMENT '向量维度',
    max_batch_size INT DEFAULT 32 COMMENT '批处理大小',
    request_timeout INT DEFAULT 30 COMMENT '请求超时(秒)',

    -- 状态管理
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    is_default BOOLEAN DEFAULT FALSE COMMENT '是否默认',

    -- 监控统计
    monthly_budget DECIMAL(10,2) DEFAULT NULL COMMENT '月度预算',
    current_usage DECIMAL(10,2) DEFAULT 0 COMMENT '当前使用量',

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_is_default (is_default),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='嵌入模型供应商配置';

-- 插入默认配置(黑白供应商)
INSERT INTO embedding_providers
(name, api_base_url, api_key, model_name, embedding_dim, is_active, is_default)
VALUES
('黑白 Qwen Embedding',
 'https://ai.hybgzs.com',
 'sk-wFqofpSHJnHVPbf_biHC0oKwoxPV2qR-cq0ZOzRcQOUjFsypcLev9-qYJWw',
 'Qwen/Qwen3-Embedding-8B',
 4096,
 TRUE,
 TRUE)
ON DUPLICATE KEY UPDATE name=name;
