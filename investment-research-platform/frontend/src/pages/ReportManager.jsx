import { useState, useEffect, useRef } from 'react';
import { uploadReport, parseReport, getReports, deleteReport, downloadReportFile } from '../api';
import ErrorMessage from '../components/ErrorMessage';
import Loading from '../components/Loading';
import ConfirmDialog from '../components/ConfirmDialog';
import RatingTag from '../components/RatingTag';
import StatusTag from '../components/StatusTag';
import './ReportManager.css';

function formatTime(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now - date;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  let relative;
  if (minutes < 1) relative = '刚刚';
  else if (minutes < 60) relative = `${minutes}分钟前`;
  else if (hours < 24) relative = `${hours}小时前`;
  else if (days < 30) relative = `${days}天前`;
  else relative = date.toLocaleDateString('zh-CN');
  return { relative, full: date.toLocaleString('zh-CN') };
}

export default function ReportManager({ onNavigateToStock }) {
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ stock_code: '', industry: '', date_from: '', date_to: '' });
  const [deleteTarget, setDeleteTarget] = useState(null);
  const fileInputRef = useRef(null);

  const fetchReports = async (currentFilters) => {
    setLoading(true);
    setError(null);
    try {
      const f = currentFilters || filters;
      const activeFilters = {};
      if (f.stock_code) activeFilters.stock_code = f.stock_code;
      if (f.industry) activeFilters.industry = f.industry;
      if (f.date_from) activeFilters.date_from = f.date_from;
      if (f.date_to) activeFilters.date_to = f.date_to;
      const data = await getReports(activeFilters);
      setReports(data.reports || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('仅支持 PDF 格式文件');
      fileInputRef.current.value = '';
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError('文件大小不能超过 50MB');
      fileInputRef.current.value = '';
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const result = await uploadReport(file);
      await parseReport(result.report_id);
      await fetchReports();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      fileInputRef.current.value = '';
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteReport(deleteTarget);
      setDeleteTarget(null);
      if (selectedReport?.id === deleteTarget) setSelectedReport(null);
      await fetchReports();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDownload = async (reportId, filename) => {
    try {
      const blob = await downloadReportFile(reportId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'report.pdf';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleFilterChange = (key, value) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    fetchReports(newFilters);
  };

  return (
    <div className="report-manager">
      <ErrorMessage message={error} onClose={() => setError(null)} />

      {/* Upload Area */}
      <div className="card upload-area">
        <h2 className="card-title">上传研报</h2>
        <div className="upload-content">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleUpload}
            style={{ display: 'none' }}
          />
          <button
            className="btn btn-primary"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? '上传解析中...' : '选择 PDF 文件上传'}
          </button>
          <span className="text-secondary">支持 PDF 格式，最大 50MB</span>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="card">
        <div className="filter-bar">
          <input
            className="input"
            placeholder="股票代码"
            value={filters.stock_code}
            onChange={(e) => handleFilterChange('stock_code', e.target.value)}
          />
          <input
            className="input"
            placeholder="行业"
            value={filters.industry}
            onChange={(e) => handleFilterChange('industry', e.target.value)}
          />
          <input
            className="input"
            type="date"
            value={filters.date_from}
            onChange={(e) => handleFilterChange('date_from', e.target.value)}
          />
          <span className="text-secondary">至</span>
          <input
            className="input"
            type="date"
            value={filters.date_to}
            onChange={(e) => handleFilterChange('date_to', e.target.value)}
          />
        </div>
      </div>

      {/* Report List */}
      {loading ? (
        <Loading text="加载研报列表..." />
      ) : reports.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-text">暂无研报，请上传 PDF 研报</div>
        </div>
      ) : (
        <div className="report-list">
          {reports.map((report) => {
            const time = formatTime(report.upload_time);
            const isSelected = selectedReport?.id === report.id;
            return (
              <div
                key={report.id}
                className={`report-card card ${isSelected ? 'report-card-active' : ''}`}
                onClick={() => setSelectedReport(isSelected ? null : report)}
              >
                <div className="report-card-header">
                  <h3 className="report-card-title">{report.title || report.filename}</h3>
                  <StatusTag status={report.parse_status} />
                </div>
                <div className="report-card-tags">
                  {report.stock_code && (
                    <span
                      className="tag tag-blue link"
                      onClick={(e) => {
                        e.stopPropagation();
                        onNavigateToStock?.(report.stock_code);
                      }}
                    >
                      {report.stock_code} {report.stock_name}
                    </span>
                  )}
                  {report.industry && <span className="tag tag-gray">{report.industry}</span>}
                  {report.rating && <RatingTag rating={report.rating} />}
                </div>
                {report.target_price && (
                  <div className="report-card-price">
                    目标价：<strong>{report.target_price} 元</strong>
                  </div>
                )}
                <div className="report-card-footer">
                  <span className="text-secondary" title={time.full}>{time.relative}</span>
                  <div className="report-card-actions">
                    <button
                      className="btn btn-default btn-small"
                      onClick={(e) => { e.stopPropagation(); handleDownload(report.id, report.filename); }}
                    >
                      下载
                    </button>
                    <button
                      className="btn btn-danger btn-small"
                      onClick={(e) => { e.stopPropagation(); setDeleteTarget(report.id); }}
                    >
                      删除
                    </button>
                  </div>
                </div>

                {/* Expanded Detail */}
                {isSelected && report.parse_status === 'completed' && (
                  <div className="report-detail" onClick={(e) => e.stopPropagation()}>
                    <hr className="report-detail-divider" />
                    <h4 className="report-detail-title">{report.title}</h4>
                    <div className="report-detail-row">
                      <span>评级：</span><RatingTag rating={report.rating} />
                    </div>
                    {report.target_price && (
                      <div className="report-detail-row">
                        <span>目标价：</span><strong>{report.target_price} 元</strong>
                      </div>
                    )}
                    {report.stock_code && (
                      <div className="report-detail-row">
                        <span>股票：</span>
                        <span
                          className="link"
                          onClick={() => onNavigateToStock?.(report.stock_code)}
                        >
                          {report.stock_code} {report.stock_name}
                        </span>
                      </div>
                    )}
                    {report.key_points && (
                      <div className="report-detail-points">
                        <span className="report-detail-label">核心观点：</span>
                        <div className="report-detail-points-text">
                          {Array.isArray(report.key_points)
                            ? report.key_points.map((p, i) => <p key={i}>{p}</p>)
                            : <p>{report.key_points}</p>}
                        </div>
                      </div>
                    )}
                    {report.parse_time_ms && (
                      <div className="text-secondary">解析耗时：{report.parse_time_ms}ms</div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        visible={!!deleteTarget}
        title="删除研报"
        message="确认删除该研报？此操作不可撤销，关联的知识库数据也将被删除。"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
