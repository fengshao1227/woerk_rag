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
import Agent from './pages/Agent';
import Evaluation from './pages/Evaluation';
import EmbeddingProviders from './pages/EmbeddingProviders';
import ApiKeys from './pages/ApiKeys';

function PrivateRoute({ children }) {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" />;
}

export default function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter basename="/admin">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="channels" element={<Channels />} />
            <Route path="embedding-providers" element={<EmbeddingProviders />} />
            <Route path="knowledge" element={<Knowledge />} />
            <Route path="groups" element={<Groups />} />
            <Route path="usage" element={<UsageStats />} />
            <Route path="chat" element={<Chat />} />
            <Route path="agent" element={<Agent />} />
            <Route path="evaluation" element={<Evaluation />} />
            <Route path="api-keys" element={<ApiKeys />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
