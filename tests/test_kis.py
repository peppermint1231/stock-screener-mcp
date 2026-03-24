"""한투 API 연결 + MCP 도구 통합 테스트"""

import sys
import json
sys.path.insert(0, ".")

from server.kis_client import KISClient
from server.pivot import calculate_pivot_points
from server.screener import predict_gap


def test_all():
    client = KISClient(mock=False)

    # 1. 선물 현재가
    print("=== 1. KOSPI200 선물 (101T6) ===")
    futures = client.get_futures_price("101T6")
    print(f"  KOSPI200 지수: {futures['kospi200']['price']} ({futures['kospi200']['change_pct']}%)")
    print(f"  선물 현재가: {futures['current_price']} (장마감시 0)")

    # 2. 피봇 포인트
    print("\n=== 2. 피봇 포인트 (KOSPI200 기준) ===")
    k = futures["kospi200"]["price"] or 827.64
    pivot = calculate_pivot_points(high=k * 1.01, low=k * 0.99, close=k)
    for level in ["R3", "R2", "R1", "P", "S1", "S2", "S3"]:
        print(f"  {level}: {pivot['range'][level]}")

    # 3. 삼성전자
    print("\n=== 3. 삼성전자 (005930) ===")
    samsung = client.get_stock_price("005930")
    print(f"  현재가: {samsung['price']:,}원 ({samsung['change_pct']}%)")
    print(f"  PER={samsung['per']}, PBR={samsung['pbr']}")

    # 4. 거래량 순위
    print("\n=== 4. 거래량 순위 TOP 5 ===")
    for v in client.get_volume_rank()[:5]:
        print(f"  {v['rank']}위: {v['name']} ({v['code']}) {v['price']:,}원 {v['change_pct']}%")

    # 5. 상승률 순위
    print("\n=== 5. 상승률 순위 TOP 5 ===")
    for g in client.get_fluctuation_rank("0")[:5]:
        print(f"  {g['rank']}위: {g['name']} +{g['change_pct']}%")

    # 6. 갭 예측
    print("\n=== 6. 갭 예측 (예시) ===")
    gap = predict_gap(835.0, 827.64, sp500_change_pct=0.5)
    print(f"  괴리율: {gap['gap_pct']}% -> {gap['direction']} ({gap['probability']}%)")

    print("\n모든 테스트 통과!")


if __name__ == "__main__":
    test_all()
