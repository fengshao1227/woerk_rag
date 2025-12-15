import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm, Space, Tag, Tooltip, DatePicker, Typography, Card, Spin, Alert } from 'antd';
import { PlusOutlined, DeleteOutlined, CopyOutlined, KeyOutlined, CheckCircleOutlined, CloseCircleOutlined, InfoCircleOutlined, CodeOutlined, BookOutlined } from '@ant-design/icons';
import { myApiKeysAPI } from '../services/api';
import useResponsive from '../hooks/useResponsive';
import dayjs from 'dayjs';

const { Paragraph, Text } = Typography;

// RAG 知识库使用规则
const RAG_USAGE_RULES = `## RAG 知识库使用规则

### 可用工具

| 工具 | 用途 | 示例 |
|------|------|------|
| \`search\` | 语义搜索（优先，不耗Token） | \`search("邮件发送", group_names="my-backend")\` |
| \`query\` | AI综合问答 | \`query("架构是怎样的", top_k=8, group_names="my-backend")\` |
| \`add_knowledge\` | 添加知识 | \`add_knowledge(content="...", category="note", group_names="my-backend")\` |
| \`delete_knowledge\` | 删除条目 | \`delete_knowledge(qdrant_id="xxx")\` |
| \`list_groups\` | 查看所有分组 | \`list_groups()\` |
| \`stats\` | 知识库统计 | \`stats()\` |

### 工作流程

\`\`\`
接到任务 → search查RAG → 无结果再搜代码 → 完成后add_knowledge沉淀
\`\`\`

### 各工具参数

**search**
- \`query_text\`: 搜索词
- \`top_k\`: 返回数量（默认5）
- \`group_names\`: 分组，逗号分隔
- \`min_score\`: 最低相似度（0-1）

**query**
- \`question\`: 问题
- \`top_k\`: 检索数量（复杂问题用8-10）
- \`group_names\`: 分组

**add_knowledge**
- \`content\`: 知识内容（必填）
- \`category\`: project/skill/experience/note
- \`group_names\`: 分组（强烈建议填）
- \`title\`: 可选，不填自动生成

**delete_knowledge**
- \`qdrant_id\`: 条目ID（通过search获取）

### 必须沉淀的场景

| 场景 | 记录内容 |
|------|----------|
| 阅读代码 | 模块职责、关键函数、文件路径 |
| 实现功能 | 实现思路、核心代码、涉及文件 |
| 修复Bug | 问题原因、解决方案、踩坑点 |
| 技术决策 | 选型原因、优缺点 |

### 分组示例

- \`my-backend\` - 后端项目
- \`my-frontend\` - 前端项目
- \`my-docs\` - 文档项目
`;

export default function MyApiKeys() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [rulesModalOpen, setRulesModalOpen] = useState(false);
  const [installModalOpen, setInstallModalOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState(null);
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

  // 打开安装命令弹窗
  const handleShowInstallModal = (record) => {
    setSelectedKey(record);
    setInstallModalOpen(true);
  };

  // 生成安装命令
  const getInstallCommand = (apiKey) => {
    return `git clone https://github.com/fengshao1227/woerk_rag.git ~/rag-mcp && cd ~/rag-mcp/mcp_server_ts && npm install && claude mcp add rag-knowledge -s user -e RAG_API_KEY=${apiKey} -- node ~/rag-mcp/mcp_server_ts/dist/index.js`;
  };

  // 复制安装命令
  const handleCopyInstallCommand = async () => {
    if (!selectedKey) return;
    const command = getInstallCommand(selectedKey.key);

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
          <Tooltip title="安装到 Claude">
            <Button icon={<CodeOutlined />} size="small" onClick={() => handleShowInstallModal(record)} />
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
            <Button size="small" icon={<CodeOutlined />} onClick={() => handleShowInstallModal(record)}>安装</Button>
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
              需要先安装 <Text code>Node.js</Text>（版本 18+）和 <Text code>Git</Text>
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

      {/* 安装命令弹窗 */}
      <Modal
        title={<><CodeOutlined /> 安装到 Claude</>}
        open={installModalOpen}
        onCancel={() => {
          setInstallModalOpen(false);
          setSelectedKey(null);
        }}
        footer={[
          <Button key="close" type="primary" onClick={() => setInstallModalOpen(false)}>关闭</Button>
        ]}
        width={isMobile ? '95vw' : 700}
      >
        <Alert
          type="info"
          showIcon
          message="安装要求"
          description={
            <div style={{ fontSize: isMobile ? 12 : 14 }}>
              <ul style={{ paddingLeft: 20, margin: '8px 0' }}>
                <li>Node.js 18+ 和 Git</li>
                <li>Claude Code CLI（<Text code>npm install -g @anthropic-ai/claude-code</Text>）</li>
              </ul>
            </div>
          }
          style={{ marginBottom: 16 }}
        />

        <div>
          <Text strong>安装命令：</Text>
          <div style={{
            marginTop: 8,
            padding: '8px 12px',
            background: '#f5f5f5',
            borderRadius: 6,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <Text
              code
              style={{
                flex: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontSize: isMobile ? 11 : 13
              }}
            >
              {selectedKey && getInstallCommand(selectedKey.key)}
            </Text>
            <Button
              type="primary"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => handleCopyInstallCommand()}
            >
              复制
            </Button>
          </div>
        </div>

        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 16 }}
          message="使用说明"
          description="复制命令在终端执行，然后重启 Claude 即可。"
        />
      </Modal>
    </div>
  );
}
