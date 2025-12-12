import { useState, useEffect } from 'react';
import { Layout as AntLayout, Menu, Space, Tag } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { DashboardOutlined, ApiOutlined, BookOutlined, LogoutOutlined, BarChartOutlined, MessageOutlined, ExperimentOutlined, RobotOutlined, FolderOutlined, DatabaseOutlined, KeyOutlined, TeamOutlined, UserOutlined } from '@ant-design/icons';

const { Header, Sider, Content } = AntLayout;

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(null);

  useEffect(() => {
    // 从 localStorage 获取用户信息
    const userStr = localStorage.getItem('user');
    if (userStr) {
      try {
        setUser(JSON.parse(userStr));
      } catch (e) {
        console.error('解析用户信息失败', e);
      }
    }
  }, []);

  const isAdmin = user?.role === 'admin';

  // 基础菜单项（所有用户可见）
  const baseMenuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: '/chat', icon: <MessageOutlined />, label: '智能问答' },
    { key: '/agent', icon: <RobotOutlined />, label: '智能Agent' },
    { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
    { key: '/groups', icon: <FolderOutlined />, label: '知识分组' },
  ];

  // 管理员专属菜单项
  const adminMenuItems = [
    { key: '/channels', icon: <ApiOutlined />, label: '渠道管理' },
    { key: '/embedding-providers', icon: <DatabaseOutlined />, label: '嵌入模型' },
    { key: '/api-keys', icon: <KeyOutlined />, label: 'MCP卡密' },
    { key: '/users', icon: <TeamOutlined />, label: '用户管理' },
    { key: '/usage', icon: <BarChartOutlined />, label: '使用统计' },
    { key: '/evaluation', icon: <ExperimentOutlined />, label: '系统评估' },
  ];

  // 根据角色组合菜单
  const menuItems = isAdmin ? [...baseMenuItems, ...adminMenuItems] : baseMenuItems;

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
          <Space>
            {user && (
              <Space>
                <UserOutlined />
                <span>{user.username}</span>
                <Tag color={isAdmin ? 'gold' : 'blue'}>{isAdmin ? '管理员' : '用户'}</Tag>
              </Space>
            )}
            <LogoutOutlined onClick={handleLogout} style={{ fontSize: '18px', cursor: 'pointer' }} />
          </Space>
        </Header>
        <Content style={{ margin: '16px', background: '#fff', padding: '16px', minHeight: 280, overflow: 'initial' }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
