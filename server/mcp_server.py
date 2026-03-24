"""Stock Screener MCP Server — KRX 야간선물 + 주도주 스크리닝"""

import sys
import json
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from server.kis_client import KISClient
from server.pivot import calculate_pivot_points
from server.screener import score_stock, predict_gap
from server import ws_night_futures

mcp = FastMCP("stock-screener", dependencies=["requests", "python-dotenv", "websockets"])

# 실전투자 클라이언트 (선물옵션 시세는 실전 서버만 지원)
client = KISClient(mock=False)

# 야간선물 WebSocket 자동 시작
ws_night_futures.start("A01606")

# 종목 코드 매핑 로드
TICKERS_FILE = Path(__file__).parent.parent / "config" / "tickers.json"
TICKERS = json.loads(TICKERS_FILE.read_text(encoding="utf-8"))


@mcp.tool()
def get_futures_price(code: str = "A01606") -> dict:
    """KOSPI200 선물 현재가 조회

    종목코드 형식 (마스터파일 기준):
      KOSPI200선물: A016 + 만기(06,09,12,03) — 예: A01606 = 2026년 6월물
      미니KOSPI200: A056 + 만기 — 예: A05606

    Args:
        code: 선물 종목코드 (기본값: A01606 = KOSPI200 근월물)
    """
    return client.get_futures_price(code)


@mcp.tool()
def get_pivot_points(high: float, low: float, close: float) -> dict:
    """피봇 포인트 계산 (Standard + Fibonacci)

    선물 또는 주식의 고가/저가/종가를 입력하면
    Standard 및 Fibonacci 방식의 R3~S3 피봇 포인트를 계산합니다.

    Args:
        high: 고가
        low: 저가
        close: 종가
    """
    return calculate_pivot_points(high, low, close)


@mcp.tool()
def get_market_leaders() -> dict:
    """주도주 조회 — 거래대금 상위 + 상승률/하락률 순위

    거래대금 TOP 20, 상승률 TOP 20, 하락률 TOP 20을 반환합니다.
    """
    top_volume = client.get_volume_rank()
    top_gainers = client.get_fluctuation_rank(sort="0")
    top_losers = client.get_fluctuation_rank(sort="1")
    return {
        "top_volume": top_volume,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
    }


@mcp.tool()
def get_stock_detail(ticker: str) -> dict:
    """개별 종목 상세 시세 + 투자자별 수급

    종목코드를 입력하면 현재가, OHLC, PER, PBR, 52주 범위,
    외국인/기관 매매동향을 조회합니다.

    Args:
        ticker: 종목코드 (예: 005930=삼성전자, 000660=SK하이닉스)
    """
    price_data = client.get_stock_price(ticker)
    investor_data = client.get_investor_trading(ticker)
    return {
        "price": price_data,
        "investors": investor_data,
    }


@mcp.tool()
def screen_leaders() -> list:
    """주도주 스크리닝 — 멀티팩터 스코어링

    거래대금 상위 20 종목을 대상으로
    거래대금(25%), 등락률(15%), 외국인(20%), 기관(15%),
    뉴스/테마(15%), 기술적(10%) 점수를 합산하여 순위를 매깁니다.
    """
    volume_ranks = client.get_volume_rank()
    gainer_ranks = client.get_fluctuation_rank(sort="0")

    scored = []
    for item in volume_ranks[:15]:
        code = item["code"]
        try:
            price = client.get_stock_price(code)
            investors = client.get_investor_trading(code)
            stock = {**price, "code": code, "investors": investors}
            result = score_stock(stock, volume_ranks, gainer_ranks)
            scored.append(result)
        except Exception as e:
            scored.append({"code": code, "name": item["name"], "error": str(e)})

    scored.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    return scored


@mcp.tool()
def predict_opening_gap(
    night_futures_price: float,
    day_close: float,
    sp500_change_pct: float = 0.0,
) -> dict:
    """익일 갭 예측 — 야간선물 vs 주간선물 괴리율

    야간선물 현재가와 주간선물 종가를 비교하여
    익일 시초가 갭 방향과 확률을 예측합니다.

    Args:
        night_futures_price: 야간선물 현재가
        day_close: 주간선물(또는 KOSPI200) 종가
        sp500_change_pct: S&P500 등락률 (보조 지표)
    """
    return predict_gap(night_futures_price, day_close, sp500_change_pct)


@mcp.tool()
def get_night_futures() -> dict:
    """야간선물 실시간 체결가 조회 (WebSocket)

    야간세션(18:00~05:00) 중에만 데이터가 수신됩니다.
    가장 최근 체결된 가격, 등락률, 거래량을 반환합니다.
    장 마감 시간에는 REST API로 주간선물 데이터를 대신 반환합니다.
    """
    data = ws_night_futures.get_latest()
    if data:
        return {
            "source": "websocket_realtime",
            "session": "night",
            **data,
        }
    # 야간 데이터 없으면 REST로 주간 데이터 반환
    rest_data = client.get_futures_price("A01606")
    return {
        "source": "rest_api",
        "session": "day",
        "message": "야간세션 데이터 없음. 주간선물 데이터를 반환합니다.",
        **rest_data,
    }


@mcp.tool()
def lookup_ticker(name: str) -> dict:
    """종목명으로 종목코드 조회

    주요 종목 및 선물 코드 매핑을 검색합니다.

    Args:
        name: 종목명 또는 키워드 (예: 삼성전자, KOSPI200)
    """
    results = {}
    for category, mapping in TICKERS.items():
        for key, code in mapping.items():
            if name.lower() in key.lower():
                results[key] = code
    return results if results else {"message": f"'{name}'에 해당하는 종목을 찾을 수 없습니다."}


if __name__ == "__main__":
    mcp.run()
