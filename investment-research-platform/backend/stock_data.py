"""StockDataService — Multi-source market data with caching and degradation."""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone


class StockDataService:
    """行情数据服务：多数据源降级（腾讯行情 → 东方财富 → unavailable），带内存缓存。"""

    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self._cache: dict[str, dict] = {}

    def get_market_data(self, stock_code: str, stock_name: str = "") -> dict:
        """Get market data with cache → live API → unavailable fallback."""
        # 1. Check cache
        cached = self._get_cached(stock_code)
        if cached is not None:
            cached["source"] = "cache"
            cached["stock_name"] = stock_name or cached.get("stock_name", "")
            return cached

        # 2. Try data sources in order
        for fetcher, source_tag in [
            (self._fetch_from_tencent, "tencent"),
            (self._fetch_from_eastmoney, "eastmoney"),
        ]:
            data = fetcher(stock_code)
            if data is not None:
                data["stock_name"] = stock_name or data.get("stock_name", "")
                data["source"] = source_tag
                self._update_cache(stock_code, data)
                return data

        # 3. Degraded response
        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "pe": None,
            "pb": None,
            "market_cap": None,
            "latest_price": None,
            "data_time": None,
            "source": "unavailable",
        }

    # ── 腾讯行情 API（主数据源，稳定性好）────────────────────────

    def _make_tencent_symbol(self, stock_code: str) -> str:
        if stock_code.startswith(("6", "9")):
            return f"sh{stock_code}"
        return f"sz{stock_code}"

    def _fetch_from_tencent(self, stock_code: str) -> dict | None:
        """腾讯行情 qt.gtimg.cn — 无 TLS 指纹检测，稳定可用。"""
        try:
            import urllib.request
            symbol = self._make_tencent_symbol(stock_code)
            url = f"https://qt.gtimg.cn/q={symbol}"

            # 绕过系统代理
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.qq.com",
            })
            resp = opener.open(req, timeout=10)
            raw = resp.read().decode("gbk", errors="ignore")

            # 格式: v_sh600519="1~贵州茅台~600519~1466.40~1446.90~..."
            match = re.search(r'"(.+)"', raw)
            if not match:
                return None
            fields = match.group(1).split("~")
            if len(fields) < 50:
                return None

            def _safe_float(idx):
                try:
                    return round(float(fields[idx]), 2)
                except (ValueError, TypeError, IndexError):
                    return None

            # 腾讯行情字段索引:
            # 1=名称, 2=代码, 3=最新价, 4=昨收, 9=成交额(万)
            # 39=市盈率(TTM), 44=总市值(亿), 45=流通市值(亿), 46=市净率
            return {
                "stock_code": stock_code,
                "stock_name": fields[1] if len(fields) > 1 else "",
                "latest_price": _safe_float(3),
                "pe": _safe_float(39),
                "pb": _safe_float(46),
                "market_cap": _safe_float(44),  # 已经是亿元
                "data_time": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            return None

    # ── 东方财富 API（备用数据源，有 TLS 指纹检测）──────────────

    _EM_FIELDS = "f43,f57,f58,f116,f162,f167"
    _EM_URL = "https://push2.eastmoney.com/api/qt/stock/get"

    def _make_secid(self, stock_code: str) -> str:
        if stock_code.startswith(("6", "9")):
            return f"1.{stock_code}"
        return f"0.{stock_code}"

    def _fetch_from_eastmoney(self, stock_code: str) -> dict | None:
        """东方财富 push2 API — 需要 curl_cffi 模拟浏览器 TLS。"""
        try:
            from curl_cffi import requests as curl_requests
            params = {
                "fltt": 2, "invt": 2,
                "fields": self._EM_FIELDS,
                "secid": self._make_secid(stock_code),
            }
            resp = curl_requests.get(
                self._EM_URL, params=params,
                impersonate="chrome", timeout=10,
            )
            resp.raise_for_status()
            d = resp.json().get("data")
            if not d:
                return None

            def _safe_float(val, divisor=1):
                try:
                    return round(float(val) / divisor, 2)
                except (ValueError, TypeError):
                    return None

            return {
                "stock_code": stock_code,
                "stock_name": d.get("f58", ""),
                "latest_price": _safe_float(d.get("f43")),
                "pe": _safe_float(d.get("f162")),
                "pb": _safe_float(d.get("f167")),
                "market_cap": _safe_float(d.get("f116"), divisor=1e8),
                "data_time": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            return None

    # ── Cache ───────────────────────────────────────────────────

    def _get_cached(self, stock_code: str) -> dict | None:
        entry = self._cache.get(stock_code)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > self.cache_ttl:
            del self._cache[stock_code]
            return None
        return dict(entry["data"])

    def _update_cache(self, stock_code: str, data: dict) -> None:
        self._cache[stock_code] = {
            "data": dict(data),
            "timestamp": time.time(),
        }
