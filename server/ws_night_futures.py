"""KRX 야간선물 실시간 WebSocket 수신기"""

import os
import json
import threading
import websockets
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

WS_URL = "ws://ops.koreainvestment.com:21000"

# 최근 체결 데이터를 저장하는 공유 딕셔너리
_latest = {}
_lock = threading.Lock()
_running = False


def get_approval_key():
    """WebSocket 접속키 발급"""
    import requests
    url = "https://openapi.koreainvestment.com:9443/oauth2/Approval"
    body = {
        "grant_type": "client_credentials",
        "appkey": os.getenv("KIS_APP_KEY"),
        "secretkey": os.getenv("KIS_APP_SECRET"),
    }
    resp = requests.post(url, json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()["approval_key"]


def _parse_night_futures(data: str) -> dict | None:
    """야간선물 체결 데이터 파싱 (H0MFCNT0)

    수신 형식: tr_id|tr_type|tr_key|체결데이터(^구분)
    """
    parts = data.split("|")
    if len(parts) < 4:
        return None

    tr_id = parts[0]
    if tr_id != "H0MFCNT0":
        return None

    fields = parts[3].split("^")
    if len(fields) < 20:
        return None

    return {
        "code": fields[0],           # 종목코드
        "time": fields[1],           # 체결시간 HHMMSS
        "price": float(fields[2]),   # 현재가
        "change": float(fields[4]),  # 전일대비
        "change_pct": float(fields[5]),  # 등락률
        "open": float(fields[7]),    # 시가
        "high": float(fields[8]),    # 고가
        "low": float(fields[9]),     # 저가
        "volume": int(fields[10]),   # 누적거래량
        "trade_amount": int(fields[11]) if fields[11] else 0,  # 누적거래대금
        "timestamp": datetime.now().isoformat(),
    }


async def _ws_loop(code: str):
    """WebSocket 수신 루프"""
    global _running

    approval_key = get_approval_key()

    subscribe_msg = json.dumps({
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "1",
            "content-type": "utf-8",
        },
        "body": {
            "input": {
                "tr_id": "H0MFCNT0",
                "tr_key": code,
            }
        }
    })

    while _running:
        try:
            async with websockets.connect(WS_URL, ping_interval=30) as ws:
                await ws.send(subscribe_msg)
                print(f"[WS] 야간선물 {code} 구독 시작")

                while _running:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)

                    # JSON 응답 (구독 확인 등)
                    if raw.startswith("{"):
                        msg = json.loads(raw)
                        header = msg.get("header", {})
                        if header.get("tr_id") == "PINGPONG":
                            await ws.send(raw)
                        continue

                    # 체결 데이터
                    parsed = _parse_night_futures(raw)
                    if parsed:
                        with _lock:
                            _latest[parsed["code"]] = parsed

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            if _running:
                print(f"[WS] 재연결 시도... ({e})")
                await asyncio.sleep(3)


def start(code: str = "101W9000"):
    """백그라운드 스레드에서 야간선물 수신 시작

    Args:
        code: 야간선물 종목코드 (WebSocket용, 예: 101W9000)
    """
    global _running
    if _running:
        return

    _running = True

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_ws_loop(code))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print(f"[WS] 백그라운드 수신 스레드 시작 (code={code})")


def stop():
    """수신 중지"""
    global _running
    _running = False
    print("[WS] 수신 중지")


def get_latest(code: str = None) -> dict | None:
    """가장 최근 체결 데이터 반환"""
    with _lock:
        if code:
            return _latest.get(code)
        # 코드 미지정 시 가장 최근 데이터
        if _latest:
            return max(_latest.values(), key=lambda x: x["timestamp"])
        return None


def get_all() -> dict:
    """모든 종목의 최근 체결 데이터"""
    with _lock:
        return dict(_latest)


# 단독 실행 테스트
if __name__ == "__main__":
    import time
    print("야간선물 WebSocket 테스트 (Ctrl+C로 종료)")
    start("101W9000")
    try:
        while True:
            time.sleep(2)
            data = get_latest()
            if data:
                print(f"  {data['time']} | {data['price']} ({data['change_pct']:+.2f}%) | vol={data['volume']:,}")
            else:
                print("  대기 중... (야간세션 18:00~05:00)")
    except KeyboardInterrupt:
        stop()
