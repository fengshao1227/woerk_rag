import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, message, Popconfirm, Space, Tag, Tooltip, Card, Spin } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CheckCircleOutlined, ThunderboltOutlined, DatabaseOutlined } from '@ant-design/icons';
import { embeddingProviderAPI } from '../services/api';
import useResponsive from '../hooks/useResponsive';

export default function EmbeddingProviders() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testingId, setTestingId] = useState(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [form] = Form.useForm();
  const [testForm] = Form.useForm();
  const { isMobile } = useResponsive();

  const loadData = async () => {
    setLoading(true);
    try {
      const { data } = await embeddingProviderAPI.list();
      setData(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleSubmit = async (values) => {
    try {
      if (editingId) {
        await embeddingProviderAPI.update(editingId, values);
        message.success('更新成功');
      } else {
        await embeddingProviderAPI.create(values);
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
      api_base_url: record.api_base_url,
      api_key: record.api_key_masked.includes('****') ? '' : record.api_key_masked,
      model_name: record.model_name,
      embedding_dim: record.embedding_dim,
      max_batch_size: record.max_batch_size,
      request_timeout: record.request_timeout,
      monthly_budget: record.monthly_budget
    });
    setModalOpen(true);
  };

  const handleDelete = async (id) => {
    try {
      await embeddingProviderAPI.delete(id);
      message.success('删除成功');
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const handleSetDefault = async (id) => {
    try {
      await embeddingProviderAPI.setDefault(id);
      message.success('已设为默认嵌入供应商');
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const handleTest = async (values) => {
    setTestLoading(true);
    setTestResult(null);
    try {
      const { data } = await embeddingProviderAPI.test(testingId, values.text);
      setTestResult(data);
      message.success('测试成功');
    } catch (error) {
      message.error(error.response?.data?.detail || '测试失败');
      setTestResult({ success: false, message: error.response?.data?.detail || '测试失败' });
    } finally {
      setTestLoading(false);
    }
  };

  const openTestModal = (record) => {
    setTestingId(record.id);
    setTestResult(null);
    testForm.setFieldsValue({ text: '测试文本内容' });
    setTestModalOpen(true);
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '名称',
      dataIndex: 'name',
      render: (text, record) => (
        <Space>
          {text}
          {record.is_default && <Tag color="blue">默认</Tag>}
        </Space>
      )
    },
    { title: 'API地址', dataIndex: 'api_base_url', ellipsis: true },
    { title: 'API Key', dataIndex: 'api_key_masked', width: 150 },
    { title: '模型', dataIndex: 'model_name', ellipsis: true },
    {
      title: '向量维度',
      dataIndex: 'embedding_dim',
      width: 100,
      render: v => <Tag>{v}</Tag>
    },
    {
      title: '批处理',
      dataIndex: 'max_batch_size',
      width: 90
    },
    {
      title: '超时(秒)',
      dataIndex: 'request_timeout',
      width: 90
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: v => v ? <Tag color="green">激活</Tag> : <Tag>禁用</Tag>
    },
    {
      title: '操作',
      width: 200,
      render: (_, record) => (
        <Space>
          <Tooltip title="编辑">
            <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
          <Tooltip title="测试">
            <Button size="small" icon={<ThunderboltOutlined />} onClick={() => openTestModal(record)} />
          </Tooltip>
          {!record.is_default && (
            <Tooltip title="设为默认">
              <Button
                size="small"
                icon={<CheckCircleOutlined />}
                onClick={() => handleSetDefault(record.id)}
              />
            </Tooltip>
          )}
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="删除">
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      )
    }
  ];

  // 移动端卡片渲染
  const renderMobileCard = (record) => (
    <Card key={record.id} size="small" style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <DatabaseOutlined style={{ color: '#1890ff' }} />
            <span style={{ fontWeight: 500 }}>{record.name}</span>
            {record.is_default && <Tag color="blue">默认</Tag>}
          </div>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>{record.model_name}</div>
          <div style={{ fontSize: 11, color: '#999', marginBottom: 8 }}>{record.api_base_url}</div>
          <Space size={4} wrap>
            <Tag>{record.embedding_dim}维</Tag>
            <Tag>批{record.max_batch_size}</Tag>
            {record.is_active ? <Tag color="green">激活</Tag> : <Tag>禁用</Tag>}
          </Space>
        </div>
        <Space direction="vertical" size={4}>
          <Button size="small" icon={<ThunderboltOutlined />} onClick={() => openTestModal(record)}>测试</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          {!record.is_default && (
            <Button size="small" icon={<CheckCircleOutlined />} onClick={() => handleSetDefault(record.id)}>默认</Button>
          )}
        </Space>
      </div>
    </Card>
  );

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: isMobile ? 16 : 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <DatabaseOutlined /> 嵌入模型管理
        </h2>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size={isMobile ? 'small' : 'middle'}
          onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}
        >
          {isMobile ? '添加' : '添加嵌入供应商'}
        </Button>
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
          scroll={{ x: 1200 }}
        />
      )}

      {/* 创建/编辑模态框 */}
      <Modal
        title={editingId ? '编辑嵌入供应商' : '添加嵌入供应商'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        footer={null}
        width={isMobile ? '95vw' : 600}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item name="name" label="供应商名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如: 黑白 Qwen Embedding" />
          </Form.Item>

          <Form.Item name="api_base_url" label="API地址" rules={[{ required: true, message: '请输入API地址' }]}>
            <Input placeholder="https://api.example.com" />
          </Form.Item>

          <Form.Item
            name="api_key"
            label="API Key"
            rules={editingId ? [] : [{ required: true, message: '请输入API Key' }]}
            extra={editingId ? '留空则不修改' : ''}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>

          <Form.Item name="model_name" label="模型名称" rules={[{ required: true, message: '请输入模型名称' }]}>
            <Input placeholder="例如: Qwen/Qwen3-Embedding-8B" />
          </Form.Item>

          <Form.Item name="embedding_dim" label="向量维度" initialValue={1024}>
            <InputNumber min={1} max={8192} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item name="max_batch_size" label="最大批处理大小" initialValue={32}>
            <InputNumber min={1} max={512} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item name="request_timeout" label="请求超时(秒)" initialValue={30}>
            <InputNumber min={1} max={300} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item name="monthly_budget" label="月度预算(可选)">
            <InputNumber min={0} precision={2} style={{ width: '100%' }} placeholder="留空表示无限制" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                {editingId ? '更新' : '创建'}
              </Button>
              <Button onClick={() => { setModalOpen(false); setEditingId(null); }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 测试模态框 */}
      <Modal
        title="测试嵌入供应商"
        open={testModalOpen}
        onCancel={() => { setTestModalOpen(false); setTestingId(null); setTestResult(null); }}
        footer={null}
        width={isMobile ? '95vw' : 600}
      >
        <Form form={testForm} onFinish={handleTest} layout="vertical">
          <Form.Item name="text" label="测试文本" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="输入要测试的文本内容" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={testLoading}>
              开始测试
            </Button>
          </Form.Item>
        </Form>

        {testResult && (
          <div style={{
            marginTop: 16,
            padding: 12,
            background: testResult.success ? '#f6ffed' : '#fff2e8',
            border: `1px solid ${testResult.success ? '#b7eb8f' : '#ffbb96'}`,
            borderRadius: 4
          }}>
            <div><strong>测试结果:</strong></div>
            {testResult.success ? (
              <>
                <div>✓ {testResult.message}</div>
                <div>供应商: {testResult.provider_name}</div>
                <div>模型: {testResult.model_name}</div>
                <div>向量维度: {testResult.embedding_dim}</div>
                <div>耗时: {testResult.request_time}秒</div>
                <div>向量样本: [{testResult.sample_vector?.slice(0, 5).join(', ')}...]</div>
              </>
            ) : (
              <div style={{ color: '#cf1322' }}>✗ {testResult.message}</div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
