import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Spin, Empty, Tag, Collapse, Switch, Tooltip } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, FileTextOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { chatAPI } from '../services/api';

const { TextArea } = Input;

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamMode, setStreamMode] = useState(true);
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendStream = async () => {
    if (!input.trim() || loading) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    const question = input;
    setInput('');
    setLoading(true);

    // 创建一个空的 assistant 消息，稍后更新
    const assistantMessageId = Date.now();
    const initialAssistantMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      sources: [],
      isStreaming: true
    };
    setMessages(prev => [...prev, initialAssistantMessage]);

    try {
      for await (const event of chatAPI.queryStream(question, 5, true)) {
        if (event.type === 'sources') {
          // 更新来源
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, sources: event.data }
                : msg
            )
          );
        } else if (event.type === 'chunk') {
          // 追加内容
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, content: msg.content + event.data }
                : msg
            )
          );
        } else if (event.type === 'done') {
          // 完成
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, isStreaming: false }
                : msg
            )
          );
        } else if (event.type === 'error') {
          // 错误
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, content: '错误：' + event.data, isError: true, isStreaming: false }
                : msg
            )
          );
        }
      }
    } catch (error) {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, content: '抱歉，发生了错误：' + error.message, isError: true, isStreaming: false }
            : msg
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSendNormal = async () => {
    if (!input.trim() || loading) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const { data } = await chatAPI.query(input, 5, true);

      const assistantMessage = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        retrieved_count: data.retrieved_count
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage = {
        role: 'assistant',
        content: '抱歉，发生了错误：' + (error.response?.data?.detail || error.message),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = () => {
    if (streamMode) {
      handleSendStream();
    } else {
      handleSendNormal();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearHistory = async () => {
    try {
      await chatAPI.clearHistory();
      setMessages([]);
    } catch (error) {
      console.error('清除历史失败:', error);
    }
  };

  return (
    <div style={{ height: 'calc(100vh - 110px)', display: 'flex', flexDirection: 'column' }}>
      {/* 消息区域 */}
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <span>知识库问答</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Tooltip title="流式输出可实时显示生成内容">
                <Switch
                  checkedChildren={<ThunderboltOutlined />}
                  unCheckedChildren="普通"
                  checked={streamMode}
                  onChange={setStreamMode}
                  size="small"
                />
              </Tooltip>
              {streamMode && <Tag color="blue" style={{ margin: 0 }}>流式模式</Tag>}
            </div>
          </div>
        }
        extra={
          <Button size="small" onClick={clearHistory} disabled={messages.length === 0}>
            清除对话
          </Button>
        }
        style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        styles={{ body: { flex: 1, overflow: 'auto', padding: '16px' } }}
      >
        {messages.length === 0 ? (
          <Empty
            image={<RobotOutlined style={{ fontSize: 64, color: '#1890ff' }} />}
            description="基于知识库的智能问答，输入问题开始对话"
            style={{ marginTop: 100 }}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {messages.map((msg, index) => (
              <div
                key={msg.id || index}
                style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    maxWidth: '80%',
                    padding: '12px 16px',
                    borderRadius: 12,
                    background: msg.role === 'user' ? '#1890ff' : (msg.isError ? '#fff2f0' : '#f5f5f5'),
                    color: msg.role === 'user' ? '#fff' : (msg.isError ? '#ff4d4f' : '#333'),
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    {msg.role === 'user' ? (
                      <UserOutlined />
                    ) : (
                      <RobotOutlined />
                    )}
                    <span style={{ fontWeight: 500 }}>
                      {msg.role === 'user' ? '你' : 'AI 助手'}
                    </span>
                    {msg.isStreaming && (
                      <Tag color="processing" style={{ marginLeft: 4 }}>
                        <Spin size="small" style={{ marginRight: 4 }} />
                        生成中...
                      </Tag>
                    )}
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                    {msg.content}
                    {msg.isStreaming && <span className="cursor-blink">|</span>}
                  </div>
                  {/* 显示来源 */}
                  {msg.sources && msg.sources.length > 0 && !msg.isStreaming && (
                    <Collapse
                      size="small"
                      style={{ marginTop: 12, background: 'rgba(0,0,0,0.02)' }}
                      items={[{
                        key: '1',
                        label: (
                          <span style={{ fontSize: 12 }}>
                            <FileTextOutlined /> 参考来源 ({msg.sources.length})
                          </span>
                        ),
                        children: (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {msg.sources.map((source, idx) => (
                              <div
                                key={idx}
                                style={{
                                  padding: 8,
                                  background: '#fff',
                                  borderRadius: 4,
                                  fontSize: 12,
                                  border: '1px solid #f0f0f0'
                                }}
                              >
                                <div style={{ fontWeight: 500, marginBottom: 4 }}>
                                  {source.file_path || source.title || '未命名'}
                                  {source.category && (
                                    <Tag size="small" style={{ marginLeft: 8 }}>{source.category}</Tag>
                                  )}
                                </div>
                                <div style={{ color: '#666' }}>
                                  {source.preview || source.content?.substring(0, 200)}...
                                </div>
                                {source.score && (
                                  <div style={{ color: '#999', marginTop: 4 }}>
                                    相关度: {(source.score * 100).toFixed(1)}%
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )
                      }]}
                    />
                  )}
                </div>
              </div>
            ))}
            {loading && !streamMode && (
              <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <div style={{ padding: '12px 16px', background: '#f5f5f5', borderRadius: 12 }}>
                  <Spin size="small" /> 思考中...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </Card>

      {/* 输入区域 */}
      <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
        <TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，按 Enter 发送，Shift+Enter 换行"
          autoSize={{ minRows: 1, maxRows: 4 }}
          style={{ flex: 1 }}
          disabled={loading}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading}
          style={{ height: 'auto' }}
        >
          发送
        </Button>
      </div>

      <style>{`
        .cursor-blink {
          animation: blink 1s step-end infinite;
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
