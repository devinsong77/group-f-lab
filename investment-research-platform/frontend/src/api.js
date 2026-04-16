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
  AKSHARE_ERROR: '行情数据获取失败',
  SESSION_NOT_FOUND: '会话不存在或已被删除',
  QUESTION_EMPTY: '请输入问题内容',
  REPORTS_NOT_PARSED: '选中的研报尚未解析完成',
  REPORTS_NOT_FOUND: '选中的研报不存在',
  QA_FAILED: '问答生成失败，请稍后重试',
};

async function request(url, options = {}) {
  const resp = await fetch(`${API_BASE}${url}`, options);
  const data = await resp.json().catch(() => null);

  if (!resp.ok) {
    const code = data?.error?.code || 'UNKNOWN';
    const message = ERROR_MESSAGES[code] || data?.error?.message || '请求失败';
    const err = new Error(message);
    err.code = code;
    err.status = resp.status;
    throw err;
  }
  return data;
}

// ── Report APIs ──────────────────────────────────────────────

export async function uploadReport(file) {
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch(`${API_BASE}/reports/upload`, {
    method: 'POST',
    body: formData,
  });
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    const code = data?.error?.code || 'UNKNOWN';
    const message = ERROR_MESSAGES[code] || data?.error?.message || '上传失败';
    const err = new Error(message);
    err.code = code;
    throw err;
  }
  return data;
}

export async function parseReport(reportId) {
  return request(`/reports/${reportId}/parse`, { method: 'POST' });
}

export async function getReports(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params.append(k, v);
  });
  const qs = params.toString();
  return request(`/reports${qs ? `?${qs}` : ''}`);
}

export async function getReport(reportId) {
  return request(`/reports/${reportId}`);
}

export async function deleteReport(reportId) {
  return request(`/reports/${reportId}`, { method: 'DELETE' });
}

export async function downloadReportFile(reportId) {
  const resp = await fetch(`${API_BASE}/reports/${reportId}/file`);
  if (!resp.ok) throw new Error('下载失败');
  return resp.blob();
}

// ── Knowledge Base APIs ──────────────────────────────────────

export async function getStocks() {
  return request('/kb/stocks');
}

export async function getStockDetail(stockCode) {
  return request(`/kb/stocks/${stockCode}`);
}

export async function getStockReports(stockCode) {
  return request(`/kb/stocks/${stockCode}/reports`);
}

// ── Compare APIs ─────────────────────────────────────────────

export async function compareReports(reportIds) {
  return request('/reports/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_ids: reportIds }),
  });
}

// ── Market Data APIs ─────────────────────────────────────────

export async function getMarketData(stockCode) {
  return request(`/stocks/${stockCode}/market-data`);
}

// ── 研报问答 ─────────────────────────────────────────────

export async function createQASession(reportIds) {
  return request('/qa/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_ids: reportIds }),
  });
}

export async function getQASessions() {
  return request('/qa/sessions');
}

export async function getQASession(sessionId) {
  return request(`/qa/sessions/${sessionId}`);
}

export async function deleteQASession(sessionId) {
  return request(`/qa/sessions/${sessionId}`, { method: 'DELETE' });
}

export async function sendQAMessage(sessionId, question) {
  return request(`/qa/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
}

/**
 * 流式发送问答消息
 * @param {string} sessionId
 * @param {string} question
 * @param {object} callbacks - { onToken, onDone, onError, onReset }
 */
export async function sendQAMessageStream(sessionId, question, { onToken, onDone, onError, onReset }) {
  const resp = await fetch(`${API_BASE}/qa/sessions/${sessionId}/messages?stream=true`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify({ question }),
  });

  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    const code = data?.error?.code || 'UNKNOWN';
    const message = ERROR_MESSAGES[code] || data?.error?.message || '请求失败';
    throw new Error(message);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      try {
        const event = JSON.parse(jsonStr);
        switch (event.type) {
          case 'token':
            onToken?.(event.content);
            break;
          case 'done':
            onDone?.(event.message);
            break;
          case 'error':
            onError?.(event.message);
            break;
          case 'reset':
            onReset?.();
            break;
        }
      } catch (e) {
        // 忽略无法解析的行
      }
    }
  }
}
