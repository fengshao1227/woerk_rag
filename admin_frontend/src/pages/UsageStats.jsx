import { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Select, Spin, message } from 'antd';
import {
  LineChartOutlined,
  DollarOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import { usageAPI } from '../services/api';

const { Option } = Select;

export default function UsageStats() {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [days, setDays] = useState(30);

  useEffect(() => {
    loadData();
  }, [days]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, logsRes] = await Promise.all([
        usageAPI.getStats(days),
        usageAPI.getLogs(null, null, null, days, 100)
      ]);
      setStats(statsRes.data);
      setLogs(logsRes.data);
    } catch (error) {
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text) => new Date(text).toLocaleString('zh-CN')
    },
    {
      title: '供应商',
      dataIndex: 'provider_name',
      key: 'provider_name',
      width: 120
    },
    {
      title: '模型',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 150
    },
    {
      title: 'Tokens',
      key: 'tokens',
      width: 120,
      render: (_, record) => (
        <span>
          {record.prompt_tokens} / {record.completion_tokens}
        </span>
      )
    },
    {
      title: '总计',
      dataIndex: 'total_tokens',
      key: 'total_tokens',
      width: 80
    },
    {
      title: '费用',
      dataIndex: 'cost',
      key: 'cost',
      width: 100,
      render: (cost) => `$${cost.toFixed(4)}`
    },
    {
      title: '耗时',
      dataIndex: 'request_time',
      key: 'request_time',
      width: 80,
      render: (time) => `${time.toFixed(2)}s`
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status) => (
        status === 'success'
          ? <CheckCircleOutlined style={{ color: '#52c41a' }} />
          : <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
      )
    }
  ];

  if (loading && !stats) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>使用量统计</h2>
        <Select value={days} onChange={setDays} style={{ width: 120 }}>
          <Option value={7}>最近7天</Option>
          <Option value={30}>最近30天</Option>
          <Option value={90}>最近90天</Option>
        </Select>
      </div>

      {/* 概览统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="总请求数"
              value={stats?.total_requests || 0}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="成功率"
              value={stats?.total_requests
                ? ((stats.success_requests / stats.total_requests) * 100).toFixed(1)
                : 0}
              suffix="%"
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="总Token数"
              value={stats?.total_tokens || 0}
              prefix={<LineChartOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="总费用"
              value={stats?.total_cost || 0}
              precision={4}
              prefix={<DollarOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={8}>
          <Card>
            <Statistic
              title="平均响应时间"
              value={stats?.avg_request_time || 0}
              precision={2}
              suffix="秒"
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card>
            <Statistic
              title="成功请求"
              value={stats?.success_requests || 0}
              valueStyle={{ color: '#3f8600' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card>
            <Statistic
              title="失败请求"
              value={stats?.error_requests || 0}
              valueStyle={{ color: '#cf1322' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 按模型统计 */}
      {stats?.by_model && stats.by_model.length > 0 && (
        <Card title="按模型统计" style={{ marginBottom: 16 }}>
          <Row gutter={[16, 16]}>
            {stats.by_model.map((item, index) => (
              <Col xs={24} sm={12} md={6} key={index}>
                <Card size="small">
                  <div style={{ fontWeight: 'bold', marginBottom: 8 }}>{item.name}</div>
                  <div>请求数: {item.count}</div>
                  <div>Tokens: {item.tokens.toLocaleString()}</div>
                  <div>费用: ${item.cost.toFixed(4)}</div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {/* 按供应商统计 */}
      {stats?.by_provider && stats.by_provider.length > 0 && (
        <Card title="按供应商统计" style={{ marginBottom: 16 }}>
          <Row gutter={[16, 16]}>
            {stats.by_provider.map((item, index) => (
              <Col xs={24} sm={12} md={6} key={index}>
                <Card size="small">
                  <div style={{ fontWeight: 'bold', marginBottom: 8 }}>{item.name}</div>
                  <div>请求数: {item.count}</div>
                  <div>Tokens: {item.tokens.toLocaleString()}</div>
                  <div>费用: ${item.cost.toFixed(4)}</div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {/* 使用记录表格 */}
      <Card title="使用记录">
        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          size="small"
          pagination={{ pageSize: 20 }}
          loading={loading}
          scroll={{ x: 1000 }}
        />
      </Card>
    </div>
  );
}
