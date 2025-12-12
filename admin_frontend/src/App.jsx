import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import Login from './pages/Login';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Channels from './pages/Channels';
import Knowledge from './pages/Knowledge';
import Groups from './pages/Groups';
import UsageStats from './pages/UsageStats';
import Chat from './pages/Chat';
import Evaluation from './pages/Evaluation';
import EmbeddingProviders from './pages/EmbeddingProviders';
import ApiKeys from './pages/ApiKeys';
import MyApiKeys from './pages/MyApiKeys';
import Users from './pages/Users';

function PrivateRoute({ children }) {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" />;
}

function AdminRoute({ children }) {
  const token = localStorage.getItem('token');
  const userStr = localStorage.getItem('user');

  if (!token) {
    return <Navigate to="/login" />;
  }

  try {
    const user = JSON.parse(userStr);
    if (user?.role !== 'admin') {
      return <Navigate to="/" />;
    }
  } catch (e) {
    return <Navigate to="/" />;
  }

  return children;
}

export default function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter basename="/admin">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            {/* 所有用户可访问 */}
            <Route index element={<Dashboard />} />
            <Route path="chat" element={<Chat />} />
            <Route path="knowledge" element={<Knowledge />} />
            <Route path="groups" element={<Groups />} />
            <Route path="my-api-keys" element={<MyApiKeys />} />

            {/* 仅管理员可访问 */}
            <Route path="channels" element={<AdminRoute><Channels /></AdminRoute>} />
            <Route path="embedding-providers" element={<AdminRoute><EmbeddingProviders /></AdminRoute>} />
            <Route path="api-keys" element={<AdminRoute><ApiKeys /></AdminRoute>} />
            <Route path="users" element={<AdminRoute><Users /></AdminRoute>} />
            <Route path="usage" element={<AdminRoute><UsageStats /></AdminRoute>} />
            <Route path="evaluation" element={<AdminRoute><Evaluation /></AdminRoute>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
