import { useState, useEffect } from 'react';
import { getStocks, getStockDetail, compareReports } from '../api';

function RatingTag({ rating }) {
  return <span className={`tag rating-${rating || '未提及'}`}>{rating || '未提及'}</span>;
}

export default function ReportCompare() {
  const [stocks, setStocks] = useState([]);
  const [selectedStockCode, setSelectedStockCode] = useState('');
  const [stockReports, setStockReports] = useState([]);
  const [compareReportIds, setCompareReportIds] = useState([]);
  const [compareResult, setCompareResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadStocks();
  }, []);

  const loadStocks = async () => {
    try {
      const data = await getStocks();
      setStocks(data.stocks || []);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleStockChange = async (code) => {
    setSelectedStockCode(code);
    setCompareReportIds([]);
    setCompareResult(null);
    setStockReports([]);
    if (!code) return;
    try {
      const detail = await getStockDetail(code);
      setStockReports(detail.reports || []);
    } catch (e) {
      setError(e.message);
    }
  };

  const toggleReport = (reportId) => {
    setCompareReportIds((prev) =>
      prev.includes(reportId)
        ? prev.filter((id) => id !== reportId)
        : [...prev, reportId]
    );
  };

  const handleCompare = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await compareReports(compareReportIds);
      setCompareResult(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="section-header">研报比对</h2>

      {error && <div className="error-msg">{error}</div>}

      {/* Stock selector */}
      <div className="card">
        <h3 style={{ marginBottom: 12 }}>选择股票</h3>
        <select
          className="select"
          value={selectedStockCode}
          onChange={(e) => handleStockChange(e.target.value)}
          style={{ width: '100%', maxWidth: 400 }}
        >
          <option value="">-- 请选择股票 --</option>
          {stocks.map((s) => (
            <option key={s.stock_code} value={s.stock_code}>
              {s.stock_code} {s.stock_name} ({s.report_count}份研报)
            </option>
          ))}
        </select>

        {/* Report selection */}
        {stockReports.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3 style={{ marginBottom: 8 }}>选择研报（至少2份）</h3>
            {stockReports.map((r) => (
              <label key={r.report_id} className="checkbox-item">
                <input
                  type="checkbox"
                  checked={compareReportIds.includes(r.report_id)}
                  onChange={() => toggleReport(r.report_id)}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500 }}>{r.title || '未命名'}</div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                    <RatingTag rating={r.rating} />
                    {r.target_price != null && (
                      <span className="tag tag-gray">目标价: {r.target_price}元</span>
                    )}
                  </div>
                </div>
              </label>
            ))}
            <div style={{ marginTop: 16 }}>
              <button
                className="btn btn-primary"
                disabled={compareReportIds.length < 2 || loading}
                onClick={handleCompare}
              >
                {loading ? '比对中...' : `开始比对 (${compareReportIds.length}份)`}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="loading">
          <div className="spinner" />
          <p style={{ marginTop: 12 }}>正在进行智能比对分析...</p>
        </div>
      )}

      {/* Compare result */}
      {compareResult && !loading && (
        <div style={{ marginTop: 24 }}>
          {/* Reports summary table */}
          <div className="card">
            <h3 style={{ marginBottom: 12 }}>基本信息对照表</h3>
            <div style={{ overflowX: 'auto' }}>
              <table className="compare-table">
                <thead>
                  <tr>
                    <th>字段</th>
                    {compareResult.reports_summary.map((r) => (
                      <th key={r.report_id}>{r.title || '研报'}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>评级</td>
                    {compareResult.reports_summary.map((r) => (
                      <td key={r.report_id}><RatingTag rating={r.rating} /></td>
                    ))}
                  </tr>
                  <tr>
                    <td>目标价</td>
                    {compareResult.reports_summary.map((r) => (
                      <td key={r.report_id}>{r.target_price != null ? `${r.target_price}元` : '未提及'}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>核心观点</td>
                    {compareResult.reports_summary.map((r) => (
                      <td key={r.report_id} style={{ fontSize: 13 }}>{r.key_points}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Similarities */}
          {compareResult.similarities.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: 12 }}>相似观点合并</h3>
              {compareResult.similarities.map((s, i) => (
                <div key={i} className="similarity-card">
                  <div className="similarity-topic">{s.topic}</div>
                  <p>{s.merged_view}</p>
                  {s.source_reports && (
                    <p style={{ color: '#999', fontSize: 12, marginTop: 8 }}>
                      来源: {s.source_reports.length}份研报
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Differences */}
          {compareResult.differences.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: 12 }}>差异高亮</h3>
              {compareResult.differences.map((d, i) => (
                <div key={i} className="difference-card">
                  <div className="difference-field">
                    {d.field === 'rating' ? '评级' : d.field === 'target_price' ? '目标价' : '核心观点'}
                  </div>
                  <p>{d.highlight}</p>
                  {d.field === 'rating' && d.values && (
                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                      {Object.entries(d.values).map(([rid, val]) => (
                        <RatingTag key={rid} rating={val} />
                      ))}
                    </div>
                  )}
                  {d.field === 'target_price' && d.values && (
                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                      {Object.entries(d.values).map(([rid, val]) => (
                        <span key={rid} className="tag tag-gray">
                          {val != null ? `${val}元` : '未提及'}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <p style={{ textAlign: 'center', color: '#999', fontSize: 13, marginTop: 16 }}>
            比对耗时: {compareResult.compare_time_ms}ms
          </p>
        </div>
      )}
    </div>
  );
}
