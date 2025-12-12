import { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Select, Spin, message, Tag } from 'antd';
import {
  LineChartOutlined,
  DollarOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import { usageAPI } from '../services/api';
import useResponsive from '../hooks/useResponsive';

const { Option } = Select;

export default function UsageStats() {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [days, setDays] = useState(30);
  const { isMobile } = useResponsive();

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

  // 移动端日志卡片渲染
  const renderMobileLogCard = (record) => (
    <Card key={record.id} size="small" style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 500, marginBottom: 4 }}>{record.model_name}</div>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>{record.provider_name}</div>
          <div style={{ fontSize: 11, color: '#999', marginBottom: 4 }}>
            {new Date(record.created_at).toLocaleString('zh-CN')}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Tag>{record.prompt_tokens}/{record.completion_tokens} tokens</Tag>
            <Tag color="green">${record.cost.toFixed(4)}</Tag>
            <Tag>{record.request_time.toFixed(2)}s</Tag>
          </div>
        </div>
        <div>
          {record.status === 'success'
            ? <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
            : <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 20 }} />
          }
        </div>
      </div>
    </Card>
  );

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0, fontSize: isMobile ? 16 : 20 }}>使用量统计</h2>
        <Select value={days} onChange={setDays} style={{ width: isMobile ? 100 : 120 }} size={isMobile ? 'small' : 'middle'}>
          <Option value={7}>最近7天</Option>
          <Option value={30}>最近30天</Option>
          <Option value={90}>最近90天</Option>
        </Select>
      </div>

      {/* 概览统计卡片 */}
      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginBottom: isMobile ? 16 : 24 }}>
        <Col xs={12} sm={12} md={6}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title="总请求数"
              value={stats?.total_requests || 0}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title="成功率"
              value={stats?.total_requests
                ? ((stats.success_requests / stats.total_requests) * 100).toFixed(1)
                : 0}
              suffix="%"
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600', fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title="总Token数"
              value={stats?.total_tokens || 0}
              prefix={<LineChartOutlined />}
              valueStyle={{ fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title="总费用"
              value={stats?.total_cost || 0}
              precision={4}
              prefix={<DollarOutlined />}
              valueStyle={{ fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginBottom: isMobile ? 16 : 24 }}>
        <Col xs={12} sm={12} md={8}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title="平均响应时间"
              value={stats?.avg_request_time || 0}
              precision={2}
              suffix="秒"
              prefix={<ClockCircleOutlined />}
              valueStyle={{ fontSize: isMobile ? 18 : 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={8}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title="成功请求"
              value={stats?.success_requests || 0}
              valueStyle={{ color: '#3f8600', fontSize: isMobile ? 18 : 24 }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title="失败请求"
              value={stats?.error_requests || 0}
              valueStyle={{ color: '#cf1322', fontSize: isMobile ? 18 : 24 }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 按模型统计 */}
      {stats?.by_model && stats.by_model.length > 0 && (
        <Card title="按模型统计" style={{ marginBottom: 16 }} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
          <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
            {stats.by_model.map((item, index) => (
              <Col xs={12} sm={12} md={6} key={index}>
                <Card size="small" bodyStyle={{ padding: isMobile ? 8 : 12 }}>
                  <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: isMobile ? 12 : 14 }}>{item.name}</div>
                  <div style={{ fontSize: isMobile ? 11 : 13 }}>请求数: {item.count}</div>
                  <div style={{ fontSize: isMobile ? 11 : 13 }}>Tokens: {item.tokens.toLocaleString()}</div>
                  <div style={{ fontSize: isMobile ? 11 : 13 }}>费用: ${item.cost.toFixed(4)}</div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {/* 按供应商统计 */}
      {stats?.by_provider && stats.by_provider.length > 0 && (
        <Card title="按供应商统计" style={{ marginBottom: 16 }} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
          <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
            {stats.by_provider.map((item, index) => (
              <Col xs={12} sm={12} md={6} key={index}>
                <Card size="small" bodyStyle={{ padding: isMobile ? 8 : 12 }}>
                  <div style={{ fontWeight: 'bold', marginBottom: 8, fontSize: isMobile ? 12 : 14 }}>{item.name}</div>
                  <div style={{ fontSize: isMobile ? 11 : 13 }}>请求数: {item.count}</div>
                  <div style={{ fontSize: isMobile ? 11 : 13 }}>Tokens: {item.tokens.toLocaleString()}</div>
                  <div style={{ fontSize: isMobile ? 11 : 13 }}>费用: ${item.cost.toFixed(4)}</div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {/* 使用记录表格 */}
      <Card title="使用记录" bodyStyle={{ padding: isMobile ? 12 : 24 }}>
        {isMobile ? (
          loading ? (
            <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
          ) : (
            logs.map(renderMobileLogCard)
          )
        ) : (
          <Table
            columns={columns}
            dataSource={logs}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 20 }}
            loading={loading}
            scroll={{ x: 1000 }}
          />
        )}
      </Card>
    </div>
  );
}
