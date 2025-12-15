import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm, Space, Tag, Tooltip, Switch, DatePicker, Typography, Card, Spin, Alert } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CopyOutlined, KeyOutlined, CheckCircleOutlined, CloseCircleOutlined, CodeOutlined } from '@ant-design/icons';
import { apiKeysAPI } from '../services/api';
import useResponsive from '../hooks/useResponsive';
import dayjs from 'dayjs';

const { Paragraph, Text } = Typography;

export default function ApiKeys() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [installModalOpen, setInstallModalOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState(null);
  const [form] = Form.useForm();
  const { isMobile } = useResponsive();

  const loadData = async () => {
    setLoading(true);
    try {
      const { data: res } = await apiKeysAPI.list();
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

      if (editingId) {
        payload.is_active = values.is_active;
        await apiKeysAPI.update(editingId, payload);
        message.success('更新成功');
      } else {
        await apiKeysAPI.create(payload);
        message.success('创建成功');
      }
      setModalOpen(false);
      form.resetFields();
      setEditingId(null);
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const handleEdit = (record) => {
    setEditingId(record.id);
    form.setFieldsValue({
      name: record.name,
      is_active: record.is_active,
      expires_at: record.expires_at ? dayjs(record.expires_at) : null
    });
    setModalOpen(true);
  };

  const handleDelete = async (id) => {
    try {
      await apiKeysAPI.delete(id);
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
      message.success('安装命令已复制');
    } catch (err) {
      const textArea = document.createElement('textarea');
      textArea.value = command;
      document.body.appendChild(textArea);
      textArea.select();
      try {
        document.execCommand('copy');
        message.success('安装命令已复制');
      } catch (e) {
        message.error('复制失败，请手动复制');
      }
      document.body.removeChild(textArea);
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: '绑定用户',
      dataIndex: 'username',
      key: 'username',
      width: 120,
      render: (username, record) => username
        ? <Tag color="blue">{username}</Tag>
        : <Tag color="gold">管理员级</Tag>
    },
    {
      title: '卡密',
      dataIndex: 'key',
      key: 'key',
      width: 280,
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
      width: 140,
      render: (val) => val ? dayjs(val).format('MM-DD HH:mm') : '-'
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 140,
      render: (val) => dayjs(val).format('YYYY-MM-DD HH:mm')
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_, record) => (
        <Space size={4}>
          <Tooltip title="安装到 Claude">
            <Button icon={<CodeOutlined />} size="small" onClick={() => handleShowInstallModal(record)} />
          </Tooltip>
          <Tooltip title="编辑">
            <Button icon={<EditOutlined />} size="small" onClick={() => handleEdit(record)} />
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
              {record.username
                ? <Tag color="blue" style={{ marginLeft: 4 }}>{record.username}</Tag>
                : <Tag color="gold" style={{ marginLeft: 4 }}>管理员级</Tag>
              }
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
            <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
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
          <KeyOutlined /> MCP 卡密管理
        </h2>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size={isMobile ? 'small' : 'middle'}
          onClick={() => {
            setEditingId(null);
            form.resetFields();
            setModalOpen(true);
          }}
        >
          {isMobile ? '创建' : '创建卡密'}
        </Button>
      </div>

      <div style={{
        background: '#e6f7ff',
        border: '1px solid #91d5ff',
        borderRadius: 8,
        padding: isMobile ? 12 : 16,
        marginBottom: 16
      }}>
        <h4 style={{ fontWeight: 500, color: '#1890ff', marginBottom: 8, fontSize: isMobile ? 13 : 14 }}>使用说明</h4>
        <p style={{ fontSize: isMobile ? 12 : 14, color: '#096dd9', margin: 0 }}>
          MCP 卡密用于 Claude Desktop 连接本知识库。将卡密配置到 MCP Server 环境变量 <code style={{ background: '#bae7ff', padding: '0 4px', borderRadius: 2 }}>RAG_API_KEY</code> 即可使用。
        </p>
      </div>

      {isMobile ? (
        loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
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
          scroll={{ x: 1200 }}
        />
      )}

      <Modal
        title={editingId ? '编辑卡密' : '创建卡密'}
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          setEditingId(null);
          form.resetFields();
        }}
        footer={null}
        width={isMobile ? '95vw' : 500}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{ is_active: true }}
        >
          <Form.Item
            name="name"
            label="卡密名称"
            rules={[{ required: true, message: '请输入卡密名称' }]}
          >
            <Input placeholder="如：Claude Desktop 主用卡密" />
          </Form.Item>

          {editingId && (
            <Form.Item name="is_active" label="状态" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
          )}

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
              <Button type="primary" htmlType="submit">
                {editingId ? '保存' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
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
