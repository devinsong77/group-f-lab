import { useState, useEffect } from 'react';
import { getStocks, getStockDetail, getMarketData } from '../api';

export default function KnowledgeBase() {
  const [stocks, setStocks] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadStocks();
  }, []);

  const loadStocks = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getStocks();
      setStocks(data.stocks || []);
    } catch (e) {
      setError(e.message);
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
      // Load market data (non-blocking)
      try {
        const md = await getMarketData(stockCode);
        setMarketData(md);
      } catch {
        // Market data failure doesn't block page
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const filteredStocks = stocks.filter((s) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.stock_code.includes(q) ||
      s.stock_name.toLowerCase().includes(q) ||
      (s.industry || '').toLowerCase().includes(q)
    );
  });

  // Detail view
  if (selectedStock) {
    return (
      <div>
        <h2 className="section-header">知识库</h2>
        <span className="back-link" onClick={() => { setSelectedStock(null); setMarketData(null); }}>
          ← 返回股票列表
        </span>

        {error && <div className="error-msg">{error}</div>}

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <span className="tag tag-blue" style={{ fontSize: 16 }}>{selectedStock.stock_code}</span>
            <span style={{ fontSize: 20, fontWeight: 600 }}>{selectedStock.stock_name}</span>
            {selectedStock.industry && <span className="tag tag-gray">{selectedStock.industry}</span>}
            <span style={{ color: '#999' }}>共 {selectedStock.report_count} 份研报</span>
          </div>

          {/* Market data */}
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ marginBottom: 8 }}>行情数据</h3>
            {marketData ? (
              marketData.source === 'unavailable' ? (
                <div className="market-grid">
                  {['PE（市盈率）', 'PB（市净率）', '总市值（亿元）', '最新收盘价'].map((l) => (
                    <div className="market-item" key={l}>
                      <div className="market-label">{l}</div>
                      <div className="market-value" style={{ color: '#999' }}>暂无数据</div>
                    </div>
                  ))}
                </div>
              ) : (
                <>
                  <div className="market-grid">
                    <div className="market-item">
                      <div className="market-label">PE（市盈率）</div>
                      <div className="market-value">{marketData.pe ?? '暂无数据'}</div>
                    </div>
                    <div className="market-item">
                      <div className="market-label">PB（市净率）</div>
                      <div className="market-value">{marketData.pb ?? '暂无数据'}</div>
                    </div>
                    <div className="market-item">
                      <div className="market-label">总市值（亿元）</div>
                      <div className="market-value">{marketData.market_cap ?? '暂无数据'}</div>
                    </div>
                    <div className="market-item">
                      <div className="market-label">最新收盘价</div>
                      <div className="market-value">{marketData.latest_price ?? '暂无数据'}</div>
                    </div>
                  </div>
                  {marketData.source === 'cache' && marketData.data_time && (
                    <p style={{ color: '#999', fontSize: 12, marginTop: 8 }}>
                      数据更新于 {new Date(marketData.data_time).toLocaleString('zh-CN')}
                    </p>
                  )}
                </>
              )
            ) : (
              <div style={{ color: '#999' }}>加载行情数据中...</div>
            )}
          </div>

          {/* Summary */}
          {selectedStock.recent_summary && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 8 }}>最近观点汇总</h3>
              <div className="summary-text">{selectedStock.recent_summary}</div>
            </div>
          )}

          {/* Related reports */}
          <h3 style={{ marginBottom: 12 }}>关联研报</h3>
          {(selectedStock.reports || []).length === 0 ? (
            <div className="empty">暂无关联研报</div>
          ) : (
            selectedStock.reports.map((r) => (
              <div key={r.report_id} className="card" style={{ marginBottom: 8 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{r.title || '未命名'}</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {r.rating && <span className={`tag rating-${r.rating}`}>{r.rating}</span>}
                  {r.target_price != null && <span className="tag tag-gray">目标价: {r.target_price}元</span>}
                </div>
                {r.key_points && (
                  <p style={{ color: '#666', marginTop: 8, fontSize: 14 }}>{r.key_points}</p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    );
  }

  // List view
  return (
    <div>
      <h2 className="section-header">知识库</h2>

      {error && <div className="error-msg">{error}</div>}

      <div style={{ marginBottom: 16 }}>
        <input
          className="input"
          placeholder="搜索股票代码、名称或行业..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ width: '100%', maxWidth: 400 }}
        />
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : filteredStocks.length === 0 ? (
        <div className="empty">暂无知识库数据，请先上传并解析研报</div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          {filteredStocks.map((s) => (
            <div key={s.stock_code} className="stock-item" onClick={() => handleSelectStock(s.stock_code)}>
              <div className="stock-info">
                <div className="stock-name">
                  <span className="tag tag-blue">{s.stock_code}</span> {s.stock_name}
                </div>
                <div className="stock-meta">
                  {s.industry && <span>{s.industry}</span>}
                  {' · '}共 {s.report_count} 份研报
                  {s.latest_report_date && <span> · 最新: {new Date(s.latest_report_date).toLocaleDateString('zh-CN')}</span>}
                </div>
              </div>
              <span style={{ color: '#999', fontSize: 20 }}>→</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
