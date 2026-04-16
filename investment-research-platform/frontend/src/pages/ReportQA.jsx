import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  getReports,
  createQASession,
  getQASessions,
  getQASession,
  deleteQASession,
  sendQAMessage,
} from '../api';
import { sendQAMessageStream } from '../api';

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
  return d.toLocaleDateString('zh-CN');
}

const SOURCE_TYPE_LABELS = {
  report_based: '基于研报',
  ai_generated: 'AI 生成',
  mixed: '综合分析',
};

export default function ReportQA() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [creating, setCreating] = useState(false);
  const [reports, setReports] = useState([]);
  const [selectedReportIds, setSelectedReportIds] = useState([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');
  const [expandedSources, setExpandedSources] = useState({});
  const [creatingSession, setCreatingSession] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const messagesEndRef = useRef(null);

  // 初始化加载会话列表
  useEffect(() => {
    loadSessions();
  }, []);

  // 错误自动消失
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(''), 3000);
    return () => clearTimeout(t);
  }, [error]);

  // 新消息自动滚动
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.messages, loading, streamingContent]);

  const loadSessions = async () => {
    try {
      const data = await getQASessions();
      setSessions(data.sessions || []);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleSelectSession = async (sessionId) => {
    setCreating(false);
    setActiveSessionId(sessionId);
    try {
      const data = await getQASession(sessionId);
      setActiveSession(data.session || data);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleNewSession = async () => {
    setCreating(true);
    setActiveSessionId(null);
    setActiveSession(null);
    setSelectedReportIds([]);
    try {
      const data = await getReports();
      const parsed = (data.reports || []).filter((r) => r.parse_status === 'completed');
      setReports(parsed);
    } catch (e) {
      setError(e.message);
    }
  };

  const toggleReportSelection = (reportId) => {
    setSelectedReportIds((prev) =>
      prev.includes(reportId) ? prev.filter((id) => id !== reportId) : [...prev, reportId]
    );
  };

  const handleCreateSession = async () => {
    if (selectedReportIds.length === 0) return;
    setCreatingSession(true);
    try {
      const data = await createQASession(selectedReportIds);
      const newId = data.session_id || data.session?.session_id;
      await loadSessions();
      if (newId) {
        await handleSelectSession(newId);
      }
      setCreating(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setCreatingSession(false);
    }
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    if (!window.confirm('确认删除该会话？删除后不可恢复。')) return;
    try {
      await deleteQASession(sessionId);
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setActiveSession(null);
      }
      await loadSessions();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleSend = async () => {
    const q = question.trim();
    if (!q || !activeSessionId || loading) return;

    setQuestion('');
    setLoading(true);
    setElapsed(0);
    setStreamingContent('');
    setError('');

    // 乐观添加用户消息
    setActiveSession((prev) => ({
      ...prev,
      messages: [...(prev?.messages || []), { role: 'user', content: q, timestamp: new Date().toISOString() }],
    }));

    const t0 = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);

    try {
      let displayContent = '';

      await sendQAMessageStream(activeSessionId, q, {
        onToken: (content) => {
          displayContent += content;
          // 过滤掉 <!--SOURCES_JSON--> 及之后的内容
          const markerIndex = displayContent.indexOf('<!--SOURCES_JSON-->');
          const visibleContent = markerIndex >= 0 ? displayContent.slice(0, markerIndex) : displayContent;
          setStreamingContent(visibleContent);
        },
        onDone: (message) => {
          setStreamingContent('');
          setActiveSession((prev) => ({
            ...prev,
            messages: [...(prev?.messages || []), message],
          }));
          loadSessions();
        },
        onError: (errMsg) => {
          setError(errMsg || '问答生成失败');
          setStreamingContent('');
        },
        onReset: () => {
          displayContent = '';
          setStreamingContent('');
        },
      });
    } catch (err) {
      setError(err.message || '发送失败');
      setStreamingContent('');
    } finally {
      clearInterval(timer);
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleSourceExpand = (idx) => {
    setExpandedSources((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  // ── 渲染 ──

  const renderSidebar = () => (
    <div className="qa-sidebar">
      <div className="qa-sidebar-header">
        <h3>会话列表</h3>
        <button className="qa-new-btn" onClick={handleNewSession}>+ 新建会话</button>
      </div>
      <div className="qa-session-list">
        {sessions.length === 0 ? (
          <div className="qa-empty-sessions">
            <p>暂无会话</p>
            <p style={{ fontSize: 12, marginTop: 4 }}>点击"新建会话"开始提问</p>
          </div>
        ) : (
          sessions.map((s) => (
            <div
              key={s.session_id}
              className={`qa-session-item ${activeSessionId === s.session_id ? 'active' : ''}`}
              onClick={() => handleSelectSession(s.session_id)}
            >
              <div className="qa-session-title">
                {s.title && s.title !== '新会话' ? s.title : '新会话'}
              </div>
              <div className="qa-session-meta">
                <span>{s.message_count || 0} 条消息 · {formatTime(s.updated_at || s.created_at)}</span>
                <button
                  className="qa-session-delete"
                  onClick={(e) => handleDeleteSession(e, s.session_id)}
                  title="删除会话"
                >
                  ✕
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );

  const renderWelcome = () => (
    <div className="qa-main">
      <div className="qa-welcome">
        <div className="qa-welcome-icon">💬</div>
        <h3>研报智能问答</h3>
        <p>选择左侧已有会话继续对话，或点击"新建会话"选择研报开始提问。AI 将基于研报内容为您提供专业解答，并标注引用来源。</p>
      </div>
    </div>
  );

  const renderCreatePanel = () => (
    <div className="qa-main">
      <div className="qa-create-panel">
        <h3>选择研报创建会话</h3>
        {reports.length === 0 ? (
          <div style={{ color: '#999', fontSize: 14 }}>暂无已解析的研报，请先上传并解析研报</div>
        ) : (
          <>
            <div className="qa-report-selector">
              {reports.map((r) => (
                <div
                  key={r.report_id}
                  className={`qa-report-option ${selectedReportIds.includes(r.report_id) ? 'selected' : ''}`}
                  onClick={() => toggleReportSelection(r.report_id)}
                >
                  <input
                    type="checkbox"
                    checked={selectedReportIds.includes(r.report_id)}
                    onChange={() => toggleReportSelection(r.report_id)}
                  />
                  <div className="qa-report-option-info">
                    <div className="qa-report-option-name">{r.title || r.filename || '未命名研报'}</div>
                    <div className="qa-report-option-detail">
                      {r.stock_code && `${r.stock_code} ${r.stock_name || ''}`}
                      {r.stock_code && r.industry ? ' · ' : ''}
                      {r.industry || ''}
                      {!r.stock_code && !r.industry ? '已解析' : ''}
                    </div>
                  </div>
                  <span className="tag tag-green" style={{ fontSize: 11 }}>已解析</span>
                </div>
              ))}
            </div>
            <button
              className="qa-create-btn"
              disabled={selectedReportIds.length === 0 || creatingSession}
              onClick={handleCreateSession}
            >
              {creatingSession ? '创建中...' : `创建会话 (${selectedReportIds.length}份研报)`}
            </button>
          </>
        )}
      </div>
    </div>
  );

  const renderChat = () => {
    const messages = activeSession?.messages || [];
    const reportTags = activeSession?.report_titles || activeSession?.reports || [];

    return (
      <div className="qa-main">
        {/* Header */}
        <div className="qa-main-header">
          <h3>{activeSession?.title && activeSession.title !== '新会话' ? activeSession.title : '研报问答'}</h3>
          <div className="qa-report-tags">
            {(Array.isArray(reportTags) ? reportTags : []).map((tag, i) => (
              <span key={i} className="qa-report-tag">
                📄 {typeof tag === 'string' ? tag : tag.title || tag.filename || '研报'}
              </span>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div className="qa-messages">
          {messages.length === 0 && !loading && (
            <div style={{ textAlign: 'center', color: '#bbb', padding: '60px 20px', fontSize: 14 }}>
              开始提问吧，AI 将基于研报内容为您解答
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`qa-message ${msg.role}`}>
              <div className="qa-message-bubble">
                {msg.role === 'assistant' ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                ) : (
                  msg.content
                )}
              </div>

              {msg.role === 'assistant' && (
                <>
                  {/* 来源标签 */}
                  {msg.source_type && (
                    <span className={`qa-source-type ${msg.source_type}`}>
                      {SOURCE_TYPE_LABELS[msg.source_type] || msg.source_type}
                    </span>
                  )}

                  {/* 溯源引用 */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="qa-sources">
                      <button
                        className="qa-sources-toggle"
                        onClick={() => toggleSourceExpand(idx)}
                      >
                        {expandedSources[idx] ? '▼' : '▶'} 查看引用来源 ({msg.sources.length})
                      </button>
                      {expandedSources[idx] && (
                        <div className="qa-source-list">
                          {msg.sources.map((src, si) => (
                            <div key={si} className="qa-source-item">
                              <div className="qa-source-item-title">
                                📄 {src.report_title || src.title || '研报'}
                              </div>
                              <div className="qa-source-item-quote">
                                "{src.quote || src.content || src.text || ''}"
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 耗时 */}
                  {msg.response_time_ms != null && (
                    <span className="qa-message-time">
                      耗时 {(msg.response_time_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                </>
              )}

              {msg.role === 'user' && msg.timestamp && (
                <span className="qa-message-time">{formatTime(msg.timestamp)}</span>
              )}
            </div>
          ))}

          {/* 流式输出中的实时显示 */}
          {loading && streamingContent && (
            <div className="qa-message assistant">
              <div className="qa-message-bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingContent}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* 加载中（等待首个 token） */}
          {loading && !streamingContent && (
            <div className="qa-loading">
              <div className="spinner" />
              <span>AI 正在思考...</span>
              <span className="qa-elapsed">{elapsed}s</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入区 */}
        <div className="qa-input-area">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            rows={1}
            disabled={loading}
          />
          <button
            className="qa-send-btn"
            disabled={!question.trim() || loading}
            onClick={handleSend}
          >
            {loading ? '发送中...' : '发送'}
          </button>
        </div>
      </div>
    );
  };

  // 右侧内容区分三种状态
  const renderMain = () => {
    if (creating) return renderCreatePanel();
    if (activeSession) return renderChat();
    return renderWelcome();
  };

  return (
    <div>
      <h2 className="section-header">💬 研报问答</h2>
      {error && <div className="error-msg">{error}</div>}
      <div className="qa-container">
        {renderSidebar()}
        {renderMain()}
      </div>
    </div>
  );
}
