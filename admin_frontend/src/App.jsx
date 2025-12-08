import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import Login from './pages/Login';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Providers from './pages/Providers';
import Models from './pages/Models';
import Knowledge from './pages/Knowledge';
import UsageStats from './pages/UsageStats';

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
            <Route path="providers" element={<Providers />} />
            <Route path="models" element={<Models />} />
            <Route path="knowledge" element={<Knowledge />} />
            <Route path="usage" element={<UsageStats />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
