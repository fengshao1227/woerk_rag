import { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, Tag, Progress, message, Popconfirm, Space, Row, Col, Statistic, Tabs, Select, Spin } from 'antd';
import { PlusOutlined, PlayCircleOutlined, DeleteOutlined, EditOutlined, ReloadOutlined, ClearOutlined } from '@ant-design/icons';
import { evalAPI, cacheAPI } from '../services/api';
import useResponsive from '../hooks/useResponsive';

const { TextArea } = Input;

export default function Evaluation() {
  const [testCases, setTestCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCase, setEditingCase] = useState(null);
  const [evalResults, setEvalResults] = useState(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [cacheStats, setCacheStats] = useState(null);
  const [form] = Form.useForm();
  const { isMobile } = useResponsive();

  useEffect(() => {
    loadTestCases();
    loadCacheStats();
  }, []);

  const loadTestCases = async () => {
    setLoading(true);
    try {
      const res = await evalAPI.listTestCases();
      setTestCases(res.data);
    } catch (error) {
      message.error('加载测试用例失败');
    } finally {
      setLoading(false);
    }
  };

  const loadCacheStats = async () => {
    try {
      const res = await cacheAPI.getStats();
      setCacheStats(res.data);
    } catch (error) {
      console.error('加载缓存统计失败', error);
    }
  };

  const handleCreate = () => {
    setEditingCase(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record) => {
    setEditingCase(record);
    form.setFieldsValue({
      ...record,
      expected_files: record.expected_files.join('\n'),
      expected_keywords: record.expected_keywords.join('\n')
    });
    setModalVisible(true);
  };

  const handleDelete = async (id) => {
    try {
      await evalAPI.deleteTestCase(id);
      message.success('删除成功');
      loadTestCases();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const data = {
        question: values.question,
        expected_files: values.expected_files ? values.expected_files.split('\n').filter(f => f.trim()) : [],
        expected_keywords: values.expected_keywords ? values.expected_keywords.split('\n').filter(k => k.trim()) : [],
        category: values.category || 'general'
      };

      if (editingCase) {
        await evalAPI.updateTestCase(editingCase.id, data);
        message.success('更新成功');
      } else {
        await evalAPI.createTestCase(data);
        message.success('创建成功');
      }
      setModalVisible(false);
      loadTestCases();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const runEvaluation = async (testCaseIds = null) => {
    setEvalLoading(true);
    try {
      const res = await evalAPI.runEvaluation(testCaseIds);
      setEvalResults(res.data);
      message.success('评估完成');
    } catch (error) {
      message.error('评估失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setEvalLoading(false);
    }
  };

  const clearCache = async () => {
    try {
      await cacheAPI.clear();
      message.success('缓存已清空');
      loadCacheStats();
    } catch (error) {
      message.error('清空缓存失败');
    }
  };

  // 移动端卡片渲染测试用例
  const renderMobileTestCard = (record) => (
    <Card key={record.id} size="small" style={{ marginBottom: 8 }}>
      <div style={{ marginBottom: 8 }}>
        <Tag color="blue" style={{ marginRight: 8 }}>{record.category}</Tag>
        <span style={{ fontSize: 12, color: '#999' }}>ID: {record.id}</span>
      </div>
      <div style={{ fontWeight: 500, marginBottom: 8, fontSize: 14 }}>
        {record.question}
      </div>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
        期望文件: {record.expected_files?.length || 0} | 关键词: {record.expected_keywords?.length || 0}
      </div>
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
        <Button
          size="small"
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={() => runEvaluation([record.id])}
          loading={evalLoading}
        >
          测试
        </Button>
        <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    </Card>
  );

  // 桌面端表格列
  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '问题', dataIndex: 'question', ellipsis: true },
    { title: '分类', dataIndex: 'category', width: 100, render: (text) => <Tag color="blue">{text}</Tag> },
    { title: '期望文件', dataIndex: 'expected_files', width: 80, render: (files) => files?.length || 0 },
    { title: '期望关键词', dataIndex: 'expected_keywords', width: 90, render: (keywords) => keywords?.length || 0 },
    {
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          <Button size="small" type="primary" icon={<PlayCircleOutlined />} onClick={() => runEvaluation([record.id])} loading={evalLoading} />
          <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    }
  ];

  // Tab 项配置
  const tabItems = [
    {
      key: 'testcases',
      label: '测试用例',
      children: (
        <Card
          title={<span style={{ fontSize: isMobile ? 14 : 16 }}>RAG 评估测试用例</span>}
          extra={
            <Space wrap size={isMobile ? 4 : 8}>
              <Button size={isMobile ? 'small' : 'middle'} icon={<ReloadOutlined />} onClick={loadTestCases}>
                {isMobile ? '' : '刷新'}
              </Button>
              <Button size={isMobile ? 'small' : 'middle'} type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                {isMobile ? '新建' : '新建测试用例'}
              </Button>
              <Button
                size={isMobile ? 'small' : 'middle'}
                type="primary"
                danger
                icon={<PlayCircleOutlined />}
                onClick={() => runEvaluation()}
                loading={evalLoading}
              >
                {isMobile ? '运行' : '运行全部评估'}
              </Button>
            </Space>
          }
          bodyStyle={{ padding: isMobile ? 8 : 24 }}
        >
          {isMobile ? (
            loading ? (
              <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
            ) : (
              testCases.map(renderMobileTestCard)
            )
          ) : (
            <Table columns={columns} dataSource={testCases} loading={loading} rowKey="id" pagination={{ pageSize: 10 }} />
          )}
        </Card>
      )
    },
    {
      key: 'results',
      label: '评估结果',
      children: (
        <Card title="评估结果" bodyStyle={{ padding: isMobile ? 12 : 24 }}>
          {evalResults ? (
            <>
              <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginBottom: 16 }}>
                <Col xs={8} sm={4}><Statistic title="总测试" value={evalResults.summary.total_cases} valueStyle={{ fontSize: isMobile ? 18 : 24 }} /></Col>
                <Col xs={8} sm={4}><Statistic title="成功" value={evalResults.summary.successful_cases} valueStyle={{ color: '#3f8600', fontSize: isMobile ? 18 : 24 }} /></Col>
                <Col xs={8} sm={4}><Statistic title="失败" value={evalResults.summary.failed_cases} valueStyle={{ color: '#cf1322', fontSize: isMobile ? 18 : 24 }} /></Col>
                <Col xs={8} sm={4}><Statistic title="文件召回" value={`${(evalResults.summary.avg_file_recall * 100).toFixed(0)}%`} valueStyle={{ fontSize: isMobile ? 16 : 24 }} /></Col>
                <Col xs={8} sm={4}><Statistic title="关键词" value={`${(evalResults.summary.avg_keyword_coverage_retrieval * 100).toFixed(0)}%`} valueStyle={{ fontSize: isMobile ? 16 : 24 }} /></Col>
                <Col xs={8} sm={4}><Statistic title="拒答率" value={`${(evalResults.summary.refusal_rate * 100).toFixed(0)}%`} valueStyle={{ fontSize: isMobile ? 16 : 24 }} /></Col>
              </Row>
              {isMobile ? (
                evalResults.results.map((record, idx) => (
                  <Card key={idx} size="small" style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 500, marginBottom: 8 }}>{record.question}</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                      <span>文件召回: <Progress percent={Math.round((record.retrieval_metrics?.file_recall || 0) * 100)} size="small" style={{ width: 80 }} /></span>
                      <span>关键词: <Progress percent={Math.round((record.retrieval_metrics?.keyword_coverage || 0) * 100)} size="small" style={{ width: 80 }} /></span>
                    </div>
                    {record.error && <Tag color="red">{record.error.substring(0, 30)}...</Tag>}
                  </Card>
                ))
              ) : (
                <Table
                  columns={[
                    { title: '问题', dataIndex: 'question', ellipsis: true, width: 200 },
                    { title: '文件召回', dataIndex: ['retrieval_metrics', 'file_recall'], width: 120, render: (v) => v != null ? <Progress percent={Math.round(v * 100)} size="small" /> : '-' },
                    { title: '关键词', dataIndex: ['retrieval_metrics', 'keyword_coverage'], width: 120, render: (v) => v != null ? <Progress percent={Math.round(v * 100)} size="small" /> : '-' },
                    { title: '拒答', dataIndex: ['answer_metrics', 'is_refusal'], width: 60, render: (v) => v ? <Tag color="red">是</Tag> : <Tag color="green">否</Tag> },
                    { title: '错误', dataIndex: 'error', width: 100, render: (e) => e ? <Tag color="red">{e.substring(0, 20)}...</Tag> : '-' }
                  ]}
                  dataSource={evalResults.results}
                  rowKey="test_case_id"
                  pagination={{ pageSize: 10 }}
                  size="small"
                />
              )}
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>运行评估后查看结果</div>
          )}
        </Card>
      )
    },
    {
      key: 'cache',
      label: '缓存统计',
      children: (
        <Card
          title="语义缓存统计"
          extra={
            <Space>
              <Button size={isMobile ? 'small' : 'middle'} icon={<ReloadOutlined />} onClick={loadCacheStats}>{isMobile ? '' : '刷新'}</Button>
              <Popconfirm title="确认清空所有缓存?" onConfirm={clearCache}>
                <Button size={isMobile ? 'small' : 'middle'} danger icon={<ClearOutlined />}>{isMobile ? '清空' : '清空缓存'}</Button>
              </Popconfirm>
            </Space>
          }
          bodyStyle={{ padding: isMobile ? 12 : 24 }}
        >
          {cacheStats ? (
            <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
              <Col xs={12} sm={6}><Statistic title="缓存条目" value={cacheStats.total_entries} valueStyle={{ fontSize: isMobile ? 20 : 24 }} /></Col>
              <Col xs={12} sm={6}><Statistic title="命中率" value={`${(cacheStats.hit_rate * 100).toFixed(1)}%`} valueStyle={{ fontSize: isMobile ? 20 : 24 }} /></Col>
              <Col xs={12} sm={6}><Statistic title="相似阈值" value={cacheStats.avg_similarity?.toFixed(2) || 0.92} valueStyle={{ fontSize: isMobile ? 20 : 24 }} /></Col>
              <Col xs={12} sm={6}><Statistic title="缓存大小" value={`${cacheStats.cache_size_mb || 0} MB`} valueStyle={{ fontSize: isMobile ? 20 : 24 }} /></Col>
            </Row>
          ) : (
            <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>加载中...</div>
          )}
        </Card>
      )
    }
  ];

  return (
    <div>
      <Tabs defaultActiveKey="testcases" items={tabItems} size={isMobile ? 'small' : 'middle'} />

      <Modal
        title={editingCase ? '编辑测试用例' : '新建测试用例'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={isMobile ? '95vw' : 600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="question" label="问题" rules={[{ required: true, message: '请输入问题' }]}>
            <TextArea rows={2} placeholder="输入测试问题" />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select placeholder="选择分类">
              <Select.Option value="general">通用</Select.Option>
              <Select.Option value="项目概述">项目概述</Select.Option>
              <Select.Option value="配置说明">配置说明</Select.Option>
              <Select.Option value="技术实现">技术实现</Select.Option>
              <Select.Option value="使用指南">使用指南</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="expected_files" label="期望文件 (每行一个)">
            <TextArea rows={3} placeholder="README.md&#10;config.py" />
          </Form.Item>
          <Form.Item name="expected_keywords" label="期望关键词 (每行一个)">
            <TextArea rows={3} placeholder="RAG&#10;知识库&#10;检索" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
