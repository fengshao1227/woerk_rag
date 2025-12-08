import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Select, message, Popconfirm, Space, Tag, Upload } from 'antd';
import { EditOutlined, DeleteOutlined, SearchOutlined, ExportOutlined, ImportOutlined } from '@ant-design/icons';
import { knowledgeAPI } from '../services/api';

export default function Knowledge() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [filters, setFilters] = useState({ category: null, search: null });
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form] = Form.useForm();
  const [importing, setImporting] = useState(false);

  const loadData = async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const { data: res } = await knowledgeAPI.list(page, pageSize, filters.category, filters.search);
      setData(res.items);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } finally {
      setLoading(false);
    }
  };

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
    return false; // 阻止默认上传行为
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '标题', dataIndex: 'title', ellipsis: true },
    { title: '分类', dataIndex: 'category', render: v => <Tag>{v}</Tag> },
    { title: '摘要', dataIndex: 'summary', ellipsis: true },
    { title: '关键词', dataIndex: 'keywords', render: v => v?.slice(0, 3).map(k => <Tag key={k} color="blue">{k}</Tag>) },
    { title: '创建时间', dataIndex: 'created_at', render: v => new Date(v).toLocaleString() },
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
      <Form layout="inline" onFinish={handleSearch} style={{ marginBottom: 16 }}>
        <Form.Item name="category">
          <Select placeholder="分类" allowClear style={{ width: 150 }}>
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
          <Form.Item>
            <Button type="primary" htmlType="submit" block>提交</Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
