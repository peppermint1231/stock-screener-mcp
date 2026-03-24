"""야간세션 테스트 — 18:00 이후 실행하세요

REST API(A01606)가 야간선물 데이터를 반환하는지,
WebSocket(101W9000)과 같은 값인지 비교합니다.
"""

import sys
import time

sys.path.insert(0, ".")

from server.kis_client import KISClient
from server import ws_night_futures

client = KISClient(mock=False)

# 1. REST로 주간선물 코드 조회
print("=== REST API: A01606 ===")
rest = client.get_futures_price("A01606")
print(f"  현재가: {rest['current_price']}")
print(f"  등락: {rest['change']} ({rest['change_pct']:+.2f}%)")
print(f"  시가: {rest['open']}, 고가: {rest['high']}, 저가: {rest['low']}")
print(f"  거래량: {rest['volume']:,}")

# 2. WebSocket으로 야간선물 수신
print("\n=== WebSocket: 101W9000 (10초 대기) ===")
ws_night_futures.start("101W9000")
time.sleep(10)
ws = ws_night_futures.get_latest()

if ws:
    print(f"  현재가: {ws['price']}")
    print(f"  등락: {ws['change']} ({ws['change_pct']:+.2f}%)")
    print(f"  시가: {ws['open']}, 고가: {ws['high']}, 저가: {ws['low']}")
    print(f"  거래량: {ws['volume']:,}")
    print(f"  체결시간: {ws['time']}")

    # 3. 비교
    print("\n=== 비교 결과 ===")
    if rest["current_price"] > 0 and ws["price"] > 0:
        match = abs(rest["current_price"] - ws["price"]) < 0.5
        print(f"  REST 현재가: {rest['current_price']}")
        print(f"  WS   현재가: {ws['price']}")
        print(f"  결론: {'같은 데이터! REST만으로 충분' if match else 'REST와 WS가 다름 → 야간은 WebSocket 필요'}")
    elif rest["current_price"] == 0:
        print(f"  REST는 비어있고 WS만 데이터 있음 → 야간선물은 WebSocket 전용")
    else:
        print("  판단 불가")
else:
    print("  WebSocket 데이터 없음")
    if rest["current_price"] > 0:
        print("  REST에만 데이터 있음 → REST가 야간으로 전환된 것일 수 있음")
    else:
        print("  둘 다 없음 → 아직 야간세션 시작 전")

ws_night_futures.stop()
