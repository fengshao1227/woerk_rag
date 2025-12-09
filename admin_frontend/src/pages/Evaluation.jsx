import { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, Tag, Progress, message, Popconfirm, Space, Row, Col, Statistic, Tabs, Select } from 'antd';
import { PlusOutlined, PlayCircleOutlined, DeleteOutlined, EditOutlined, ReloadOutlined, ClearOutlined } from '@ant-design/icons';
import { evalAPI, cacheAPI } from '../services/api';

const { TextArea } = Input;
const { TabPane } = Tabs;

export default function Evaluation() {
  const [testCases, setTestCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCase, setEditingCase] = useState(null);
  const [evalResults, setEvalResults] = useState(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [cacheStats, setCacheStats] = useState(null);
  const [form] = Form.useForm();

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

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 80
    },
    {
      title: '问题',
      dataIndex: 'question',
      ellipsis: true
    },
    {
      title: '分类',
      dataIndex: 'category',
      width: 120,
      render: (text) => <Tag color="blue">{text}</Tag>
    },
    {
      title: '期望文件',
      dataIndex: 'expected_files',
      width: 150,
      render: (files) => files?.length || 0
    },
    {
      title: '期望关键词',
      dataIndex: 'expected_keywords',
      width: 150,
      render: (keywords) => keywords?.length || 0
    },
    {
      title: '操作',
      width: 180,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
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
      )
    }
  ];

  const resultColumns = [
    {
      title: '问题',
      dataIndex: 'question',
      ellipsis: true,
      width: 200
    },
    {
      title: '文件召回率',
      dataIndex: ['retrieval_metrics', 'file_recall'],
      width: 120,
      render: (value) => value != null ? (
        <Progress percent={Math.round(value * 100)} size="small" />
      ) : '-'
    },
    {
      title: '关键词覆盖',
      dataIndex: ['retrieval_metrics', 'keyword_coverage'],
      width: 120,
      render: (value) => value != null ? (
        <Progress percent={Math.round(value * 100)} size="small" status={value >= 0.7 ? 'success' : 'exception'} />
      ) : '-'
    },
    {
      title: '答案关键词',
      dataIndex: ['answer_metrics', 'keyword_coverage'],
      width: 120,
      render: (value) => value != null ? (
        <Progress percent={Math.round(value * 100)} size="small" />
      ) : '-'
    },
    {
      title: '拒答',
      dataIndex: ['answer_metrics', 'is_refusal'],
      width: 80,
      render: (value) => value ? <Tag color="red">是</Tag> : <Tag color="green">否</Tag>
    },
    {
      title: '错误',
      dataIndex: 'error',
      width: 100,
      render: (error) => error ? <Tag color="red">{error.substring(0, 20)}...</Tag> : '-'
    }
  ];

  return (
    <div>
      <Tabs defaultActiveKey="testcases">
        <TabPane tab="测试用例" key="testcases">
          <Card
            title="RAG 评估测试用例"
            extra={
              <Space>
                <Button icon={<ReloadOutlined />} onClick={loadTestCases}>刷新</Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                  新建测试用例
                </Button>
                <Button
                  type="primary"
                  danger
                  icon={<PlayCircleOutlined />}
                  onClick={() => runEvaluation()}
                  loading={evalLoading}
                >
                  运行全部评估
                </Button>
              </Space>
            }
          >
            <Table
              columns={columns}
              dataSource={testCases}
              loading={loading}
              rowKey="id"
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </TabPane>

        <TabPane tab="评估结果" key="results">
          <Card title="评估结果">
            {evalResults ? (
              <>
                <Row gutter={16} style={{ marginBottom: 16 }}>
                  <Col span={4}>
                    <Statistic title="总测试数" value={evalResults.summary.total_cases} />
                  </Col>
                  <Col span={4}>
                    <Statistic title="成功" value={evalResults.summary.successful_cases} valueStyle={{ color: '#3f8600' }} />
                  </Col>
                  <Col span={4}>
                    <Statistic title="失败" value={evalResults.summary.failed_cases} valueStyle={{ color: '#cf1322' }} />
                  </Col>
                  <Col span={4}>
                    <Statistic title="平均文件召回" value={`${(evalResults.summary.avg_file_recall * 100).toFixed(1)}%`} />
                  </Col>
                  <Col span={4}>
                    <Statistic title="平均关键词覆盖" value={`${(evalResults.summary.avg_keyword_coverage_retrieval * 100).toFixed(1)}%`} />
                  </Col>
                  <Col span={4}>
                    <Statistic title="拒答率" value={`${(evalResults.summary.refusal_rate * 100).toFixed(1)}%`} />
                  </Col>
                </Row>
                <Table
                  columns={resultColumns}
                  dataSource={evalResults.results}
                  rowKey="test_case_id"
                  pagination={{ pageSize: 10 }}
                  expandable={{
                    expandedRowRender: (record) => (
                      <div style={{ padding: 16 }}>
                        <h4>答案:</h4>
                        <p style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                          {record.answer || '无答案'}
                        </p>
                        {record.sources && record.sources.length > 0 && (
                          <>
                            <h4>参考来源:</h4>
                            <ul>
                              {record.sources.map((s, i) => (
                                <li key={i}>{s.file_path} (相似度: {s.score?.toFixed(3)})</li>
                              ))}
                            </ul>
                          </>
                        )}
                      </div>
                    )
                  }}
                />
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                运行评估后查看结果
              </div>
            )}
          </Card>
        </TabPane>

        <TabPane tab="缓存统计" key="cache">
          <Card
            title="语义缓存统计"
            extra={
              <Space>
                <Button icon={<ReloadOutlined />} onClick={loadCacheStats}>刷新</Button>
                <Popconfirm title="确认清空所有缓存?" onConfirm={clearCache}>
                  <Button danger icon={<ClearOutlined />}>清空缓存</Button>
                </Popconfirm>
              </Space>
            }
          >
            {cacheStats ? (
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic title="缓存条目数" value={cacheStats.total_entries} />
                </Col>
                <Col span={6}>
                  <Statistic title="命中率" value={`${(cacheStats.hit_rate * 100).toFixed(1)}%`} />
                </Col>
                <Col span={6}>
                  <Statistic title="相似度阈值" value={cacheStats.avg_similarity?.toFixed(2) || 0.92} />
                </Col>
                <Col span={6}>
                  <Statistic title="缓存大小" value={`${cacheStats.cache_size_mb || 0} MB`} />
                </Col>
              </Row>
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                加载中...
              </div>
            )}
          </Card>
        </TabPane>
      </Tabs>

      <Modal
        title={editingCase ? '编辑测试用例' : '新建测试用例'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="question"
            label="问题"
            rules={[{ required: true, message: '请输入问题' }]}
          >
            <TextArea rows={2} placeholder="输入测试问题" />
          </Form.Item>
          <Form.Item
            name="category"
            label="分类"
          >
            <Select placeholder="选择分类">
              <Select.Option value="general">通用</Select.Option>
              <Select.Option value="项目概述">项目概述</Select.Option>
              <Select.Option value="配置说明">配置说明</Select.Option>
              <Select.Option value="技术实现">技术实现</Select.Option>
              <Select.Option value="使用指南">使用指南</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="expected_files"
            label="期望文件 (每行一个)"
          >
            <TextArea rows={3} placeholder="README.md&#10;config.py" />
          </Form.Item>
          <Form.Item
            name="expected_keywords"
            label="期望关键词 (每行一个)"
          >
            <TextArea rows={3} placeholder="RAG&#10;知识库&#10;检索" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
