import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, message, Popconfirm, Space, Tag, Card, Switch } from 'antd';
import { EditOutlined, DeleteOutlined, PlusOutlined, UserOutlined, KeyOutlined, CrownOutlined } from '@ant-design/icons';
import { userAPI } from '../services/api';

export default function Users() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [form] = Form.useForm();

  const loadUsers = async () => {
    setLoading(true);
    try {
      const { data } = await userAPI.list();
      setUsers(data.items || []);
    } catch (error) {
      message.error('加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, []);

  const handleCreate = () => {
    setEditingUser(null);
    form.resetFields();
    form.setFieldsValue({ role: 'user' });
    setModalOpen(true);
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    form.setFieldsValue({
      username: user.username,
      role: user.role,
      is_active: user.is_active
    });
    setModalOpen(true);
  };

  const handleSubmit = async (values) => {
    try {
      if (editingUser) {
        // 更新时，如果密码为空则不传
        const updateData = {
          role: values.role,
          is_active: values.is_active
        };
        if (values.password) {
          updateData.password = values.password;
        }
        await userAPI.update(editingUser.id, updateData);
        message.success('更新成功');
      } else {
        await userAPI.create(values);
        message.success('创建成功');
      }
      setModalOpen(false);
      form.resetFields();
      setEditingUser(null);
      loadUsers();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await userAPI.delete(id);
      message.success('删除成功');
      loadUsers();
    } catch (error) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const handleToggleActive = async (user) => {
    try {
      await userAPI.update(user.id, { is_active: !user.is_active });
      message.success(user.is_active ? '已禁用' : '已启用');
      loadUsers();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      render: (text, record) => (
        <Space>
          <UserOutlined style={{ color: record.role === 'admin' ? '#faad14' : '#1890ff' }} />
          <span style={{ fontWeight: 500 }}>{text}</span>
          {record.role === 'admin' && (
            <CrownOutlined style={{ color: '#faad14' }} />
          )}
        </Space>
      )
    },
    {
      title: '角色',
      dataIndex: 'role',
      width: 100,
      render: v => v === 'admin'
        ? <Tag color="gold">管理员</Tag>
        : <Tag color="blue">普通用户</Tag>
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 100,
      render: (v, record) => (
        <Switch
          checked={v}
          checkedChildren="启用"
          unCheckedChildren="禁用"
          onChange={() => handleToggleActive(record)}
        />
      )
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: v => new Date(v).toLocaleString()
    },
    {
      title: '操作',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除此用户?"
            description="删除后该用户的所有数据将被保留，但无法登录"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div>
      <Card
        title={
          <Space>
            <UserOutlined />
            <span>用户管理</span>
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            新建用户
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        title={
          <Space>
            {editingUser ? <EditOutlined /> : <PlusOutlined />}
            <span>{editingUser ? '编辑用户' : '新建用户'}</span>
          </Space>
        }
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingUser(null); }}
        footer={null}
        width={450}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical" style={{ marginTop: 20 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: !editingUser, message: '请输入用户名' },
              { min: 2, message: '用户名至少2个字符' },
              { max: 50, message: '用户名最多50个字符' }
            ]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
              disabled={!!editingUser}
            />
          </Form.Item>

          <Form.Item
            name="password"
            label={editingUser ? "新密码（留空则不修改）" : "密码"}
            rules={[
              { required: !editingUser, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' }
            ]}
          >
            <Input.Password
              prefix={<KeyOutlined />}
              placeholder={editingUser ? "留空则不修改密码" : "密码"}
            />
          </Form.Item>

          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select>
              <Select.Option value="user">
                <Space>
                  <UserOutlined style={{ color: '#1890ff' }} />
                  普通用户
                </Space>
              </Select.Option>
              <Select.Option value="admin">
                <Space>
                  <CrownOutlined style={{ color: '#faad14' }} />
                  管理员
                </Space>
              </Select.Option>
            </Select>
          </Form.Item>

          {editingUser && (
            <Form.Item
              name="is_active"
              label="账户状态"
              valuePropName="checked"
            >
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
          )}

          <Form.Item style={{ marginTop: 24, marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" block>
              {editingUser ? '保存修改' : '创建用户'}
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
