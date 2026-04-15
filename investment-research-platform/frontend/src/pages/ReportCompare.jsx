import { useState, useEffect } from 'react';
import { getStocks, getStockDetail, compareReports } from '../api';
import ErrorMessage from '../components/ErrorMessage';
import Loading from '../components/Loading';
import RatingTag from '../components/RatingTag';
import './ReportCompare.css';

export default function ReportCompare() {
  const [stocks, setStocks] = useState([]);
  const [selectedStockCode, setSelectedStockCode] = useState('');
  const [stockReports, setStockReports] = useState([]);
  const [compareReportIds, setCompareReportIds] = useState([]);
  const [compareResult, setCompareResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingReports, setLoadingReports] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStocks();
  }, []);

  const fetchStocks = async () => {
    try {
      const data = await getStocks();
      setStocks(data.stocks || []);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleStockChange = async (stockCode) => {
    setSelectedStockCode(stockCode);
    setCompareReportIds([]);
    setCompareResult(null);
    setStockReports([]);
    if (!stockCode) return;
    setLoadingReports(true);
    setError(null);
    try {
      const detail = await getStockDetail(stockCode);
      setStockReports(detail.reports || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingReports(false);
    }
  };

  const handleToggleReport = (reportId) => {
    setCompareReportIds((prev) =>
      prev.includes(reportId)
        ? prev.filter((id) => id !== reportId)
        : [...prev, reportId]
    );
  };

  const handleCompare = async () => {
    if (compareReportIds.length < 2) return;
    setLoading(true);
    setError(null);
    setCompareResult(null);
    try {
      const result = await compareReports(compareReportIds);
      setCompareResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const calcPriceDiffPercent = (prices) => {
    const nums = prices.filter((p) => p != null).map(Number);
    if (nums.length < 2) return null;
    const max = Math.max(...nums);
    const min = Math.min(...nums);
    if (min === 0) return null;
    return (((max - min) / min) * 100).toFixed(1);
  };

  return (
    <div className="report-compare">
      <ErrorMessage message={error} onClose={() => setError(null)} />

      {/* Stock & Report Selection */}
      <div className="card">
        <h2 className="card-title">选择比对研报</h2>
        <div className="compare-select-area">
          <div className="compare-stock-select">
            <label className="compare-label">选择股票：</label>
            <select
              className="select"
              value={selectedStockCode}
              onChange={(e) => handleStockChange(e.target.value)}
            >
              <option value="">请选择股票</option>
              {stocks.map((s) => (
                <option key={s.stock_code} value={s.stock_code}>
                  {s.stock_code} {s.stock_name}
                </option>
              ))}
            </select>
          </div>

          {loadingReports && <Loading text="加载研报列表..." />}

          {stockReports.length > 0 && (
            <div className="compare-report-list">
              <label className="compare-label">选择研报（至少选2份）：</label>
              {stockReports.map((report) => (
                <label key={report.id} className="compare-report-item">
                  <input
                    type="checkbox"
                    checked={compareReportIds.includes(report.id)}
                    onChange={() => handleToggleReport(report.id)}
                  />
                  <div className="compare-report-info">
                    <span className="compare-report-title">{report.title || report.filename}</span>
                    <span className="compare-report-meta">
                      {report.rating && <RatingTag rating={report.rating} />}
                      {report.upload_time && (
                        <span className="text-secondary">
                          {new Date(report.upload_time).toLocaleDateString('zh-CN')}
                        </span>
                      )}
                    </span>
                  </div>
                </label>
              ))}
            </div>
          )}

          {selectedStockCode && !loadingReports && stockReports.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-text">该股票暂无研报</div>
            </div>
          )}

          <button
            className="btn btn-primary"
            disabled={compareReportIds.length < 2 || loading}
            onClick={handleCompare}
            style={{ marginTop: 16 }}
          >
            {loading ? '比对中...' : '开始比对'}
          </button>
        </div>
      </div>

      {/* Compare Loading */}
      {loading && <Loading text="正在比对研报，请稍候..." />}

      {/* Compare Results */}
      {compareResult && (
        <div className="compare-results">
          {/* Basic Info Comparison Table */}
          {compareResult.reports_summary && compareResult.reports_summary.length > 0 && (
            <div className="card">
              <h3 className="card-title">基本信息对照</h3>
              <div className="compare-table-wrapper">
                <table className="compare-table">
                  <thead>
                    <tr>
                      <th>字段</th>
                      {compareResult.reports_summary.map((r, i) => (
                        <th key={i}>研报 {i + 1}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>标题</td>
                      {compareResult.reports_summary.map((r, i) => (
                        <td key={i}>{r.title}</td>
                      ))}
                    </tr>
                    <tr>
                      <td>评级</td>
                      {compareResult.reports_summary.map((r, i) => (
                        <td key={i}><RatingTag rating={r.rating} /></td>
                      ))}
                    </tr>
                    <tr>
                      <td>目标价</td>
                      {compareResult.reports_summary.map((r, i) => (
                        <td key={i}>{r.target_price ? `${r.target_price} 元` : '-'}</td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Similarities */}
          {compareResult.similarities && compareResult.similarities.length > 0 && (
            <div className="card">
              <h3 className="card-title">相似观点</h3>
              <div className="similarity-list">
                {compareResult.similarities.map((item, i) => (
                  <div key={i} className="similarity-card">
                    {item.topic && <h4 className="similarity-topic">{item.topic}</h4>}
                    <p className="similarity-desc">{item.description || item.content}</p>
                    {item.sources && (
                      <div className="text-secondary">来源：{item.sources.join('、')}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Differences */}
          {compareResult.differences && compareResult.differences.length > 0 && (
            <div className="card">
              <h3 className="card-title">差异对比</h3>
              <div className="diff-list">
                {compareResult.differences.map((diff, i) => (
                  <div key={i} className="diff-card">
                    <div className="diff-field">{diff.field}</div>
                    <div className="diff-values">
                      {diff.values?.map((val, j) => (
                        <div key={j} className="diff-value-item">
                          <span className="diff-value-label">研报 {j + 1}：</span>
                          <span className={`diff-value-content ${
                            diff.field === 'key_points' ? 'highlight-yellow' : ''
                          }`}>
                            {diff.field === 'rating' ? (
                              <RatingTag rating={val} />
                            ) : diff.field === 'target_price' ? (
                              <strong>{val} 元</strong>
                            ) : (
                              val
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                    {diff.field === 'target_price' && diff.values && (
                      (() => {
                        const pct = calcPriceDiffPercent(diff.values);
                        return pct ? (
                          <div className="diff-percent highlight-red">差距 {pct}%</div>
                        ) : null;
                      })()
                    )}
                    {diff.description && (
                      <div className="diff-description text-secondary">{diff.description}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
