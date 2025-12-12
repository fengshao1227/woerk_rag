import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Tag } from 'antd';
import { DatabaseOutlined, ApiOutlined, BookOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { statsAPI } from '../services/api';
import useResponsive from '../hooks/useResponsive';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const { isMobile } = useResponsive();

  useEffect(() => {
    statsAPI.getStats().then(({ data }) => setStats(data));
  }, []);

  if (!stats) return <div style={{ padding: 20, textAlign: 'center' }}>加载中...</div>;

  return (
    <div>
      <h2 style={{ fontSize: isMobile ? 18 : 22, marginBottom: isMobile ? 12 : 16 }}>系统概览</h2>
      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
        <Col xs={12} sm={12} md={6}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>知识条目</span>}
              value={stats.total_knowledge}
              prefix={<BookOutlined />}
              valueStyle={{ fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>LLM供应商</span>}
              value={stats.total_providers}
              prefix={<ApiOutlined />}
              valueStyle={{ fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>LLM模型</span>}
              value={stats.total_models}
              prefix={<DatabaseOutlined />}
              valueStyle={{ fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <Card bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>激活模型</span>}
              value={stats.active_models}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
      </Row>
      <Card
        title={<span style={{ fontSize: isMobile ? 14 : 16 }}>知识库分类统计</span>}
        style={{ marginTop: isMobile ? 12 : 16 }}
        bodyStyle={{ padding: isMobile ? 12 : 24 }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {Object.entries(stats.categories).map(([cat, count]) => (
            <Tag key={cat} color="blue" style={{ margin: 2, fontSize: isMobile ? 11 : 12 }}>
              {cat}: {count}
            </Tag>
          ))}
        </div>
      </Card>
    </div>
  );
}
