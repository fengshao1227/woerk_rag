import { useEffect, useState } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Switch, InputNumber,
  message, Popconfirm, Space, Tag, Collapse, Tooltip, Spin, Typography
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, StarOutlined,
  PlayCircleOutlined, CloudDownloadOutlined, DollarOutlined,
  SettingOutlined, ReloadOutlined
} from '@ant-design/icons';
import { providerAPI, modelAPI } from '../services/api';
import ModelTestModal from '../components/ModelTestModal';
import FetchModelsModal from '../components/FetchModelsModal';
import useResponsive from '../hooks/useResponsive';

const { Text } = Typography;

export default function Channels() {
  const [providers, setProviders] = useState([]);
  const [modelsMap, setModelsMap] = useState({}); // providerId -> models[]
  const [balanceMap, setBalanceMap] = useState({}); // providerId -> balance info
  const [loading, setLoading] = useState(false);
  const [loadingBalance, setLoadingBalance] = useState({}); // providerId -> loading state
  const { isMobile } = useResponsive();

  // Provider modal
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState(null);
  const [providerForm] = Form.useForm();

  // Model modal
  const [modelModalOpen, setModelModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState(null);
  const [currentProviderId, setCurrentProviderId] = useState(null);
  const [modelForm] = Form.useForm();

  // Test modal
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testingModel, setTestingModel] = useState(null);

  // Fetch models modal
  const [fetchModalOpen, setFetchModalOpen] = useState(false);
  const [fetchingProvider, setFetchingProvider] = useState(null);
  const [existingModelIds, setExistingModelIds] = useState([]);

  // Load all data
  const loadData = async () => {
    setLoading(true);
    try {
      const [providersRes, modelsRes] = await Promise.all([
        providerAPI.list(),
        modelAPI.list()
      ]);
      setProviders(providersRes.data);

      // Group models by provider_id
      const map = {};
      modelsRes.data.forEach(m => {
        if (!map[m.provider_id]) map[m.provider_id] = [];
        map[m.provider_id].push(m);
      });
      setModelsMap(map);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  // Provider CRUD
  const handleProviderSubmit = async (values) => {
    try {
      if (editingProvider) {
        await providerAPI.update(editingProvider.id, values);
        message.success('更新成功');
      } else {
        await providerAPI.create(values);
        message.success('创建成功');
      }
      setProviderModalOpen(false);
      providerForm.resetFields();
      setEditingProvider(null);
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const handleEditProvider = (record) => {
    setEditingProvider(record);
    providerForm.setFieldsValue(record);
    setProviderModalOpen(true);
  };

  const handleDeleteProvider = async (id) => {
    try {
      await providerAPI.delete(id);
      message.success('删除成功');
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // Get balance
  const handleGetBalance = async (provider) => {
    setLoadingBalance(prev => ({ ...prev, [provider.id]: true }));
    try {
      const { data } = await providerAPI.getBalance(provider.id);
      setBalanceMap(prev => ({ ...prev, [provider.id]: data }));
      if (data.error) {
        message.warning(data.error);
      } else {
        message.success('获取余额成功');
      }
    } catch (error) {
      message.error(error.response?.data?.detail || '获取余额失败');
    } finally {
      setLoadingBalance(prev => ({ ...prev, [provider.id]: false }));
    }
  };

  // Open fetch models modal
  const handleFetchModels = (provider) => {
    setFetchingProvider(provider);
    // Get existing model_ids for this provider
    const existing = (modelsMap[provider.id] || []).map(m => m.model_id);
    setExistingModelIds(existing);
    setFetchModalOpen(true);
  };

  // Model CRUD
  const handleModelSubmit = async (values) => {
    try {
      if (editingModel) {
        await modelAPI.update(editingModel.id, values);
        message.success('更新成功');
      } else {
        await modelAPI.create({ ...values, provider_id: currentProviderId });
        message.success('创建成功');
      }
      setModelModalOpen(false);
      modelForm.resetFields();
      setEditingModel(null);
      setCurrentProviderId(null);
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const handleEditModel = (record) => {
    setEditingModel(record);
    setCurrentProviderId(record.provider_id);
    modelForm.setFieldsValue(record);
    setModelModalOpen(true);
  };

  const handleDeleteModel = async (id) => {
    try {
      await modelAPI.delete(id);
      message.success('删除成功');
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const handleSetDefaultModel = async (id) => {
    try {
      await modelAPI.setDefault(id);
      message.success('已设为默认模型');
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const handleTestModel = (record) => {
    setTestingModel(record);
    setTestModalOpen(true);
  };

  // Model columns
  const modelColumns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '显示名称', dataIndex: 'display_name', ellipsis: true },
    { title: '模型ID', dataIndex: 'model_id', ellipsis: true },
    { title: '温度', dataIndex: 'temperature', width: 70 },
    { title: 'Max Tokens', dataIndex: 'max_tokens', width: 100 },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 70,
      render: v => <Tag color={v ? 'green' : 'default'}>{v ? '激活' : '禁用'}</Tag>
    },
    {
      title: '默认',
      dataIndex: 'is_default',
      width: 70,
      render: v => v ? <Tag color="blue">默认</Tag> : '-'
    },
    {
      title: '操作',
      width: 180,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="测试">
            <Button size="small" type="primary" icon={<PlayCircleOutlined />} onClick={() => handleTestModel(record)} />
          </Tooltip>
          <Tooltip title="设为默认">
            <Button size="small" icon={<StarOutlined />} onClick={() => handleSetDefaultModel(record.id)} disabled={record.is_default} />
          </Tooltip>
          <Tooltip title="编辑">
            <Button size="small" icon={<EditOutlined />} onClick={() => handleEditModel(record)} />
          </Tooltip>
          <Popconfirm title="确认删除此模型?" onConfirm={() => handleDeleteModel(record.id)}>
            <Tooltip title="删除">
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      )
    }
  ];

  // Render balance info
  const renderBalance = (provider) => {
    const balance = balanceMap[provider.id];
    const isLoading = loadingBalance[provider.id];

    if (isLoading) return <Spin size="small" />;
    if (!balance) return null;
    if (balance.error) return <Text type="warning">{balance.error}</Text>;

    const parts = [];
    if (balance.balance !== null && balance.balance !== undefined) {
      parts.push(`余额: $${balance.balance.toFixed(2)}`);
    }
    if (balance.used !== null && balance.used !== undefined) {
      parts.push(`已用: $${balance.used.toFixed(2)}`);
    }
    if (balance.total !== null && balance.total !== undefined) {
      parts.push(`总额: $${balance.total.toFixed(2)}`);
    }
    return parts.length > 0 ? <Text type="success">{parts.join(' / ')}</Text> : null;
  };

  // Render provider card
  const renderProviderCard = (provider) => {
    const models = modelsMap[provider.id] || [];
    const isOpenAI = provider.api_format === 'openai';

    const cardTitle = (
      <Space wrap size={isMobile ? 4 : 8}>
        <span style={{ fontSize: isMobile ? 14 : 16 }}>{provider.name}</span>
        <Tag color={isOpenAI ? 'blue' : 'purple'}>{provider.api_format.toUpperCase()}</Tag>
        {provider.is_default && <Tag color="gold">默认</Tag>}
        {!provider.is_active && <Tag color="red">禁用</Tag>}
      </Space>
    );

    const cardExtra = (
      <Space wrap size={isMobile ? 4 : 8}>
        {isOpenAI && (
          <>
            {!isMobile && (
              <Tooltip title="获取远程模型">
                <Button
                  size="small"
                  icon={<CloudDownloadOutlined />}
                  onClick={() => handleFetchModels(provider)}
                >
                  获取模型
                </Button>
              </Tooltip>
            )}
            <Tooltip title="获取余额">
              <Button
                size="small"
                icon={<DollarOutlined />}
                loading={loadingBalance[provider.id]}
                onClick={() => handleGetBalance(provider)}
              >
                {isMobile ? '' : '余额'}
              </Button>
            </Tooltip>
          </>
        )}
        <Tooltip title="编辑供应商">
          <Button size="small" icon={<SettingOutlined />} onClick={() => handleEditProvider(provider)} />
        </Tooltip>
        <Popconfirm title="确认删除此供应商及其所有模型?" onConfirm={() => handleDeleteProvider(provider.id)}>
          <Tooltip title="删除">
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Tooltip>
        </Popconfirm>
      </Space>
    );

    // 移动端模型卡片渲染
    const renderMobileModelCard = (model) => (
      <Card key={model.id} size="small" style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 500, marginBottom: 4 }}>{model.display_name}</div>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>{model.model_id}</div>
            <Space size={4} wrap>
              <Tag color={model.is_active ? 'green' : 'default'}>{model.is_active ? '激活' : '禁用'}</Tag>
              {model.is_default && <Tag color="blue">默认</Tag>}
              <span style={{ fontSize: 11, color: '#999' }}>T:{model.temperature} | Max:{model.max_tokens}</span>
            </Space>
          </div>
          <Space direction="vertical" size={4}>
            <Button size="small" type="primary" icon={<PlayCircleOutlined />} onClick={() => handleTestModel(model)}>测试</Button>
            <Button size="small" icon={<EditOutlined />} onClick={() => handleEditModel(model)}>编辑</Button>
          </Space>
        </div>
      </Card>
    );

    return (
      <Card
        key={provider.id}
        title={cardTitle}
        extra={cardExtra}
        style={{ marginBottom: 16 }}
        size="small"
        bodyStyle={{ padding: isMobile ? 12 : 24 }}
      >
        {/* Balance display */}
        {balanceMap[provider.id] && (
          <div style={{ marginBottom: 12, padding: '8px 12px', background: '#f5f5f5', borderRadius: 4 }}>
            {renderBalance(provider)}
          </div>
        )}

        {/* Provider info */}
        <div style={{ marginBottom: 12, color: '#666', fontSize: 12 }}>
          <Space split="|" wrap>
            <span>API Key: {provider.api_key_masked}</span>
            {provider.base_url && <span>Base URL: {provider.base_url}</span>}
            <span>超时: {provider.request_timeout}s</span>
            <span>并发: {provider.max_concurrent}</span>
          </Space>
        </div>

        {/* Mobile: fetch models button */}
        {isMobile && isOpenAI && (
          <Button
            size="small"
            icon={<CloudDownloadOutlined />}
            onClick={() => handleFetchModels(provider)}
            style={{ marginBottom: 8 }}
          >
            获取远程模型
          </Button>
        )}

        {/* Models table/cards */}
        <div style={{ marginBottom: 8 }}>
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => {
              setCurrentProviderId(provider.id);
              setEditingModel(null);
              modelForm.resetFields();
              setModelModalOpen(true);
            }}
          >
            添加模型
          </Button>
        </div>

        {isMobile ? (
          models.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', padding: 20 }}>暂无模型</div>
          ) : (
            models.map(renderMobileModelCard)
          )
        ) : (
          <Table
            columns={modelColumns}
            dataSource={models}
            rowKey="id"
            size="small"
            pagination={false}
            scroll={{ x: 700 }}
            locale={{ emptyText: '暂无模型' }}
          />
        )}
      </Card>
    );
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size={isMobile ? 'small' : 'middle'}
          onClick={() => {
            setEditingProvider(null);
            providerForm.resetFields();
            setProviderModalOpen(true);
          }}
        >
          {isMobile ? '添加' : '添加供应商'}
        </Button>
        <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading} size={isMobile ? 'small' : 'middle'}>
          {isMobile ? '' : '刷新'}
        </Button>
      </div>

      <Spin spinning={loading}>
        {providers.length === 0 && !loading ? (
          <Card>
            <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>
              暂无供应商，请先添加一个供应商
            </div>
          </Card>
        ) : (
          providers.map(p => renderProviderCard(p))
        )}
      </Spin>

      {/* Provider Modal */}
      <Modal
        title={editingProvider ? '编辑供应商' : '添加供应商'}
        open={providerModalOpen}
        onCancel={() => { setProviderModalOpen(false); setEditingProvider(null); }}
        footer={null}
        width="min(520px, 95vw)"
      >
        <Form form={providerForm} onFinish={handleProviderSubmit} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="api_format" label="API格式" rules={[{ required: true }]}>
            <Select options={[{ label: 'OpenAI', value: 'openai' }, { label: 'Anthropic', value: 'anthropic' }]} />
          </Form.Item>
          <Form.Item name="api_key" label="API Key" rules={[{ required: !editingProvider }]}>
            <Input.Password placeholder={editingProvider ? '留空则不修改' : ''} />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL">
            <Input placeholder="留空使用官方地址" />
          </Form.Item>
          <Form.Item name="request_timeout" label="请求超时(秒)" initialValue={120}>
            <InputNumber min={10} max={600} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max_concurrent" label="最大并发" initialValue={10}>
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_active" label="激活" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
          <Form.Item name="is_default" label="设为默认" valuePropName="checked" initialValue={false}>
            <Switch />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>提交</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Model Modal */}
      <Modal
        title={editingModel ? '编辑模型' : '添加模型'}
        open={modelModalOpen}
        onCancel={() => { setModelModalOpen(false); setEditingModel(null); setCurrentProviderId(null); }}
        footer={null}
        width="min(600px, 95vw)"
      >
        <Form form={modelForm} onFinish={handleModelSubmit} layout="vertical">
          <Form.Item name="model_id" label="模型ID" rules={[{ required: true }]}>
            <Input placeholder="如: gpt-4, claude-3-5-haiku-20241022" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="temperature" label="温度" initialValue={0.7}>
            <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="max_tokens" label="最大Token数" initialValue={4096}>
            <InputNumber min={1} max={200000} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="system_prompt" label="系统提示词">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="is_active" label="激活" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
          <Form.Item name="is_default" label="设为默认" valuePropName="checked" initialValue={false}>
            <Switch />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>提交</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Test Modal */}
      <ModelTestModal
        visible={testModalOpen}
        model={testingModel}
        onClose={() => { setTestModalOpen(false); setTestingModel(null); }}
      />

      {/* Fetch Models Modal */}
      <FetchModelsModal
        visible={fetchModalOpen}
        provider={fetchingProvider}
        existingModelIds={existingModelIds}
        onClose={() => { setFetchModalOpen(false); setFetchingProvider(null); }}
        onSuccess={() => loadData()}
      />
    </div>
  );
}
