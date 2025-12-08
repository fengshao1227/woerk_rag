import { Layout as AntLayout, Menu } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { DashboardOutlined, ApiOutlined, DatabaseOutlined, BookOutlined, LogoutOutlined, BarChartOutlined, MessageOutlined } from '@ant-design/icons';

const { Header, Sider, Content } = AntLayout;

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: '/chat', icon: <MessageOutlined />, label: '智能问答' },
    { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
    { key: '/providers', icon: <ApiOutlined />, label: 'LLM供应商' },
    { key: '/models', icon: <DatabaseOutlined />, label: 'LLM模型' },
    { key: '/usage', icon: <BarChartOutlined />, label: '使用统计' }
  ];

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider>
        <div style={{ color: '#fff', padding: '16px', fontSize: '18px', fontWeight: 'bold' }}>
          RAG Admin
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Header style={{ background: '#fff', padding: '0 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '20px', fontWeight: 'bold' }}>后台管理系统</div>
          <LogoutOutlined onClick={handleLogout} style={{ fontSize: '18px', cursor: 'pointer' }} />
        </Header>
        <Content style={{ margin: '24px', background: '#fff', padding: '24px' }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
