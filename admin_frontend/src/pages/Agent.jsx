import { useState, useRef, useEffect } from 'react';
import { Card, Input, Button, List, Typography, Tag, Collapse, Spin, message, Space, Tooltip } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, ClearOutlined, ThunderboltOutlined, ToolOutlined } from '@ant-design/icons';
import { agentAPI } from '../services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;
const { Panel } = Collapse;

export default function Agent() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await agentAPI.query(input.trim());
      const data = res.data;

      const agentMessage = {
        role: 'agent',
        content: data.answer || '抱歉，我无法处理这个请求。',
        success: data.success,
        iterations: data.iterations,
        thoughtProcess: data.thought_process || [],
        error: data.error,
        timestamp: new Date().toLocaleTimeString()
      };

      setMessages(prev => [...prev, agentMessage]);
    } catch (error) {
      const errorMessage = {
        role: 'agent',
        content: '请求失败: ' + (error.response?.data?.detail || error.message),
        success: false,
        error: true,
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, errorMessage]);
      message.error('Agent 请求失败');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const renderThoughtProcess = (thoughtProcess) => {
    if (!thoughtProcess || thoughtProcess.length === 0) return null;

    return (
      <Collapse size="small" ghost style={{ marginTop: 8 }}>
        <Panel
          header={
            <Space>
              <ThunderboltOutlined />
              <Text type="secondary">思考过程 ({thoughtProcess.length} 步)</Text>
            </Space>
          }
          key="thought"
        >
          <List
            size="small"
            dataSource={thoughtProcess}
            renderItem={(item, index) => (
              <List.Item style={{ padding: '8px 0', borderBottom: '1px dashed #f0f0f0' }}>
                <div style={{ width: '100%' }}>
                  <div style={{ marginBottom: 4 }}>
                    <Tag color="blue">步骤 {index + 1}</Tag>
                    {item.tool_calls && item.tool_calls.length > 0 && (
                      <Tag color="orange" icon={<ToolOutlined />}>
                        {item.tool_calls.map(t => t.tool_name || t).join(', ')}
                      </Tag>
                    )}
                  </div>
                  <Paragraph
                    style={{ margin: 0, fontSize: 12 }}
                    ellipsis={{ rows: 3, expandable: true }}
                  >
                    <Text type="secondary">思考: </Text>
                    {item.thought}
                  </Paragraph>
                  {item.observation && (
                    <Paragraph
                      style={{ margin: '4px 0 0 0', fontSize: 12 }}
                      ellipsis={{ rows: 2, expandable: true }}
                    >
                      <Text type="secondary">观察: </Text>
                      <Text code>{item.observation.substring(0, 200)}{item.observation.length > 200 ? '...' : ''}</Text>
                    </Paragraph>
                  )}
                </div>
              </List.Item>
            )}
          />
        </Panel>
      </Collapse>
    );
  };

  const renderMessage = (msg, index) => {
    const isUser = msg.role === 'user';

    return (
      <div
        key={index}
        style={{
          display: 'flex',
          justifyContent: isUser ? 'flex-end' : 'flex-start',
          marginBottom: 16
        }}
      >
        <div
          style={{
            maxWidth: '80%',
            display: 'flex',
            flexDirection: isUser ? 'row-reverse' : 'row',
            alignItems: 'flex-start',
            gap: 8
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: '50%',
              background: isUser ? '#1890ff' : '#52c41a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0
            }}
          >
            {isUser ? (
              <UserOutlined style={{ color: '#fff', fontSize: 18 }} />
            ) : (
              <RobotOutlined style={{ color: '#fff', fontSize: 18 }} />
            )}
          </div>
          <div
            style={{
              background: isUser ? '#1890ff' : '#f5f5f5',
              color: isUser ? '#fff' : '#000',
              padding: '12px 16px',
              borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
              minWidth: 60
            }}
          >
            <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {msg.content}
            </div>
            {!isUser && (
              <>
                <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {msg.success !== undefined && (
                    <Tag color={msg.success ? 'success' : 'error'}>
                      {msg.success ? '成功' : '失败'}
                    </Tag>
                  )}
                  {msg.iterations && (
                    <Tag color="blue">迭代: {msg.iterations}</Tag>
                  )}
                </div>
                {renderThoughtProcess(msg.thoughtProcess)}
              </>
            )}
            <div style={{
              fontSize: 11,
              marginTop: 6,
              opacity: 0.7,
              textAlign: isUser ? 'left' : 'right'
            }}>
              {msg.timestamp}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div style={{ height: 'calc(100vh - 180px)', display: 'flex', flexDirection: 'column' }}>
      <Card
        title={
          <Space>
            <RobotOutlined />
            <span>智能 Agent</span>
            <Tag color="green">在线</Tag>
          </Space>
        }
        extra={
          <Tooltip title="清空对话">
            <Button
              icon={<ClearOutlined />}
              onClick={handleClear}
              disabled={messages.length === 0}
            >
              清空
            </Button>
          </Tooltip>
        }
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: 0 }}
      >
        {/* 功能说明 */}
        <div style={{ padding: '12px 16px', background: '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
          <Text type="secondary" style={{ fontSize: 13 }}>
            Agent 可以使用以下工具为你服务：
          </Text>
          <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Tag icon={<ToolOutlined />} color="blue">calculator 计算器</Tag>
            <Tag icon={<ToolOutlined />} color="green">search 知识搜索</Tag>
            <Tag icon={<ToolOutlined />} color="orange">web_search 网页搜索</Tag>
            <Tag icon={<ToolOutlined />} color="purple">datetime 日期时间</Tag>
            <Tag icon={<ToolOutlined />} color="cyan">code_executor 代码执行</Tag>
            <Tag icon={<ToolOutlined />} color="magenta">json JSON处理</Tag>
          </div>
        </div>

        {/* 消息列表 */}
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            padding: 16,
            background: '#fff'
          }}
        >
          {messages.length === 0 ? (
            <div style={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexDirection: 'column',
              color: '#999'
            }}>
              <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
              <Text type="secondary">开始与 Agent 对话吧！</Text>
              <Text type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
                试试问："计算 1234 * 5678" 或 "搜索项目的配置方法"
              </Text>
            </div>
          ) : (
            <>
              {messages.map(renderMessage)}
              {loading && (
                <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: '50%',
                        background: '#52c41a',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                    >
                      <RobotOutlined style={{ color: '#fff', fontSize: 18 }} />
                    </div>
                    <div style={{ background: '#f5f5f5', padding: '12px 16px', borderRadius: '16px 16px 16px 4px' }}>
                      <Spin size="small" /> <Text type="secondary">思考中...</Text>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div style={{ padding: 16, borderTop: '1px solid #f0f0f0', background: '#fafafa' }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <TextArea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入你的问题... (按 Enter 发送，Shift+Enter 换行)"
              autoSize={{ minRows: 1, maxRows: 4 }}
              disabled={loading}
              style={{ flex: 1 }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={loading}
              disabled={!input.trim()}
              style={{ height: 'auto', minHeight: 32 }}
            >
              发送
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
