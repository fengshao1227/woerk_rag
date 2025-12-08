import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, Switch, InputNumber, message, Popconfirm, Space } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { providerAPI } from '../services/api';

export default function Providers() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form] = Form.useForm();

  const loadData = async () => {
    setLoading(true);
    try {
      const { data } = await providerAPI.list();
      setData(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleSubmit = async (values) => {
    try {
      if (editingId) {
        await providerAPI.update(editingId, values);
        message.success('更新成功');
      } else {
        await providerAPI.create(values);
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
      await providerAPI.delete(id);
      message.success('删除成功');
      loadData();
    } catch (error) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    { title: 'API格式', dataIndex: 'api_format' },
    { title: 'API Key', dataIndex: 'api_key_masked' },
    { title: 'Base URL', dataIndex: 'base_url', ellipsis: true },
    { title: '模型数', dataIndex: 'models_count' },
    { title: '状态', dataIndex: 'is_active', render: v => v ? '激活' : '禁用' },
    { title: '默认', dataIndex: 'is_default', render: v => v ? '是' : '否' },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}>
          添加供应商
        </Button>
      </div>
      <Table columns={columns} dataSource={data} rowKey="id" loading={loading} />
      <Modal
        title={editingId ? '编辑供应商' : '添加供应商'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        footer={null}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="api_format" label="API格式" rules={[{ required: true }]}>
            <Select options={[{ label: 'Anthropic', value: 'anthropic' }, { label: 'OpenAI', value: 'openai' }]} />
          </Form.Item>
          <Form.Item name="api_key" label="API Key" rules={[{ required: !editingId }]}>
            <Input.Password placeholder={editingId ? '留空则不修改' : ''} />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL">
            <Input placeholder="留空使用官方地址" />
          </Form.Item>
          <Form.Item name="request_timeout" label="请求超时(秒)" initialValue={120}>
            <InputNumber min={10} max={600} />
          </Form.Item>
          <Form.Item name="max_concurrent" label="最大并发" initialValue={10}>
            <InputNumber min={1} max={100} />
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
    </div>
  );
}
