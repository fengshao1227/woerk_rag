import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Tag } from 'antd';
import { DatabaseOutlined, ApiOutlined, BookOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { statsAPI } from '../services/api';

export default function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    statsAPI.getStats().then(({ data }) => setStats(data));
  }, []);

  if (!stats) return <div>加载中...</div>;

  return (
    <div>
      <h2>系统概览</h2>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title="知识条目" value={stats.total_knowledge} prefix={<BookOutlined />} /></Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title="LLM供应商" value={stats.total_providers} prefix={<ApiOutlined />} /></Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title="LLM模型" value={stats.total_models} prefix={<DatabaseOutlined />} /></Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title="激活模型" value={stats.active_models} prefix={<CheckCircleOutlined />} /></Card>
        </Col>
      </Row>
      <Card title="知识库分类统计" style={{ marginTop: 16 }}>
        {Object.entries(stats.categories).map(([cat, count]) => (
          <Tag key={cat} color="blue" style={{ margin: 4 }}>{cat}: {count}</Tag>
        ))}
      </Card>
    </div>
  );
}
