import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, Switch, InputNumber, message, Popconfirm, Space } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, StarOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { modelAPI, providerAPI } from '../services/api';
import ModelTestModal from '../components/ModelTestModal';

export default function Models() {
  const [data, setData] = useState([]);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form] = Form.useForm();
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testingModel, setTestingModel] = useState(null);

  const handleTest = (record) => {
    setTestingModel(record);
    setTestModalOpen(true);
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [modelsRes, providersRes] = await Promise.all([modelAPI.list(), providerAPI.list()]);
      setData(modelsRes.data);
      setProviders(providersRes.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleSubmit = async (values) => {
    try {
      if (editingId) {
        await modelAPI.update(editingId, values);
        message.success('更新成功');
      } else {
        await modelAPI.create(values);
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
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleDelete = async (id) => {
    try {
      await modelAPI.delete(id);
      message.success('删除成功');
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const handleSetDefault = async (id) => {
    try {
      await modelAPI.setDefault(id);
      message.success('已设为默认模型');
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '显示名称', dataIndex: 'display_name' },
    { title: '模型ID', dataIndex: 'model_id' },
    { title: '供应商', dataIndex: 'provider_name' },
    { title: '温度', dataIndex: 'temperature' },
    { title: 'Max Tokens', dataIndex: 'max_tokens' },
    { title: '状态', dataIndex: 'is_active', render: v => v ? '激活' : '禁用' },
    { title: '默认', dataIndex: 'is_default', render: v => v ? '是' : '否' },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          <Button size="small" type="primary" icon={<PlayCircleOutlined />} onClick={() => handleTest(record)} title="测试模型" />
          <Button size="small" icon={<StarOutlined />} onClick={() => handleSetDefault(record.id)} disabled={record.is_default} title="设为默认" />
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} title="编辑" />
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} title="删除" />
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}>
          添加模型
        </Button>
      </div>
      <Table columns={columns} dataSource={data} rowKey="id" loading={loading} scroll={{ x: 800 }} />
      <Modal
        title={editingId ? '编辑模型' : '添加模型'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        footer={null}
        width="min(600px, 95vw)"
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item name="provider_id" label="供应商" rules={[{ required: true }]}>
            <Select options={providers.map(p => ({ label: p.name, value: p.id }))} />
          </Form.Item>
          <Form.Item name="model_id" label="模型ID" rules={[{ required: true }]}>
            <Input placeholder="如: claude-3-5-haiku-20241022" />
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
      <ModelTestModal
        visible={testModalOpen}
        model={testingModel}
        onClose={() => { setTestModalOpen(false); setTestingModel(null); }}
      />
    </div>
  );
}
