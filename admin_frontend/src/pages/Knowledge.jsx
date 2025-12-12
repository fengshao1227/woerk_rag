import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, message, Popconfirm, Space, Tag, Upload, Spin, Switch } from 'antd';
import { EditOutlined, DeleteOutlined, SearchOutlined, ExportOutlined, ImportOutlined, EyeOutlined, FolderOutlined, LockOutlined, GlobalOutlined } from '@ant-design/icons';
import { knowledgeAPI, groupAPI } from '../services/api';

export default function Knowledge() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [filters, setFilters] = useState({ category: null, search: null, groupId: null });
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form] = Form.useForm();
  const [importing, setImporting] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [groups, setGroups] = useState([]);

  // 加载分组列表
  const loadGroups = async () => {
    try {
      const { data: res } = await groupAPI.list(true);
      setGroups(res.items || []);
    } catch (error) {
      console.error('加载分组失败', error);
    }
  };

  const loadData = async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const { data: res } = await knowledgeAPI.list(page, pageSize, filters.category, filters.search, filters.groupId);
      setData(res.items);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadGroups(); }, []);
  useEffect(() => { loadData(); }, [filters]);

  const handleTableChange = (newPagination) => {
    loadData(newPagination.current, newPagination.pageSize);
  };

  const handleSearch = (values) => {
    setFilters(values);
    setPagination(prev => ({ ...prev, current: 1 }));
  };

  const handleEdit = (record) => {
    setEditingId(record.id);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleSubmit = async (values) => {
    try {
      await knowledgeAPI.update(editingId, values);
      message.success('更新成功');
      setModalOpen(false);
      form.resetFields();
      setEditingId(null);
      loadData(pagination.current, pagination.pageSize);
    } catch (error) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await knowledgeAPI.delete(id);
      message.success('删除成功');
      loadData(pagination.current, pagination.pageSize);
    } catch (error) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const handleExport = async () => {
    try {
      const { data } = await knowledgeAPI.export(filters.category);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `knowledge_export_${Date.now()}.json`;
      a.click();
      message.success('导出成功');
    } catch (error) {
      message.error('导出失败');
    }
  };

  const handleImport = async (file) => {
    setImporting(true);
    try {
      const { data } = await knowledgeAPI.import(file);
      message.success(data.message || '导入成功');
      loadData(pagination.current, pagination.pageSize);
    } catch (error) {
      message.error(error.response?.data?.detail || '导入失败');
    } finally {
      setImporting(false);
    }
    return false;
  };

  const handleViewDetail = async (record) => {
    setDetailModalOpen(true);
    setDetailLoading(true);
    try {
      const { data } = await knowledgeAPI.get(record.id);
      setDetailData(data);
    } catch (error) {
      message.error('获取详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '标题', dataIndex: 'title', ellipsis: true },
    { title: '分类', dataIndex: 'category', render: v => <Tag>{v}</Tag> },
    {
      title: '所属分组',
      dataIndex: 'groups',
      width: 150,
      render: (groupList) => {
        if (!groupList || groupList.length === 0) {
          return <Tag color="default">未分组</Tag>;
        }
        // 显示前2个分组，多余的用 +N 表示
        const displayGroups = groupList.slice(0, 2);
        const extraCount = groupList.length - 2;
        return (
          <Space size={2} wrap>
            {displayGroups.map(g => (
              <Tag
                key={g.id}
                color={g.is_public ? 'green' : 'blue'}
                icon={g.is_public ? <GlobalOutlined /> : <LockOutlined />}
              >
                {g.name}
              </Tag>
            ))}
            {extraCount > 0 && <Tag>+{extraCount}</Tag>}
          </Space>
        );
      }
    },
    { title: '归属', dataIndex: 'username', width: 80, render: v => v || 'admin' },
    { title: '摘要', dataIndex: 'summary', ellipsis: true },
    { title: '关键词', dataIndex: 'keywords', render: v => v?.slice(0, 3).map(k => <Tag key={k} color="blue">{k}</Tag>) },
    { title: '创建时间', dataIndex: 'created_at', render: v => new Date(v).toLocaleString() },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record)} />
          {record.can_edit && (
            <>
              <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
              <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            </>
          )}
        </Space>
      )
    }
  ];

  return (
    <div>
      <Form layout="inline" onFinish={handleSearch} style={{ marginBottom: 16 }}>
        <Form.Item name="groupId">
          <Select placeholder="分组" allowClear style={{ width: 150 }}>
            {groups.map(g => (
              <Select.Option key={g.id} value={g.id}>
                <Space>
                  <FolderOutlined style={{ color: g.color }} />
                  <span>{g.name}</span>
                  <Tag style={{ marginLeft: 4 }}>{g.items_count}</Tag>
                </Space>
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item name="category">
          <Select placeholder="分类" allowClear style={{ width: 120 }}>
            <Select.Option value="general">通用</Select.Option>
            <Select.Option value="project">项目</Select.Option>
            <Select.Option value="skill">技能</Select.Option>
            <Select.Option value="note">笔记</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item name="search">
          <Input placeholder="搜索标题/摘要" style={{ width: 200 }} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>搜索</Button>
        </Form.Item>
        <Form.Item>
          <Button icon={<ExportOutlined />} onClick={handleExport}>导出</Button>
        </Form.Item>
        <Form.Item>
          <Upload
            accept=".json"
            showUploadList={false}
            beforeUpload={handleImport}
          >
            <Button icon={<ImportOutlined />} loading={importing}>导入</Button>
          </Upload>
        </Form.Item>
      </Form>
      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={pagination}
        onChange={handleTableChange}
        scroll={{ x: 800 }}
      />
      <Modal
        title="编辑知识条目"
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingId(null); }}
        footer={null}
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item name="title" label="标题">
            <Input />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select>
              <Select.Option value="general">通用</Select.Option>
              <Select.Option value="project">项目</Select.Option>
              <Select.Option value="skill">技能</Select.Option>
              <Select.Option value="note">笔记</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="summary" label="摘要">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="is_public" label="可见性" valuePropName="checked">
            <Switch
              checkedChildren={<><GlobalOutlined /> 公开</>}
              unCheckedChildren={<><LockOutlined /> 私有</>}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>提交</Button>
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title="知识条目详情"
        open={detailModalOpen}
        onCancel={() => { setDetailModalOpen(false); setDetailData(null); }}
        footer={null}
        width="min(800px, 95vw)"
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
          </div>
        ) : detailData ? (
          <div>
            <div style={{ marginBottom: 16 }}>
              <strong>标题：</strong>{detailData.title || '无标题'}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>分类：</strong><Tag>{detailData.category}</Tag>
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>摘要：</strong>
              <div style={{ marginTop: 8, color: '#666' }}>{detailData.summary || '无摘要'}</div>
            </div>
            {detailData.keywords?.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>关键词：</strong>
                <div style={{ marginTop: 8 }}>
                  {detailData.keywords.map(k => <Tag key={k} color="blue">{k}</Tag>)}
                </div>
              </div>
            )}
            {detailData.tech_stack?.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>技术栈：</strong>
                <div style={{ marginTop: 8 }}>
                  {detailData.tech_stack.map(t => <Tag key={t} color="green">{t}</Tag>)}
                </div>
              </div>
            )}
            <div style={{ marginBottom: 16 }}>
              <strong>完整内容：</strong>
              <div style={{
                marginTop: 8,
                padding: 16,
                background: '#f5f5f5',
                borderRadius: 4,
                maxHeight: 400,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                fontFamily: 'monospace',
                fontSize: 13
              }}>
                {detailData.content || detailData.content_preview || '无内容'}
              </div>
            </div>
            <div style={{ color: '#999', fontSize: 12 }}>
              创建时间：{new Date(detailData.created_at).toLocaleString()}
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
