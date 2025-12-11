import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, message, Popconfirm, Space, Tag, Card, Row, Col, Badge, Tooltip, Transfer } from 'antd';
import { EditOutlined, DeleteOutlined, PlusOutlined, FolderOutlined, AppstoreOutlined, SettingOutlined, InboxOutlined } from '@ant-design/icons';
import { groupAPI, knowledgeAPI } from '../services/api';

// 预定义颜色
const COLORS = [
  { value: '#1890ff', label: '蓝色' },
  { value: '#52c41a', label: '绿色' },
  { value: '#faad14', label: '橙色' },
  { value: '#eb2f96', label: '粉色' },
  { value: '#722ed1', label: '紫色' },
  { value: '#13c2c2', label: '青色' },
  { value: '#fa541c', label: '红橙' },
  { value: '#2f54eb', label: '深蓝' },
];

// 预定义图标
const ICONS = [
  { value: 'folder', label: '文件夹' },
  { value: 'book', label: '书籍' },
  { value: 'code', label: '代码' },
  { value: 'experiment', label: '实验' },
  { value: 'star', label: '星标' },
  { value: 'file', label: '文件' },
  { value: 'database', label: '数据库' },
  { value: 'api', label: 'API' },
];

export default function Groups() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState(null);
  const [form] = Form.useForm();

  // 分组条目管理
  const [itemsModalOpen, setItemsModalOpen] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [allKnowledge, setAllKnowledge] = useState([]);
  const [transferTargetKeys, setTransferTargetKeys] = useState([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  // 未分组分配到其他组
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignTargetGroup, setAssignTargetGroup] = useState(null);
  const [selectedUngroupedKeys, setSelectedUngroupedKeys] = useState([]);
  const [ungroupedItems, setUngroupedItems] = useState([]);

  const loadGroups = async () => {
    setLoading(true);
    try {
      const { data } = await groupAPI.list(true);
      setGroups(data.items || []);
    } catch (error) {
      message.error('加载分组失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadGroups(); }, []);

  const handleCreate = () => {
    setEditingGroup(null);
    form.resetFields();
    form.setFieldsValue({ color: '#1890ff', icon: 'folder' });
    setModalOpen(true);
  };

  const handleEdit = (group) => {
    setEditingGroup(group);
    form.setFieldsValue(group);
    setModalOpen(true);
  };

  const handleSubmit = async (values) => {
    try {
      if (editingGroup) {
        await groupAPI.update(editingGroup.id, values);
        message.success('更新成功');
      } else {
        await groupAPI.create(values);
        message.success('创建成功');
      }
      setModalOpen(false);
      form.resetFields();
      setEditingGroup(null);
      loadGroups();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await groupAPI.delete(id);
      message.success('删除成功');
      loadGroups();
    } catch (error) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 管理分组条目
  const handleManageItems = async (group) => {
    // 未分组使用特殊的分配模式
    if (group.is_default) {
      setSelectedGroup(group);
      setItemsLoading(true);
      setAssignModalOpen(true);
      setSelectedUngroupedKeys([]);
      setAssignTargetGroup(null);

      try {
        // 加载未分组的知识条目
        const { data: items } = await groupAPI.listItems(0);
        setUngroupedItems(items || []);
      } catch (error) {
        message.error('加载数据失败');
      } finally {
        setItemsLoading(false);
      }
      return;
    }

    // 正常分组使用 Transfer
    setSelectedGroup(group);
    setItemsLoading(true);
    setItemsModalOpen(true);

    try {
      // 加载当前分组条目
      const { data: currentItems } = await groupAPI.listItems(group.id);
      setTransferTargetKeys((currentItems || []).map(item => item.qdrant_id));

      // 分页加载所有知识条目
      let allKnowledge = [];
      let page = 1;
      const pageSize = 100;
      let hasMore = true;

      while (hasMore) {
        const { data: knowledgeData } = await knowledgeAPI.list(page, pageSize, null, null);
        const items = knowledgeData.items || [];
        allKnowledge = [...allKnowledge, ...items];
        hasMore = items.length === pageSize && allKnowledge.length < knowledgeData.total;
        page++;
      }

      setAllKnowledge(allKnowledge);
    } catch (error) {
      message.error('加载数据失败');
    } finally {
      setItemsLoading(false);
    }
  };

  const handleTransferChange = async (targetKeys, direction, moveKeys) => {
    try {
      if (direction === 'right') {
        await groupAPI.addItems(selectedGroup.id, moveKeys);
        message.success(`已添加 ${moveKeys.length} 个条目`);
      } else {
        for (const key of moveKeys) {
          await groupAPI.removeItem(selectedGroup.id, key);
        }
        message.success(`已移除 ${moveKeys.length} 个条目`);
      }
      setTransferTargetKeys(targetKeys);
      loadGroups();
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  // 分配未分组知识到指定分组
  const handleAssignToGroup = async () => {
    if (!assignTargetGroup || selectedUngroupedKeys.length === 0) {
      message.warning('请选择目标分组和要分配的知识');
      return;
    }

    try {
      await groupAPI.addItems(assignTargetGroup, selectedUngroupedKeys);
      message.success(`已将 ${selectedUngroupedKeys.length} 个知识分配到分组`);
      setAssignModalOpen(false);
      setSelectedUngroupedKeys([]);
      setAssignTargetGroup(null);
      loadGroups();
    } catch (error) {
      message.error(error.response?.data?.detail || '分配失败');
    }
  };

  // 表格列定义
  const columns = [
    {
      title: '分组名称',
      dataIndex: 'name',
      render: (text, record) => (
        <Space>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 28,
            height: 28,
            borderRadius: 4,
            backgroundColor: record.color + '20',
            color: record.color
          }}>
            {record.is_default ? <InboxOutlined /> : <FolderOutlined />}
          </span>
          <span style={{ fontWeight: 500 }}>{text}</span>
          {record.is_default && <Tag color="default">默认</Tag>}
        </Space>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
      render: v => v || <span style={{ color: '#999' }}>暂无描述</span>
    },
    {
      title: '知识条目',
      dataIndex: 'items_count',
      width: 100,
      render: v => <Badge count={v} showZero color="#1890ff" />
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: v => v ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: v => new Date(v).toLocaleString()
    },
    {
      title: '操作',
      width: 180,
      render: (_, record) => (
        <Space>
          <Tooltip title={record.is_default ? "分配到其他分组" : "管理条目"}>
            <Button size="small" icon={<AppstoreOutlined />} onClick={() => handleManageItems(record)} />
          </Tooltip>
          {!record.is_default && (
            <>
              <Tooltip title="编辑">
                <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
              </Tooltip>
              <Popconfirm title="确认删除此分组?" onConfirm={() => handleDelete(record.id)}>
                <Tooltip title="删除">
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Tooltip>
              </Popconfirm>
            </>
          )}
        </Space>
      )
    }
  ];

  // 获取非默认分组列表（用于分配目标选择）
  const targetGroups = groups.filter(g => !g.is_default);

  return (
    <div>
      <Card
        title={
          <Space>
            <FolderOutlined />
            <span>知识分组管理</span>
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            新建分组
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={groups}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      {/* 创建/编辑分组弹窗 */}
      <Modal
        title={editingGroup ? '编辑分组' : '新建分组'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingGroup(null); }}
        footer={null}
        width={500}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item
            name="name"
            label="分组名称"
            rules={[{ required: true, message: '请输入分组名称' }]}
          >
            <Input placeholder="如：项目A、技术文档、学习笔记" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="分组描述（可选）" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="color" label="颜色">
                <Select>
                  {COLORS.map(c => (
                    <Select.Option key={c.value} value={c.value}>
                      <Space>
                        <span style={{
                          display: 'inline-block',
                          width: 14,
                          height: 14,
                          borderRadius: 2,
                          backgroundColor: c.value
                        }} />
                        {c.label}
                      </Space>
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="icon" label="图标">
                <Select>
                  {ICONS.map(i => (
                    <Select.Option key={i.value} value={i.value}>
                      {i.label}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              {editingGroup ? '保存' : '创建'}
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 管理分组条目弹窗（非默认分组） */}
      <Modal
        title={
          <Space>
            <SettingOutlined />
            <span>管理分组条目</span>
            {selectedGroup && (
              <Tag color={selectedGroup.color}>{selectedGroup.name}</Tag>
            )}
          </Space>
        }
        open={itemsModalOpen}
        onCancel={() => { setItemsModalOpen(false); setSelectedGroup(null); }}
        footer={null}
        width={900}
      >
        <Transfer
          dataSource={allKnowledge.map(item => ({
            key: item.qdrant_id,
            title: item.title || '无标题',
            description: item.summary?.slice(0, 50) || '',
            category: item.category
          }))}
          titles={['可选知识', '已分组']}
          targetKeys={transferTargetKeys}
          onChange={handleTransferChange}
          render={item => (
            <span>
              <Tag color="blue" style={{ marginRight: 8 }}>{item.category}</Tag>
              {item.title}
            </span>
          )}
          listStyle={{ width: 380, height: 400 }}
          showSearch
          filterOption={(inputValue, option) =>
            option.title.toLowerCase().includes(inputValue.toLowerCase())
          }
          loading={itemsLoading}
        />
      </Modal>

      {/* 未分组知识分配弹窗 */}
      <Modal
        title={
          <Space>
            <InboxOutlined />
            <span>分配未分组知识</span>
            <Tag color="#999999">未分组</Tag>
          </Space>
        }
        open={assignModalOpen}
        onCancel={() => { setAssignModalOpen(false); setSelectedGroup(null); }}
        onOk={handleAssignToGroup}
        okText="分配"
        okButtonProps={{ disabled: !assignTargetGroup || selectedUngroupedKeys.length === 0 }}
        width={700}
      >
        <div style={{ marginBottom: 16 }}>
          <span style={{ marginRight: 8 }}>目标分组：</span>
          <Select
            placeholder="选择要分配到的分组"
            style={{ width: 200 }}
            value={assignTargetGroup}
            onChange={setAssignTargetGroup}
          >
            {targetGroups.map(g => (
              <Select.Option key={g.id} value={g.id}>
                <Space>
                  <FolderOutlined style={{ color: g.color }} />
                  {g.name}
                </Space>
              </Select.Option>
            ))}
          </Select>
          {selectedUngroupedKeys.length > 0 && (
            <Tag color="blue" style={{ marginLeft: 16 }}>
              已选择 {selectedUngroupedKeys.length} 项
            </Tag>
          )}
        </div>
        <Table
          size="small"
          loading={itemsLoading}
          dataSource={ungroupedItems}
          rowKey="qdrant_id"
          rowSelection={{
            selectedRowKeys: selectedUngroupedKeys,
            onChange: setSelectedUngroupedKeys,
          }}
          columns={[
            { title: '标题', dataIndex: 'title', ellipsis: true },
            { title: '创建时间', dataIndex: 'created_at', width: 170, render: v => new Date(v).toLocaleString() },
          ]}
          pagination={{ pageSize: 10 }}
          scroll={{ y: 300 }}
        />
      </Modal>
    </div>
  );
}
