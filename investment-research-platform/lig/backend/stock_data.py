import time
import logging

logger = logging.getLogger(__name__)


class StockDataService:
    """AKShare 行情数据接口 + 缓存 + 降级"""

    def __init__(self, cache_ttl=300):
        self.cache_ttl = cache_ttl
        self._cache = {}

    def get_market_data(self, stock_code):
        cached = self._get_cached(stock_code)
        if cached is not None:
            cached["source"] = "cache"
            return cached
        data = self._fetch_from_akshare(stock_code)
        if data is not None:
            data["source"] = "akshare"
            self._update_cache(stock_code, data)
            return data
        return {
            "stock_code": stock_code,
            "pe": None,
            "pb": None,
            "market_cap": None,
            "latest_price": None,
            "data_time": None,
            "source": "unavailable",
        }

    def _fetch_from_akshare(self, stock_code):
        try:
            import akshare as ak
            from datetime import datetime, timezone

            df = ak.stock_individual_info_em(symbol=stock_code)
            info = {}
            for _, row in df.iterrows():
                info[row.iloc[0]] = row.iloc[1]

            pe = self._safe_float(info.get("市盈率(动态)"))
            pb = self._safe_float(info.get("市净率"))
            market_cap_raw = self._safe_float(info.get("总市值"))
            market_cap = round(market_cap_raw / 1e8, 2) if market_cap_raw else None
            latest_price = self._safe_float(info.get("股价"))

            return {
                "stock_code": stock_code,
                "pe": pe,
                "pb": pb,
                "market_cap": market_cap,
                "latest_price": latest_price,
                "data_time": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning(f"AKShare fetch failed for {stock_code}: {e}")
            return None

    def _safe_float(self, value):
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return None

    def _get_cached(self, stock_code):
        entry = self._cache.get(stock_code)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > self.cache_ttl:
            del self._cache[stock_code]
            return None
        return dict(entry["data"])

    def _update_cache(self, stock_code, data):
        self._cache[stock_code] = {
            "data": dict(data),
            "timestamp": time.time(),
        }
