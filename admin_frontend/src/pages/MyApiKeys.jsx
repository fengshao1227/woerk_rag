import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm, Space, Tag, Tooltip, DatePicker, Typography, Card, Spin, Alert } from 'antd';
import { PlusOutlined, DeleteOutlined, CopyOutlined, KeyOutlined, CheckCircleOutlined, CloseCircleOutlined, InfoCircleOutlined, CodeOutlined, BookOutlined } from '@ant-design/icons';
import { myApiKeysAPI } from '../services/api';
import useResponsive from '../hooks/useResponsive';
import dayjs from 'dayjs';

const { Paragraph, Text } = Typography;

// RAG 知识库使用规则
const RAG_USAGE_RULES = `## RAG知识库使用规则（rag-knowledge MCP）

### 核心原则

**知识库是项目记忆的核心，必须持续沉淀细节知识！**

---

### 一、强制工作流程

1. **先查RAG** → 使用 \`search(query, group_names="项目名")\` 查询
2. **RAG 无结果** → 才使用其他工具搜索代码
3. **任务完成** → **必须** 用 \`add_knowledge\` 保存细节到知识库

---

### 二、知识沉淀（最重要！）

#### 强制添加知识的场景

| 场景 | 必须记录的内容 |
|------|---------------|
| 阅读代码 | 模块职责、关键类/函数、调用关系、设计模式 |
| 实现功能 | 实现步骤、核心代码片段、涉及的文件 |
| 修复 Bug | 问题原因、解决方案、踩坑点 |
| 技术决策 | 选型原因、优缺点对比、最佳实践 |
| 发现规律 | 代码规范、命名约定、架构模式 |

#### add_knowledge 参数（强制规范）

\`\`\`
add_knowledge(
    content="详细内容",
    category="project|skill|experience|note",
    group_names="项目名"  # ⚠️ 强制指定！
)
\`\`\`

**参数说明**:
- \`content\` - 知识内容（500-1500字为宜）
- \`category\` - 分类：project(项目)/skill(技能)/experience(经验)/note(笔记)
- \`group_names\` - **必填**！项目名称，多个用逗号分隔

#### 细节要求

- **每次只记录一个主题**，避免混杂
- **包含具体代码**，不要只写概念
- **标注文件路径**，方便定位
- **记录踩坑点**，避免重复犯错
- **说明"为什么"**，不只记录"是什么"

---

### 三、查询规范

| 工具 | 用途 | 示例 |
|------|------|------|
| \`search\` | 快速检索（优先） | \`search("邮件发送", group_names="my-project")\` |
| \`query\` | 需要AI 总结时 | \`query("整体架构是怎样的", group_names="my-app")\` |

---

### 四、分组管理

- \`my-project\` - 示例后端项目
- \`my-app\` - 示例前端项目
- 项目相关知识 → 必须指定 \`group_names\`
- 通用技术知识 → 可不指定，存入全局库
`;

export default function MyApiKeys() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [rulesModalOpen, setRulesModalOpen] = useState(false);
  const [form] = Form.useForm();
  const { isMobile } = useResponsive();

  const loadData = async () => {
    setLoading(true);
    try {
      const { data: res } = await myApiKeysAPI.list();
      setData(res.items || []);
    } catch (error) {
      message.error('加载卡密列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleSubmit = async (values) => {
    try {
      const payload = {
        name: values.name,
        expires_at: values.expires_at ? values.expires_at.toISOString() : null
      };

      await myApiKeysAPI.create(payload);
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '创建失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await myApiKeysAPI.delete(id);
      message.success('删除成功');
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const handleCopy = (key) => {
    navigator.clipboard.writeText(key);
    message.success('已复制到剪贴板');
  };

  // 生成 claude mcp add 命令并复制
  const handleCopyInstallCommand = async (record) => {
    const command = `claude mcp add rag-knowledge -s user --transport stdio -e RAG_API_KEY=${record.key} -- uvx --from git+https://github.com/fengshao1227/woerk_rag.git rag-mcp`;
    try {
      await navigator.clipboard.writeText(command);
      message.success('安装命令已复制，请在终端粘贴执行');
    } catch (err) {
      // fallback: 创建临时文本框复制
      const textArea = document.createElement('textarea');
      textArea.value = command;
      document.body.appendChild(textArea);
      textArea.select();
      try {
        document.execCommand('copy');
        message.success('安装命令已复制，请在终端粘贴执行');
      } catch (e) {
        message.error('复制失败，请手动复制');
        console.error('Copy failed:', e);
      }
      document.body.removeChild(textArea);
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
    },
    {
      title: '卡密',
      dataIndex: 'key',
      key: 'key',
      width: 300,
      render: (key) => (
        <Space>
          <Paragraph
            copyable={{ text: key, tooltips: ['复制', '已复制'] }}
            style={{ marginBottom: 0, fontFamily: 'monospace' }}
          >
            {key.slice(0, 12)}...{key.slice(-8)}
          </Paragraph>
        </Space>
      )
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (active) => active
        ? <Tag icon={<CheckCircleOutlined />} color="success">启用</Tag>
        : <Tag icon={<CloseCircleOutlined />} color="default">禁用</Tag>
    },
    {
      title: '过期时间',
      dataIndex: 'expires_at',
      key: 'expires_at',
      width: 180,
      render: (val) => {
        if (!val) return <Tag color="blue">永不过期</Tag>;
        const exp = dayjs(val);
        const isExpired = exp.isBefore(dayjs());
        return (
          <Tooltip title={exp.format('YYYY-MM-DD HH:mm:ss')}>
            <Tag color={isExpired ? 'red' : 'green'}>
              {isExpired ? '已过期' : exp.format('YYYY-MM-DD')}
            </Tag>
          </Tooltip>
        );
      }
    },
    {
      title: '使用次数',
      dataIndex: 'usage_count',
      key: 'usage_count',
      width: 100,
      render: (count) => <Tag color="purple">{count} 次</Tag>
    },
    {
      title: '最后使用',
      dataIndex: 'last_used_at',
      key: 'last_used_at',
      width: 160,
      render: (val) => val ? dayjs(val).format('MM-DD HH:mm') : '-'
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val) => dayjs(val).format('YYYY-MM-DD HH:mm')
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_, record) => (
        <Space size={4}>
          <Tooltip title="复制安装命令">
            <Button icon={<CodeOutlined />} size="small" onClick={() => handleCopyInstallCommand(record)} />
          </Tooltip>
          <Popconfirm
            title="确定要删除这个卡密吗？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Tooltip title="删除">
              <Button icon={<DeleteOutlined />} size="small" danger />
            </Tooltip>
          </Popconfirm>
        </Space>
      )
    }
  ];

  // 移动端卡片渲染
  const renderMobileCard = (record) => {
    const exp = record.expires_at ? dayjs(record.expires_at) : null;
    const isExpired = exp && exp.isBefore(dayjs());

    return (
      <Card key={record.id} size="small" style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <KeyOutlined style={{ color: '#1890ff' }} />
              <span style={{ fontWeight: 500 }}>{record.name}</span>
            </div>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 8, fontFamily: 'monospace' }}>
              {record.key.slice(0, 8)}...{record.key.slice(-6)}
              <Button
                type="link"
                size="small"
                icon={<CopyOutlined />}
                onClick={() => handleCopy(record.key)}
                style={{ padding: '0 4px' }}
              />
            </div>
            <Space size={4} wrap>
              {record.is_active
                ? <Tag icon={<CheckCircleOutlined />} color="success">启用</Tag>
                : <Tag icon={<CloseCircleOutlined />} color="default">禁用</Tag>
              }
              {!exp ? (
                <Tag color="blue">永不过期</Tag>
              ) : (
                <Tag color={isExpired ? 'red' : 'green'}>
                  {isExpired ? '已过期' : exp.format('MM-DD')}
                </Tag>
              )}
              <Tag color="purple">{record.usage_count} 次</Tag>
            </Space>
          </div>
          <Space direction="vertical" size={4}>
            <Button size="small" icon={<CodeOutlined />} onClick={() => handleCopyInstallCommand(record)}>安装</Button>
            <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        </div>
      </Card>
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: isMobile ? 16 : 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <KeyOutlined /> 我的卡密
        </h2>
        <Space size={8}>
          <Button
            icon={<BookOutlined />}
            size={isMobile ? 'small' : 'middle'}
            onClick={() => setRulesModalOpen(true)}
          >
            {isMobile ? '规则' : '推荐规则'}
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            size={isMobile ? 'small' : 'middle'}
            onClick={() => {
              form.resetFields();
              setModalOpen(true);
            }}
          >
            {isMobile ? '创建' : '创建卡密'}
          </Button>
        </Space>
      </div>

      <Alert
        type="info"
        showIcon
        icon={<InfoCircleOutlined />}
        style={{ marginBottom: 16 }}
        message="MCP 卡密使用说明"
        description={
          <div style={{ fontSize: isMobile ? 12 : 14 }}>
            <p style={{ margin: '8px 0' }}>
              使用此卡密连接 Claude Desktop，<Text strong>只能访问你自己的知识、公开知识和被共享的知识</Text>。
            </p>
            <p style={{ margin: '8px 0' }}>
              <Text strong>一键安装：</Text>点击卡密操作栏的 <CodeOutlined /> 按钮复制安装命令，在终端粘贴执行即可。
            </p>
            <p style={{ margin: '4px 0', color: '#666' }}>
              需要先安装 <Text code>uv</Text>：<Text code copyable={{ text: 'curl -LsSf https://astral.sh/uv/install.sh | sh' }}>curl -LsSf https://astral.sh/uv/install.sh | sh</Text>
            </p>
          </div>
        }
      />

      {isMobile ? (
        loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : data.length === 0 ? (
          <Card style={{ textAlign: 'center', padding: 40 }}>
            <KeyOutlined style={{ fontSize: 48, color: '#ccc', marginBottom: 16 }} />
            <p style={{ color: '#999' }}>暂无卡密，点击上方按钮创建</p>
          </Card>
        ) : (
          data.map(renderMobileCard)
        )
      ) : (
        <Table
          columns={columns}
          dataSource={data}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1100 }}
          locale={{ emptyText: '暂无卡密，点击上方按钮创建' }}
        />
      )}

      <Modal
        title="创建卡密"
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        width={isMobile ? '95vw' : 500}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="name"
            label="卡密名称"
            rules={[{ required: true, message: '请输入卡密名称' }]}
          >
            <Input placeholder="如：我的 Claude Desktop 卡密" />
          </Form.Item>

          <Form.Item name="expires_at" label="过期时间（可选）">
            <DatePicker
              showTime
              placeholder="不设置则永不过期"
              style={{ width: '100%' }}
            />
          </Form.Item>

          <Form.Item className="mb-0 text-right">
            <Space>
              <Button onClick={() => setModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit">创建</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 推荐规则弹窗 */}
      <Modal
        title={<><BookOutlined /> RAG 知识库使用规则</>}
        open={rulesModalOpen}
        onCancel={() => setRulesModalOpen(false)}
        footer={[
          <Button key="copy" icon={<CopyOutlined />} onClick={async () => {
            try {
              await navigator.clipboard.writeText(RAG_USAGE_RULES);
              message.success('规则已复制到剪贴板');
            } catch (err) {
              const textArea = document.createElement('textarea');
              textArea.value = RAG_USAGE_RULES;
              document.body.appendChild(textArea);
              textArea.select();
              try {
                document.execCommand('copy');
                message.success('规则已复制到剪贴板');
              } catch (e) {
                message.error('复制失败，请手动复制');
              }
              document.body.removeChild(textArea);
            }
          }}>
            复制规则
          </Button>,
          <Button key="close" type="primary" onClick={() => setRulesModalOpen(false)}>
            关闭
          </Button>
        ]}
        width={isMobile ? '95vw' : 800}
      >
        <div style={{
          maxHeight: '60vh',
          overflow: 'auto',
          padding: 16,
          background: '#fafafa',
          borderRadius: 8,
          fontSize: isMobile ? 12 : 14
        }}>
          <pre style={{
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
            margin: 0,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
          }}>
            {RAG_USAGE_RULES}
          </pre>
        </div>
        <Alert
          type="success"
          showIcon
          style={{ marginTop: 16 }}
          message="使用建议"
          description="将此规则复制到你的项目 CLAUDE.md 或 .cursorrules 文件中，让 AI 助手遵循知识库使用规范。"
        />
      </Modal>
    </div>
  );
}
