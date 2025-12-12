import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm, Space, Tag, Tooltip, DatePicker, Typography, Card, Spin, Alert } from 'antd';
import { PlusOutlined, DeleteOutlined, CopyOutlined, KeyOutlined, CheckCircleOutlined, CloseCircleOutlined, InfoCircleOutlined, DownloadOutlined } from '@ant-design/icons';
import { myApiKeysAPI } from '../services/api';
import useResponsive from '../hooks/useResponsive';
import dayjs from 'dayjs';

const { Paragraph, Text } = Typography;

export default function MyApiKeys() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
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

  const handleDownload = (record) => {
    // 获取 token 用于认证
    const token = localStorage.getItem('token');
    if (!token) {
      message.error('请先登录');
      return;
    }
    // 使用 fetch 下载文件（需要带认证头）
    const url = myApiKeysAPI.downloadUrl(record.id);
    fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(response => {
        if (!response.ok) throw new Error('下载失败');
        return response.blob();
      })
      .then(blob => {
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        const safeName = record.name.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '_').slice(0, 20);
        link.download = `rag_mcp_server_${safeName}.zip`;
        link.click();
        URL.revokeObjectURL(link.href);
        message.success('MCP 服务器下载成功');
      })
      .catch(err => {
        message.error(err.message || '下载失败');
      });
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
          <Tooltip title="下载 MCP 服务器">
            <Button icon={<DownloadOutlined />} size="small" onClick={() => handleDownload(record)} />
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
            <Button size="small" icon={<DownloadOutlined />} onClick={() => handleDownload(record)}>下载</Button>
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
              配置方法：将卡密设置为 MCP Server 环境变量 <Text code>RAG_API_KEY</Text>
            </p>
            <details style={{ marginTop: 8 }}>
              <summary style={{ cursor: 'pointer', color: '#1890ff' }}>查看 Claude Desktop 配置示例</summary>
              <pre style={{
                background: '#f5f5f5',
                padding: 12,
                borderRadius: 4,
                marginTop: 8,
                fontSize: 12,
                overflow: 'auto'
              }}>
{`{
  "mcpServers": {
    "rag-knowledge": {
      "command": "python",
      "args": ["/path/to/rag/mcp_server/server.py"],
      "env": {
        "RAG_API_KEY": "你的卡密"
      }
    }
  }
}`}
              </pre>
            </details>
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
    </div>
  );
}
