import { useState, useEffect, useRef } from 'react';
import {
  uploadReport,
  parseReport,
  getReports,
  deleteReport,
  downloadReportFile,
} from '../api';

function RatingTag({ rating }) {
  return <span className={`tag rating-${rating || '未提及'}`}>{rating || '未提及'}</span>;
}

function StatusTag({ status }) {
  const labels = { pending: '待解析', parsing: '解析中', completed: '已完成', failed: '失败' };
  return <span className={`tag status-${status}`}>{labels[status] || status}</span>;
}

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

export default function ReportManager() {
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({});
  const [deleteTarget, setDeleteTarget] = useState(null);
  const fileInputRef = useRef(null);

  const loadReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getReports(filters);
      setReports(data.reports || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadReports(); }, []);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const result = await uploadReport(file);
      try {
        await parseReport(result.report_id);
      } catch (parseErr) {
        setError(parseErr.message);
      }
      await loadReports();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteReport(deleteTarget);
      setDeleteTarget(null);
      setSelectedReport(null);
      await loadReports();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDownload = async (report) => {
    try {
      const blob = await downloadReportFile(report.report_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = report.filename || 'report.pdf';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <h2 className="section-header">📋 研报管理</h2>

      {/* Upload area */}
      <div
        className={`upload-area ${uploading ? 'uploading' : ''}`}
        onClick={() => !uploading && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          style={{ display: 'none' }}
          onChange={handleUpload}
        />
        {uploading ? (
          <div>
            <div className="spinner" />
            <p style={{ marginTop: 12, color: 'var(--xq-blue)' }}>正在上传并解析中...</p>
          </div>
        ) : (
          <div>
            <div className="upload-icon">📤</div>
            <div className="upload-title">点击上传研报 PDF</div>
            <div className="upload-hint">支持 PDF 格式，最大 50MB</div>
          </div>
        )}
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Filter bar */}
      <div className="filter-bar">
        <input
          className="input"
          placeholder="股票代码"
          value={filters.stock_code || ''}
          onChange={(e) => setFilters({ ...filters, stock_code: e.target.value })}
          style={{ width: 140 }}
        />
        <input
          className="input"
          placeholder="行业"
          value={filters.industry || ''}
          onChange={(e) => setFilters({ ...filters, industry: e.target.value })}
          style={{ width: 140 }}
        />
        <input
          className="input"
          type="date"
          value={filters.date_from || ''}
          onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
        />
        <span style={{ color: 'var(--xq-text-muted)' }}>至</span>
        <input
          className="input"
          type="date"
          value={filters.date_to || ''}
          onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
        />
        <button className="btn btn-primary btn-sm" onClick={loadReports}>筛选</button>
      </div>

      {/* Reports list */}
      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : reports.length === 0 ? (
        <div className="empty">暂无研报，请上传 PDF 文件开始分析</div>
      ) : (
        reports.map((r) => (
          <div
            key={r.report_id}
            className="card report-card"
            onClick={() => setSelectedReport(selectedReport?.report_id === r.report_id ? null : r)}
          >
            <div className="report-card-header">
              <span className="report-card-title">{r.title || r.filename || '未解析'}</span>
              <StatusTag status={r.parse_status} />
            </div>
            <div className="report-card-meta">
              {r.stock_code && (
                <span className="tag tag-blue">{r.stock_code} {r.stock_name}</span>
              )}
              {r.industry && <span className="tag tag-gray">{r.industry}</span>}
              {r.rating && <RatingTag rating={r.rating} />}
              {r.target_price != null && (
                <span className="tag tag-orange">目标价 {r.target_price}元</span>
              )}
            </div>
            <div className="report-card-time" title={r.upload_time}>
              {formatTime(r.upload_time)}
            </div>

            <div className="report-card-actions" onClick={(e) => e.stopPropagation()}>
              <button className="btn btn-ghost btn-sm" onClick={() => handleDownload(r)}>
                ⬇ 下载
              </button>
              <button className="btn btn-danger btn-sm" onClick={() => setDeleteTarget(r.report_id)}>
                🗑 删除
              </button>
            </div>

            {/* Detail panel */}
            {selectedReport?.report_id === r.report_id && r.parse_status === 'completed' && (
              <div className="detail-panel">
                <div className="detail-grid">
                  <div className="detail-field">
                    <div className="detail-label">标题</div>
                    <div className="detail-value" style={{ fontWeight: 600 }}>{r.title}</div>
                  </div>
                  <div className="detail-field">
                    <div className="detail-label">评级</div>
                    <div className="detail-value"><RatingTag rating={r.rating} /></div>
                  </div>
                  <div className="detail-field">
                    <div className="detail-label">目标价</div>
                    <div className="detail-value" style={{ fontSize: 18, fontWeight: 700, color: 'var(--xq-red)' }}>
                      {r.target_price != null ? `¥${r.target_price}` : '未提及'}
                    </div>
                  </div>
                  <div className="detail-field">
                    <div className="detail-label">解析耗时</div>
                    <div className="detail-value">{r.parse_time_ms}ms</div>
                  </div>
                </div>
                <div className="detail-field" style={{ marginTop: 16 }}>
                  <div className="detail-label">核心观点</div>
                  <div className="detail-value" style={{ lineHeight: 1.8 }}>{r.key_points}</div>
                </div>
              </div>
            )}
          </div>
        ))
      )}

      {/* Delete confirm dialog */}
      {deleteTarget && (
        <div className="dialog-overlay" onClick={() => setDeleteTarget(null)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <h3>⚠️ 确认删除</h3>
            <p>删除后将同时移除解析结果和知识库数据，此操作不可撤销。</p>
            <div className="dialog-actions">
              <button className="btn btn-default" onClick={() => setDeleteTarget(null)}>取消</button>
              <button className="btn btn-primary" style={{ background: 'var(--xq-red)' }} onClick={handleDelete}>确认删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
