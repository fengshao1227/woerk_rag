import { Layout as AntLayout, Menu } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { DashboardOutlined, ApiOutlined, DatabaseOutlined, BookOutlined, LogoutOutlined, BarChartOutlined, MessageOutlined, ExperimentOutlined } from '@ant-design/icons';

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
    { key: '/usage', icon: <BarChartOutlined />, label: '使用统计' },
    { key: '/evaluation', icon: <ExperimentOutlined />, label: '系统评估' }
  ];

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        breakpoint="lg"
        collapsedWidth="0"
        onBreakpoint={(broken) => {
          console.log(broken);
        }}
        onCollapse={(collapsed, type) => {
          console.log(collapsed, type);
        }}
      >
        <div style={{ color: '#fff', padding: '16px', fontSize: '18px', fontWeight: 'bold' }}>
          AI 知识库
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
        <Header style={{ background: '#fff', padding: '0 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '18px', fontWeight: 'bold' }}>知识库管理系统</div>
          <LogoutOutlined onClick={handleLogout} style={{ fontSize: '18px', cursor: 'pointer' }} />
        </Header>
        <Content style={{ margin: '16px', background: '#fff', padding: '16px', minHeight: 280, overflow: 'initial' }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
