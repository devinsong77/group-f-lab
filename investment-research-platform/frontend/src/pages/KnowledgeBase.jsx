import { useState, useEffect } from 'react';
import { getStocks, getStockDetail, getMarketData } from '../api';
import ErrorMessage from '../components/ErrorMessage';
import Loading from '../components/Loading';
import RatingTag from '../components/RatingTag';
import './KnowledgeBase.css';

export default function KnowledgeBase({ initialStockCode, onNavigated }) {
  const [stocks, setStocks] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStocks();
  }, []);

  useEffect(() => {
    if (initialStockCode && stocks.length > 0) {
      handleSelectStock(initialStockCode);
      onNavigated?.();
    }
  }, [initialStockCode, stocks]);

  const fetchStocks = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getStocks();
      setStocks(data.stocks || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectStock = async (stockCode) => {
    setLoading(true);
    setError(null);
    setMarketData(null);
    try {
      const detail = await getStockDetail(stockCode);
      setSelectedStock(detail);
      // Load market data separately (degradation)
      try {
        const md = await getMarketData(stockCode);
        setMarketData(md);
      } catch {
        setMarketData({ source: 'unavailable' });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const filteredStocks = stocks.filter((s) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.stock_code?.toLowerCase().includes(q) ||
      s.stock_name?.toLowerCase().includes(q)
    );
  });

  if (loading && !selectedStock) {
    return <Loading text="加载知识库..." />;
  }

  // Stock detail view
  if (selectedStock) {
    return (
      <div className="knowledge-base">
        <ErrorMessage message={error} onClose={() => setError(null)} />
        <button className="btn btn-default" onClick={() => setSelectedStock(null)} style={{ marginBottom: 16 }}>
          &larr; 返回股票列表
        </button>

        {loading ? <Loading /> : (
          <>
            {/* Stock Overview */}
            <div className="card">
              <div className="stock-detail-header">
                <h2 className="stock-detail-name">
                  <span className="tag tag-blue">{selectedStock.stock_code}</span>
                  {selectedStock.stock_name}
                </h2>
                {selectedStock.industry && (
                  <span className="tag tag-gray">{selectedStock.industry}</span>
                )}
              </div>
            </div>

            {/* Market Data */}
            <div className="card">
              <h3 className="card-title">行情数据</h3>
              {!marketData ? (
                <Loading text="加载行情数据..." />
              ) : marketData.source === 'unavailable' ? (
                <div className="market-data-grid">
                  <div className="market-data-item">
                    <span className="market-data-label">PE</span>
                    <span className="market-data-value market-data-na">暂无数据</span>
                  </div>
                  <div className="market-data-item">
                    <span className="market-data-label">PB</span>
                    <span className="market-data-value market-data-na">暂无数据</span>
                  </div>
                  <div className="market-data-item">
                    <span className="market-data-label">市值</span>
                    <span className="market-data-value market-data-na">暂无数据</span>
                  </div>
                  <div className="market-data-item">
                    <span className="market-data-label">最新价</span>
                    <span className="market-data-value market-data-na">暂无数据</span>
                  </div>
                </div>
              ) : (
                <>
                  <div className="market-data-grid">
                    <div className="market-data-item">
                      <span className="market-data-label">PE</span>
                      <span className="market-data-value">{marketData.pe ?? '暂无数据'}</span>
                    </div>
                    <div className="market-data-item">
                      <span className="market-data-label">PB</span>
                      <span className="market-data-value">{marketData.pb ?? '暂无数据'}</span>
                    </div>
                    <div className="market-data-item">
                      <span className="market-data-label">市值</span>
                      <span className="market-data-value">
                        {marketData.market_cap ? `${(marketData.market_cap / 100000000).toFixed(2)} 亿` : '暂无数据'}
                      </span>
                    </div>
                    <div className="market-data-item">
                      <span className="market-data-label">最新价</span>
                      <span className="market-data-value">{marketData.latest_price ?? '暂无数据'}</span>
                    </div>
                  </div>
                  {marketData.source === 'cache' && marketData.data_time && (
                    <div className="text-secondary" style={{ marginTop: 8 }}>
                      数据更新于 {marketData.data_time}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Recent Summary */}
            {selectedStock.recent_summary && (
              <div className="card">
                <h3 className="card-title">最近观点汇总</h3>
                <div className="summary-text">{selectedStock.recent_summary}</div>
              </div>
            )}

            {/* Related Reports */}
            <div className="card">
              <h3 className="card-title">关联研报（{selectedStock.reports?.length || 0}份）</h3>
              {(!selectedStock.reports || selectedStock.reports.length === 0) ? (
                <div className="empty-state">
                  <div className="empty-state-text">暂无关联研报</div>
                </div>
              ) : (
                <div className="related-reports">
                  {selectedStock.reports.map((report) => (
                    <div key={report.id} className="related-report-item">
                      <div className="related-report-title">{report.title || report.filename}</div>
                      <div className="related-report-meta">
                        {report.rating && <RatingTag rating={report.rating} />}
                        {report.target_price && <span>目标价：{report.target_price}元</span>}
                        {report.upload_time && (
                          <span className="text-secondary">
                            {new Date(report.upload_time).toLocaleDateString('zh-CN')}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    );
  }

  // Stock list view
  return (
    <div className="knowledge-base">
      <ErrorMessage message={error} onClose={() => setError(null)} />

      <div className="card">
        <div className="filter-bar">
          <input
            className="input"
            placeholder="搜索股票代码或名称..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ flex: 1, maxWidth: 400 }}
          />
        </div>
      </div>

      {filteredStocks.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-text">
            {searchQuery ? '未找到匹配的股票' : '知识库暂无数据'}
          </div>
        </div>
      ) : (
        <div className="stock-list">
          {filteredStocks.map((stock) => (
            <div
              key={stock.stock_code}
              className="stock-item card"
              onClick={() => handleSelectStock(stock.stock_code)}
            >
              <div className="stock-item-header">
                <span className="tag tag-blue">{stock.stock_code}</span>
                <span className="stock-item-name">{stock.stock_name}</span>
                {stock.industry && <span className="tag tag-gray">{stock.industry}</span>}
              </div>
              <div className="stock-item-footer">
                <span className="text-secondary">共 {stock.report_count || 0} 份研报</span>
                {stock.latest_report_date && (
                  <span className="text-secondary">
                    最新：{new Date(stock.latest_report_date).toLocaleDateString('zh-CN')}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
