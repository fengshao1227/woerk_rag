import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm, Space, Tag, Tooltip, Switch, DatePicker, Typography } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CopyOutlined, KeyOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { apiKeysAPI } from '../services/api';
import dayjs from 'dayjs';

const { Paragraph } = Typography;

export default function ApiKeys() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form] = Form.useForm();

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
      width: 150,
      render: (_, record) => (
        <Space>
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

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <KeyOutlined /> MCP 卡密管理
        </h2>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingId(null);
            form.resetFields();
            setModalOpen(true);
          }}
        >
          创建卡密
        </Button>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
        <h4 className="font-medium text-blue-700 mb-2">使用说明</h4>
        <p className="text-sm text-blue-600">
          MCP 卡密用于 Claude Desktop 连接本知识库。将卡密配置到 MCP Server 环境变量 <code className="bg-blue-100 px-1 rounded">RAG_API_KEY</code> 即可使用。
        </p>
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        scroll={{ x: 1200 }}
      />

      <Modal
        title={editingId ? '编辑卡密' : '创建卡密'}
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          setEditingId(null);
          form.resetFields();
        }}
        footer={null}
        width={500}
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
    </div>
  );
}
