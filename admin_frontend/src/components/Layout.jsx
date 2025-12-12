import { useState, useEffect } from 'react';
import { Layout as AntLayout, Menu, Space, Tag, Drawer } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined, ApiOutlined, BookOutlined, LogoutOutlined,
  BarChartOutlined, MessageOutlined, ExperimentOutlined, RobotOutlined,
  FolderOutlined, DatabaseOutlined, KeyOutlined, TeamOutlined, UserOutlined,
  MenuOutlined, CloseOutlined
} from '@ant-design/icons';

const { Header, Sider, Content } = AntLayout;

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [windowWidth, setWindowWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1200);

  // 使用 window.innerWidth 判断移动端 (< 768px)
  const isMobile = windowWidth < 768;

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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

  // 路由变化时关闭抽屉
  useEffect(() => {
    setDrawerVisible(false);
  }, [location.pathname]);

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

  const handleMenuClick = ({ key }) => {
    navigate(key);
    if (isMobile) {
      setDrawerVisible(false);
    }
  };

  // 菜单内容
  const menuContent = (
    <>
      <div style={{
        color: '#fff',
        padding: '16px',
        fontSize: '18px',
        fontWeight: 'bold',
        borderBottom: '1px solid rgba(255,255,255,0.1)'
      }}>
        AI 知识库
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={handleMenuClick}
      />
    </>
  );

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      {/* 桌面端侧边栏 */}
      {!isMobile && (
        <Sider
          width={200}
          style={{
            overflow: 'auto',
            height: '100vh',
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
          }}
        >
          {menuContent}
        </Sider>
      )}

      {/* 移动端抽屉菜单 */}
      {isMobile && (
        <Drawer
          placement="left"
          closable={false}
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          width={250}
          styles={{
            body: { padding: 0, background: '#001529' },
            header: { display: 'none' }
          }}
        >
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px',
            borderBottom: '1px solid rgba(255,255,255,0.1)'
          }}>
            <span style={{ color: '#fff', fontSize: '18px', fontWeight: 'bold' }}>
              AI 知识库
            </span>
            <CloseOutlined
              style={{ color: '#fff', fontSize: '16px', cursor: 'pointer' }}
              onClick={() => setDrawerVisible(false)}
            />
          </div>
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={handleMenuClick}
          />
          {/* 用户信息 */}
          {user && (
            <div style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              padding: '16px',
              borderTop: '1px solid rgba(255,255,255,0.1)',
              background: '#001529'
            }}>
              <div style={{ color: '#fff', marginBottom: 8 }}>
                <UserOutlined style={{ marginRight: 8 }} />
                {user.username}
                <Tag color={isAdmin ? 'gold' : 'blue'} style={{ marginLeft: 8 }}>
                  {isAdmin ? '管理员' : '用户'}
                </Tag>
              </div>
              <div
                style={{ color: '#ff4d4f', cursor: 'pointer' }}
                onClick={handleLogout}
              >
                <LogoutOutlined style={{ marginRight: 8 }} />
                退出登录
              </div>
            </div>
          )}
        </Drawer>
      )}

      <AntLayout style={{ marginLeft: isMobile ? 0 : 200 }}>
        <Header style={{
          background: '#fff',
          padding: isMobile ? '0 12px' : '0 16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          position: 'sticky',
          top: 0,
          zIndex: 100,
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* 移动端菜单按钮 */}
            {isMobile && (
              <MenuOutlined
                style={{ fontSize: '20px', cursor: 'pointer' }}
                onClick={() => setDrawerVisible(true)}
              />
            )}
            <span style={{
              fontSize: isMobile ? '14px' : '18px',
              fontWeight: 'bold',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {isMobile ? '知识库' : '知识库管理系统'}
            </span>
          </div>

          {/* 桌面端用户信息 */}
          {!isMobile && (
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
          )}

          {/* 移动端只显示登出按钮 */}
          {isMobile && (
            <LogoutOutlined onClick={handleLogout} style={{ fontSize: '18px', cursor: 'pointer' }} />
          )}
        </Header>

        <Content style={{
          margin: isMobile ? '8px' : '16px',
          background: '#fff',
          padding: isMobile ? '12px' : '16px',
          minHeight: 280,
          overflow: 'initial',
          borderRadius: 8
        }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
