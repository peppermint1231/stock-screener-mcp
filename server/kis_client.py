"""한국투자증권 Open API 클라이언트"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN_CACHE_FILE = Path(__file__).parent.parent / ".token_cache.json"

# 모의투자 베이스 URL
BASE_URL_MOCK = "https://openapivts.koreainvestment.com:29443"
# 실전투자 베이스 URL
BASE_URL_REAL = "https://openapi.koreainvestment.com:9443"


def _safe_float(val, default=0.0):
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0):
    try:
        return int(val) if val else default
    except (ValueError, TypeError):
        return default


class KISClient:
    def __init__(self, mock=False):
        self.app_key = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.account_no = os.getenv("KIS_ACCOUNT_NO", "").replace("-", "")
        self.base_url = BASE_URL_MOCK if mock else BASE_URL_REAL
        self.mock = mock
        self.access_token = None
        self.token_expired = None

    def _get_token(self):
        """OAuth 접근 토큰 발급 (파일 캐싱)"""
        if self.access_token and self.token_expired and datetime.now() < self.token_expired:
            return self.access_token

        cache_key = "mock" if self.mock else "real"
        if TOKEN_CACHE_FILE.exists():
            try:
                cache = json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
                entry = cache.get(cache_key, {})
                expires = entry.get("expires", "")
                if expires and datetime.fromisoformat(expires) > datetime.now():
                    self.access_token = entry["token"]
                    self.token_expired = datetime.fromisoformat(expires)
                    return self.access_token
            except (json.JSONDecodeError, KeyError):
                pass

        url = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        resp = requests.post(url, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.token_expired = datetime.now() + timedelta(hours=23)

        cache = {}
        if TOKEN_CACHE_FILE.exists():
            try:
                cache = json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        cache[cache_key] = {
            "token": self.access_token,
            "expires": self.token_expired.isoformat(),
        }
        TOKEN_CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
        return self.access_token

    def _headers(self, tr_id):
        """API 호출 공통 헤더"""
        token = self._get_token()
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _get(self, path, tr_id, params=None):
        """GET 요청 공통"""
        url = f"{self.base_url}{path}"
        headers = self._headers(tr_id)
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Tool 1: 선물옵션 현재가 (야간선물 포함) ──────────────────
    def get_futures_price(self, code="A01606"):
        """선물옵션 현재가 조회

        Args:
            code: 종목코드 (마스터파일 기준 단축코드)
                KOSPI200선물: A016 + 만기(06=6월,09=9월,12=12월,03=3월)
                미니KOSPI200: A056 + 만기
                예: A01606 = KOSPI200 2026년 6월물(근월물)
        """
        path = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
        tr_id = "FHMIF10000000"
        params = {
            "FID_COND_MRKT_DIV_CODE": "F",
            "FID_INPUT_ISCD": code,
        }
        data = self._get(path, tr_id, params)
        output = data.get("output1", {}) or {}

        # KOSPI200 지수 정보 (output3)
        kospi200 = data.get("output3", {}) or {}

        return {
            "current_price": _safe_float(output.get("futs_prpr")),
            "change": _safe_float(output.get("futs_prdy_vrss")),
            "change_pct": _safe_float(output.get("futs_prdy_ctrt")),
            "open": _safe_float(output.get("futs_oprc")),
            "high": _safe_float(output.get("futs_hgpr")),
            "low": _safe_float(output.get("futs_lwpr")),
            "volume": _safe_int(output.get("acml_vol")),
            "open_interest": _safe_int(output.get("hts_otst_stpl_qty")),
            "prev_close": _safe_float(output.get("futs_prdy_clpr")),
            "settle_price": _safe_float(output.get("futs_sdpr")),
            "basis": _safe_float(output.get("basis")),
            "theoretical": _safe_float(output.get("hts_thpr")),
            "last_trade_date": output.get("futs_last_tr_date", ""),
            "remaining_days": _safe_int(output.get("hts_rmnn_dynu")),
            "name": output.get("hts_kor_isnm", ""),
            "code": code,
            "kospi200": {
                "price": _safe_float(kospi200.get("bstp_nmix_prpr")),
                "change_pct": _safe_float(kospi200.get("bstp_nmix_prdy_ctrt")),
            },
        }

    # ── Tool 3: 거래량/등락률 순위 ───────────────────────────────
    def get_volume_rank(self):
        """거래량 순위 상위 종목 조회"""
        path = "/uapi/domestic-stock/v1/quotations/volume-rank"
        tr_id = "FHPST01710000"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": "0000",
            "FID_DIV_CLS_CODE": "0",
            "FID_BLNG_CLS_CODE": "0",
            "FID_TRGT_CLS_CODE": "111111111",
            "FID_TRGT_EXLS_CLS_CODE": "000000",
            "FID_INPUT_PRICE_1": "",
            "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "",
            "FID_INPUT_DATE_1": "",
        }
        data = self._get(path, tr_id, params)
        items = data.get("output", [])
        return [
            {
                "rank": _safe_int(item.get("data_rank")),
                "name": item.get("hts_kor_isnm", ""),
                "code": item.get("mksc_shrn_iscd", ""),
                "price": _safe_int(item.get("stck_prpr")),
                "change_pct": _safe_float(item.get("prdy_ctrt")),
                "volume": _safe_int(item.get("acml_vol")),
                "trade_amount": _safe_int(item.get("acml_tr_pbmn")),
            }
            for item in items[:20]
        ]

    def get_fluctuation_rank(self, sort="0"):
        """등락률 순위 (sort: 0=상승, 1=하락)"""
        path = "/uapi/domestic-stock/v1/ranking/fluctuation"
        tr_id = "FHPST01700000"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20170",
            "FID_INPUT_ISCD": "0000",
            "FID_RANK_SORT_CLS_CODE": sort,
            "FID_INPUT_CNT_1": "0",
            "FID_PRC_CLS_CODE": "0",
            "FID_INPUT_PRICE_1": "",
            "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "",
            "FID_TRGT_CLS_CODE": "0",
            "FID_TRGT_EXLS_CLS_CODE": "0",
            "FID_DIV_CLS_CODE": "0",
            "FID_RSFL_RATE1": "",
            "FID_RSFL_RATE2": "",
        }
        data = self._get(path, tr_id, params)
        items = data.get("output", [])
        return [
            {
                "rank": _safe_int(item.get("data_rank")),
                "name": item.get("hts_kor_isnm", ""),
                "code": item.get("mksc_shrn_iscd", ""),
                "price": _safe_int(item.get("stck_prpr")),
                "change_pct": _safe_float(item.get("prdy_ctrt")),
                "volume": _safe_int(item.get("acml_vol")),
            }
            for item in items[:20]
        ]

    # ── Tool 4: 개별 종목 상세 ───────────────────────────────────
    def get_stock_price(self, ticker):
        """개별 종목 현재가 조회"""
        path = "/uapi/domestic-stock/v1/quotations/inquire-price"
        tr_id = "FHKST01010100"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }
        data = self._get(path, tr_id, params)
        output = data.get("output", {})
        return {
            "name": output.get("hts_kor_isnm", ""),
            "price": _safe_int(output.get("stck_prpr")),
            "change": _safe_int(output.get("prdy_vrss")),
            "change_pct": _safe_float(output.get("prdy_ctrt")),
            "open": _safe_int(output.get("stck_oprc")),
            "high": _safe_int(output.get("stck_hgpr")),
            "low": _safe_int(output.get("stck_lwpr")),
            "volume": _safe_int(output.get("acml_vol")),
            "trade_amount": _safe_int(output.get("acml_tr_pbmn")),
            "per": _safe_float(output.get("per")),
            "pbr": _safe_float(output.get("pbr")),
            "w52_high": _safe_int(output.get("stck_dryc_hgpr")),
            "w52_low": _safe_int(output.get("stck_dryc_lwpr")),
        }

    def get_investor_trading(self, ticker):
        """투자자별 매매동향"""
        path = "/uapi/domestic-stock/v1/quotations/inquire-investor"
        tr_id = "FHKST01010900"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }
        data = self._get(path, tr_id, params)
        items = data.get("output", [])
        result = {}
        for item in items:
            investor = item.get("invst_nm", "")
            if investor:
                result[investor] = {
                    "buy": _safe_int(item.get("total_seln_qty")),
                    "sell": _safe_int(item.get("total_shnu_qty")),
                    "net": _safe_int(item.get("seln_qty_smtn")),
                }
        return result


# ── 단독 실행 테스트 ─────────────────────────────────────────────
if __name__ == "__main__":
    client = KISClient(mock=False)
    print("=== 선물(101T6) 현재가 테스트 ===")
    try:
        result = client.get_futures_price("101T6")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"에러: {e}")

    print("\n=== 삼성전자(005930) 현재가 ===")
    try:
        result = client.get_stock_price("005930")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"에러: {e}")
