const API_BASE = '/api/v1';

const ERROR_MESSAGES = {
  INVALID_FILE_TYPE: '仅支持 PDF 格式文件',
  FILE_TOO_LARGE: '文件大小不能超过 50MB',
  PARSE_FAILED: '研报解析失败，请检查文件格式',
  LLM_ERROR: 'AI 服务暂时不可用，请稍后重试',
  REPORT_NOT_FOUND: '研报不存在或已被删除',
  STOCK_NOT_FOUND: '未找到该股票的知识库数据',
  COMPARE_MIN_REPORTS: '至少选择 2 份研报进行比对',
  COMPARE_DIFF_STOCK: '比对研报必须属于同一公司',
};

async function request(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, options);
  if (!res.ok) {
    let errorData;
    try {
      errorData = await res.json();
    } catch {
      throw new Error('请求失败，请稍后重试');
    }
    const code = errorData.error?.code || errorData.code;
    const message = ERROR_MESSAGES[code] || errorData.error?.message || errorData.message || '未知错误';
    throw new Error(message);
  }
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return res.json();
  }
  return res;
}

// === 研报管理 API ===
export async function uploadReport(file) {
  const formData = new FormData();
  formData.append('file', file);
  return request('/reports/upload', {
    method: 'POST',
    body: formData,
  });
}

export async function parseReport(reportId) {
  return request(`/reports/${reportId}/parse`, {
    method: 'POST',
  });
}

export async function getReports(filters = {}) {
  const params = new URLSearchParams();
  if (filters.stock_code) params.append('stock_code', filters.stock_code);
  if (filters.industry) params.append('industry', filters.industry);
  if (filters.date_from) params.append('date_from', filters.date_from);
  if (filters.date_to) params.append('date_to', filters.date_to);
  const query = params.toString();
  return request(`/reports${query ? `?${query}` : ''}`);
}

export async function getReport(reportId) {
  return request(`/reports/${reportId}`);
}

export async function deleteReport(reportId) {
  return request(`/reports/${reportId}`, {
    method: 'DELETE',
  });
}

export async function downloadReportFile(reportId) {
  const res = await fetch(`${API_BASE}/reports/${reportId}/file`);
  if (!res.ok) throw new Error('下载失败');
  return res.blob();
}

// === 知识库 API ===
export async function getStocks() {
  return request('/kb/stocks');
}

export async function getStockDetail(stockCode) {
  return request(`/kb/stocks/${stockCode}`);
}

export async function getStockReports(stockCode) {
  return request(`/kb/stocks/${stockCode}/reports`);
}

// === 比对 API ===
export async function compareReports(reportIds) {
  return request('/reports/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_ids: reportIds }),
  });
}

// === 行情数据 API ===
export async function getMarketData(stockCode) {
  return request(`/stocks/${stockCode}/market-data`);
}
