import { useState, useRef, useEffect, useMemo } from 'react';
import { Input, Button, Card, Spin, Empty, Tag, Collapse, Switch, Tooltip, Popover, Select } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, FileTextOutlined, ThunderboltOutlined, LinkOutlined, FolderOutlined } from '@ant-design/icons';
import { chatAPI, groupAPI } from '../services/api';

const { TextArea } = Input;

/**
 * 渲染带引用高亮的回答内容
 * 将 Markdown 格式的引用标记 **text**[^n] 转换为可点击的高亮元素
 */
const HighlightedAnswer = ({ content, highlights, sources, onSourceClick }) => {
  // 如果没有高亮信息，直接显示原文
  if (!highlights || !highlights.highlighted_answer) {
    return <span style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{content}</span>;
  }

  const highlightedAnswer = highlights.highlighted_answer;
  const sourceCitations = highlights.source_citations || {};

  // 解析高亮标记: **text**[^n] 格式
  const parseHighlights = (text) => {
    const regex = /\*\*(.+?)\*\*\[\^(\d+)\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      // 添加匹配前的普通文本
      if (match.index > lastIndex) {
        parts.push({
          type: 'text',
          content: text.slice(lastIndex, match.index)
        });
      }
      // 添加高亮部分
      parts.push({
        type: 'highlight',
        content: match[1],
        sourceIndex: parseInt(match[2]) - 1  // 转为 0-based 索引
      });
      lastIndex = match.index + match[0].length;
    }
    // 添加剩余文本
    if (lastIndex < text.length) {
      parts.push({
        type: 'text',
        content: text.slice(lastIndex)
      });
    }
    return parts;
  };

  const parts = useMemo(() => parseHighlights(highlightedAnswer), [highlightedAnswer]);

  return (
    <span style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
      {parts.map((part, idx) => {
        if (part.type === 'text') {
          return <span key={idx}>{part.content}</span>;
        }
        // 高亮引用
        const source = sources?.[part.sourceIndex];
        const popoverContent = source ? (
          <div style={{ maxWidth: 300, fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>
              {source.file_path || source.title || '来源 ' + (part.sourceIndex + 1)}
            </div>
            <div style={{ color: '#666' }}>
              {source.preview?.slice(0, 150) || source.content?.slice(0, 150)}...
            </div>
            {source.score && (
              <div style={{ color: '#1890ff', marginTop: 4 }}>
                相关度: {(source.score * 100).toFixed(1)}%
              </div>
            )}
          </div>
        ) : null;

        return (
          <Popover key={idx} content={popoverContent} title={null} trigger="hover">
            <span
              className="highlight-citation"
              onClick={() => onSourceClick?.(part.sourceIndex)}
              style={{
                backgroundColor: 'rgba(24, 144, 255, 0.15)',
                borderBottom: '2px solid #1890ff',
                padding: '0 2px',
                borderRadius: 2,
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
            >
              {part.content}
              <sup style={{ color: '#1890ff', marginLeft: 1 }}>[{part.sourceIndex + 1}]</sup>
            </span>
          </Popover>
        );
      })}
    </span>
  );
};

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamMode, setStreamMode] = useState(true);
  const [activeSourceIndex, setActiveSourceIndex] = useState(null);  // 当前高亮的来源索引
  const [groups, setGroups] = useState([]);  // 知识分组列表
  const [selectedGroupNames, setSelectedGroupNames] = useState([]);  // 选中的分组名称
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  const sourceRefs = useRef({});  // 来源元素的引用

  // 加载分组列表
  useEffect(() => {
    const loadGroups = async () => {
      try {
        const { data } = await groupAPI.list(false);
        setGroups(data.items || []);
      } catch (error) {
        console.error('加载分组失败:', error);
      }
    };
    loadGroups();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 点击引用高亮时滚动到对应来源
  const handleSourceClick = (messageId, sourceIndex) => {
    setActiveSourceIndex({ messageId, sourceIndex });
    // 自动展开来源折叠面板并滚动
    const refKey = `${messageId}-${sourceIndex}`;
    const sourceElement = sourceRefs.current[refKey];
    if (sourceElement) {
      sourceElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // 闪烁高亮效果
      sourceElement.classList.add('source-highlight-active');
      setTimeout(() => {
        sourceElement.classList.remove('source-highlight-active');
        setActiveSourceIndex(null);
      }, 2000);
    }
  };

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
      const groupNames = selectedGroupNames.length > 0 ? selectedGroupNames : null;
      for await (const event of chatAPI.queryStream(question, 5, true, groupNames)) {
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
      const groupNames = selectedGroupNames.length > 0 ? selectedGroupNames : null;
      const { data } = await chatAPI.query(input, 5, true, groupNames);

      const assistantMessage = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        retrieved_count: data.retrieved_count,
        highlights: data.highlights  // 添加引用高亮信息
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
    if (e.nativeEvent.isComposing) return;
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
              <Tooltip title="选择知识分组，仅在选定分组中检索">
                <Select
                  mode="multiple"
                  allowClear
                  placeholder="全部知识"
                  value={selectedGroupNames}
                  onChange={setSelectedGroupNames}
                  style={{ minWidth: 150, maxWidth: 300 }}
                  size="small"
                  maxTagCount={2}
                  suffixIcon={<FolderOutlined />}
                >
                  {groups.map(g => (
                    <Select.Option key={g.id} value={g.name}>
                      <span style={{ color: g.color }}>●</span> {g.name}
                    </Select.Option>
                  ))}
                </Select>
              </Tooltip>
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
              {selectedGroupNames.length > 0 && (
                <Tag color="green" style={{ margin: 0 }}>
                  <FolderOutlined /> 已选 {selectedGroupNames.length} 个分组
                </Tag>
              )}
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
                    {msg.role === 'assistant' && !msg.isStreaming && msg.highlights ? (
                      <HighlightedAnswer
                        content={msg.content}
                        highlights={msg.highlights}
                        sources={msg.sources}
                        onSourceClick={(sourceIndex) => handleSourceClick(msg.id || index, sourceIndex)}
                      />
                    ) : (
                      <>
                        {msg.content}
                        {msg.isStreaming && <span className="cursor-blink">|</span>}
                      </>
                    )}
                  </div>
                  {/* 显示来源 */}
                  {msg.sources && msg.sources.length > 0 && !msg.isStreaming && (
                    <Collapse
                      size="small"
                      style={{ marginTop: 12, background: 'rgba(0,0,0,0.02)' }}
                      defaultActiveKey={activeSourceIndex?.messageId === (msg.id || index) ? ['1'] : []}
                      items={[{
                        key: '1',
                        label: (
                          <span style={{ fontSize: 12 }}>
                            <FileTextOutlined /> 参考来源 ({msg.sources.length})
                            {msg.highlights?.source_citations && Object.keys(msg.highlights.source_citations).length > 0 && (
                              <Tag color="blue" size="small" style={{ marginLeft: 8 }}>
                                <LinkOutlined /> 有引用标记
                              </Tag>
                            )}
                          </span>
                        ),
                        children: (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {msg.sources.map((source, idx) => (
                              <div
                                key={idx}
                                ref={(el) => {
                                  const refKey = `${msg.id || index}-${idx}`;
                                  sourceRefs.current[refKey] = el;
                                }}
                                className={`source-item ${
                                  activeSourceIndex?.messageId === (msg.id || index) &&
                                  activeSourceIndex?.sourceIndex === idx
                                    ? 'source-highlight-active'
                                    : ''
                                }`}
                                style={{
                                  padding: 8,
                                  background: '#fff',
                                  borderRadius: 4,
                                  fontSize: 12,
                                  border: msg.highlights?.source_citations?.[idx]
                                    ? '2px solid #1890ff'
                                    : '1px solid #f0f0f0',
                                  transition: 'all 0.3s'
                                }}
                              >
                                <div style={{ fontWeight: 500, marginBottom: 4 }}>
                                  <span style={{ marginRight: 8 }}>[{idx + 1}]</span>
                                  {source.file_path || source.title || '未命名'}
                                  {source.category && (
                                    <Tag size="small" style={{ marginLeft: 8 }}>{source.category}</Tag>
                                  )}
                                  {msg.highlights?.source_citations?.[idx] && (
                                    <Tag color="blue" size="small" style={{ marginLeft: 4 }}>
                                      被引用 {msg.highlights.source_citations[idx]} 次
                                    </Tag>
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
        .highlight-citation:hover {
          background-color: rgba(24, 144, 255, 0.3) !important;
        }
        .source-item {
          transition: all 0.3s ease;
        }
        .source-highlight-active {
          background-color: rgba(24, 144, 255, 0.15) !important;
          border-color: #1890ff !important;
          box-shadow: 0 0 8px rgba(24, 144, 255, 0.4);
          animation: pulse 0.5s ease-in-out 2;
        }
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 8px rgba(24, 144, 255, 0.4); }
          50% { box-shadow: 0 0 16px rgba(24, 144, 255, 0.8); }
        }
      `}</style>
    </div>
  );
}
