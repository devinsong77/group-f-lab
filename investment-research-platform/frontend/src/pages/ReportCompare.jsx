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
  const [elapsed, setElapsed] = useState(0);
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
    setElapsed(0);
    setError(null);
    const t0 = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
    try {
      const result = await compareReports(compareReportIds);
      setCompareResult(result);
    } catch (e) {
      setError(e.message);
    } finally {
      clearInterval(timer);
      setLoading(false);
    }
  };

  const currentStep = !selectedStockCode ? 1 : stockReports.length === 0 ? 1 : compareResult ? 3 : 2;

  return (
    <div>
      <h2 className="section-header">⚖️ 研报比对</h2>

      {/* Step indicator */}
      <div className="step-indicator">
        <div className={`step ${currentStep >= 1 ? 'active' : ''} ${currentStep > 1 ? 'done' : ''}`}>
          <span className="step-num">1</span> 选择股票
        </div>
        <div className={`step ${currentStep >= 2 ? 'active' : ''} ${currentStep > 2 ? 'done' : ''}`}>
          <span className="step-num">2</span> 选择研报
        </div>
        <div className={`step ${currentStep >= 3 ? 'active' : ''}`}>
          <span className="step-num">3</span> 查看结果
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Stock selector */}
      <div className="card">
        <div className="card-title">选择股票</div>
        <select
          className="select"
          value={selectedStockCode}
          onChange={(e) => handleStockChange(e.target.value)}
          style={{ width: '100%', maxWidth: 420 }}
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
          <div style={{ marginTop: 20 }}>
            <div className="card-title">选择研报（至少2份）</div>
            <div style={{ border: '1px solid var(--xq-border)', borderRadius: 'var(--xq-radius)', overflow: 'hidden' }}>
              {stockReports.map((r) => (
                <label key={r.report_id} className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={compareReportIds.includes(r.report_id)}
                    onChange={() => toggleReport(r.report_id)}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, fontSize: 14 }}>{r.title || '未命名'}</div>
                    <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                      <RatingTag rating={r.rating} />
                      {r.target_price != null && (
                        <span className="tag tag-orange">目标价 ¥{r.target_price}</span>
                      )}
                    </div>
                  </div>
                </label>
              ))}
            </div>
            <div style={{ marginTop: 16 }}>
              <button
                className="btn btn-primary"
                disabled={compareReportIds.length < 2 || loading}
                onClick={handleCompare}
                style={{ minWidth: 160 }}
              >
                {loading ? `AI 分析中... (${elapsed}s)` : `开始比对 (${compareReportIds.length}份)`}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="loading">
          <div className="spinner" />
          <p style={{ marginTop: 12, fontSize: 14 }}>正在进行 AI 语义比对分析，请稍候... ({elapsed}s)</p>
        </div>
      )}

      {/* Compare result */}
      {compareResult && !loading && (
        <div style={{ marginTop: 20 }}>
          {/* Reports summary table */}
          <div className="card">
            <div className="card-title">基本信息对照表</div>
            <div style={{ overflowX: 'auto' }}>
              <table className="compare-table">
                <thead>
                  <tr>
                    <th style={{ width: 100 }}>字段</th>
                    {compareResult.reports_summary.map((r) => (
                      <th key={r.report_id}>{r.title || '研报'}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td style={{ fontWeight: 600 }}>评级</td>
                    {compareResult.reports_summary.map((r) => (
                      <td key={r.report_id}><RatingTag rating={r.rating} /></td>
                    ))}
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>目标价</td>
                    {compareResult.reports_summary.map((r) => (
                      <td key={r.report_id} style={{ fontWeight: 700, color: r.target_price != null ? 'var(--xq-red)' : 'var(--xq-text-muted)' }}>
                        {r.target_price != null ? `¥${r.target_price}` : '未提及'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>核心观点</td>
                    {compareResult.reports_summary.map((r) => (
                      <td key={r.report_id} style={{ fontSize: 13, lineHeight: 1.7, color: '#555' }}>{r.key_points}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Similarities */}
          {compareResult.similarities.length > 0 && (
            <div className="card">
              <div className="card-title">✅ 相似观点合并</div>
              {compareResult.similarities.map((s, i) => (
                <div key={i} className="similarity-card">
                  <div className="similarity-topic">{s.topic}</div>
                  <p style={{ fontSize: 14, lineHeight: 1.7, color: '#444' }}>{s.merged_view}</p>
                  {s.source_reports && (
                    <p style={{ color: 'var(--xq-text-muted)', fontSize: 12, marginTop: 8 }}>
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
              <div className="card-title">⚡ 差异高亮</div>
              {compareResult.differences.map((d, i) => (
                <div key={i} className="difference-card">
                  <div className="difference-field">
                    {d.field === 'rating' ? '评级' : d.field === 'target_price' ? '目标价' : '核心观点'}
                  </div>
                  <p style={{ fontSize: 14, lineHeight: 1.7, color: '#555' }}>{d.highlight}</p>
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
                        <span key={rid} className="tag tag-orange">
                          {val != null ? `¥${val}` : '未提及'}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <p style={{ textAlign: 'center', color: 'var(--xq-text-muted)', fontSize: 13, marginTop: 16 }}>
            比对耗时 {compareResult.compare_time_ms}ms{compareResult.from_cache ? ' · 缓存命中' : ''}
          </p>
        </div>
      )}
    </div>
  );
}
