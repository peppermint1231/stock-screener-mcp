# Stock Screener MCP Server — CLAUDE.md

## 프로젝트 개요
KRX 야간선물 실시간 데이터 + 주도주 스크리닝 + 매매 플랜 자동 생성 시스템.
한국투자증권 Open API를 통해 실제 KRX-Eurex 야간선물 데이터를 확보하고,
Claude가 이를 분석하여 피봇 포인트, 갭 예측, 주도주 발굴을 수행한다.

## 환경 설정

### 1. API 키 설정 (환경변수로 관리 — 코드에 직접 넣지 않음)
```bash
# Windows PowerShell
$env:KIS_APP_KEY = "여기에_APP_KEY"
$env:KIS_APP_SECRET = "여기에_APP_SECRET"
$env:KIS_ACCOUNT_NO = "여기에_계좌번호"  # 모의투자 계좌

# 또는 .env 파일 생성
# KIS_APP_KEY=...
# KIS_APP_SECRET=...
# KIS_ACCOUNT_NO=...
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 프로젝트 구조
```
stock-screener-mcp/
├── CLAUDE.md              ← 이 파일
├── .env                   ← API 키 (gitignore 필수)
├── .gitignore
├── requirements.txt       ← Python 의존성
├── Dockerfile             ← 클라우드 배포용
├── railway.json           ← Railway 배포 설정
├── server/
│   ├── mcp_server.py      ← MCP 서버 메인 (stdio/SSE 듀얼 트랜스포트)
│   ├── kis_client.py      ← 한투 API 클라이언트
│   ├── ws_night_futures.py ← 야간선물 WebSocket 수신기
│   ├── pivot.py            ← 피봇 포인트 계산
│   └── screener.py         ← 주도주 스크리닝 로직
├── config/
│   └── tickers.json       ← 주요 종목 코드 매핑
└── tests/
    ├── test_kis.py        ← API 연결 테스트
    └── test_night_session.py ← 야간세션 테스트
```

## 핵심 기능 명세

### Tool 1: get_night_futures()
KRX-Eurex 연계 야간선물 실시간 시세 조회

```python
# 한투 API 엔드포인트
# 선물 현재가: /uapi/domestic-futureoption/v1/quotations/inquire-price
# 종목코드: 101S03 (KOSPI200 선물 근월물)
# 또는 모의투자: /uapi/domestic-futureoption/v1/quotations/inquire-price

반환값:
{
    "current_price": 859.25,     # 현재가
    "change": 54.25,             # 전일대비
    "change_pct": 6.74,          # 등락률
    "open": 807.90,              # 시가
    "high": 869.40,              # 고가
    "low": 796.55,               # 저가
    "day_close": 805.00,         # 주간선물 종가
    "volume": 29291,             # 거래량
    "timestamp": "23:27:47",     # 갱신시간
    "session": "night"           # 야간/주간 구분
}
```

### Tool 2: get_pivot_points(high, low, close)
피봇 포인트 자동 계산 (Standard + Fibonacci)

```python
반환값:
{
    "standard": {"R3": ..., "R2": ..., "R1": ..., "P": ..., "S1": ..., "S2": ..., "S3": ...},
    "fibonacci": {"R3": ..., "R2": ..., "R1": ..., "P": ..., "S1": ..., "S2": ..., "S3": ...},
    "range": {"R3": "883~892", "R2": "878~883", ...}  # 두 방식 범위
}
```

### Tool 3: get_market_leaders()
거래대금/상승률 상위 종목 조회

```python
# 한투 API: /uapi/domestic-stock/v1/ranking/volume
# 거래량 순위, 등락률 순위, 시가총액 순위 등

반환값:
{
    "top_volume": [...],         # 거래대금 상위 20
    "top_gainers": [...],        # 상승률 상위 20
    "top_losers": [...],         # 하락률 상위 20
    "foreign_net_buy": [...],    # 외국인 순매수 상위
    "institution_net_buy": [...]  # 기관 순매수 상위
}
```

### Tool 4: get_stock_detail(ticker)
개별 종목 상세 시세 + 수급

```python
반환값:
{
    "price": {...},           # 현재가, OHLC, 52주 범위
    "valuation": {...},       # PER, PBR, ROE, 배당수익률
    "supply": {...},          # 외국인/기관 순매수
    "technical": {...}        # RSI, 이평선 (한투 API 제공 시)
}
```

### Tool 5: get_macro_data()
글로벌 매크로 지표 (Phase 0 베이스라인)

```python
# 한투 API 해외지수: /uapi/overseas-price/v1/quotations/inquire-daily-chartprice
# 또는 web_search 조합

반환값:
{
    "kospi200_futures": {...},   # 야간선물
    "sp500": {...},              # S&P 500
    "nasdaq": {...},             # NASDAQ
    "vix": {...},                # VIX
    "wti": {...},                # WTI 유가
    "usd_krw": {...},            # 환율
    "gold": {...},               # 금
    "btc": {...}                 # 비트코인
}
```

## 한투 API 주요 엔드포인트

### 국내 선물옵션
| 기능 | 엔드포인트 | tr_id |
|------|----------|-------|
| 선물 현재가 | /uapi/domestic-futureoption/v1/quotations/inquire-price | FHMST51010000 |
| 선물 시세체결 | /uapi/domestic-futureoption/v1/quotations/inquire-ccnl | FHMST51020000 |

### 국내 주식 순위
| 기능 | 엔드포인트 | tr_id |
|------|----------|-------|
| 거래량 순위 | /uapi/domestic-stock/v1/ranking/volume | FHPST01710000 |
| 등락률 순위 | /uapi/domestic-stock/v1/ranking/fluctuation | FHPST01700000 |
| 시가총액 순위 | /uapi/domestic-stock/v1/ranking/market-cap | FHPST01740000 |

### 국내 주식 시세
| 기능 | 엔드포인트 | tr_id |
|------|----------|-------|
| 현재가 | /uapi/domestic-stock/v1/quotations/inquire-price | FHKST01010100 |
| 투자자별 매매동향 | /uapi/domestic-stock/v1/quotations/inquire-investor | FHKST01010900 |
| 외국인/기관 매매종목 | /uapi/domestic-stock/v1/quotations/inquire-member | FHKST01010600 |

### 해외 지수
| 기능 | 엔드포인트 | tr_id |
|------|----------|-------|
| 해외지수 시세 | /uapi/overseas-price/v1/quotations/inquire-daily-chartprice | FHKST03030100 |

## MCP 서버 설정

### 트랜스포트 모드
- **stdio** (기본값): Claude Code / Claude Desktop에서 로컬 실행
- **SSE**: 클라우드 배포용 (`MCP_TRANSPORT=sse` 환경변수로 전환)

### Claude Code에서 등록 (로컬)
```bash
claude mcp add stock-screener -- python server/mcp_server.py
```

### Claude Desktop에서 등록 (claude_desktop_config.json)
```json
{
    "mcpServers": {
        "stock-screener": {
            "command": "python",
            "args": ["C:/path/to/stock-screener-mcp/server/mcp_server.py"],
            "env": {
                "KIS_APP_KEY": "환경변수에서",
                "KIS_APP_SECRET": "환경변수에서",
                "KIS_ACCOUNT_NO": "환경변수에서"
            }
        }
    }
}
```

### 웹 Claude (claude.ai)에서 사용 — 클라우드 배포
Railway에 배포 완료됨. 설정 방법:
1. claude.ai → Settings → Integrations → Add custom integration
2. URL: `https://stock-screener-mcp-production.up.railway.app/sse`

### Railway 클라우드 배포 정보
- **플랫폼**: Railway (Dockerfile 기반)
- **환경변수** (Railway Variables에 설정):
  - `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO` — 한투 API 키
  - `MCP_TRANSPORT=sse` — SSE 모드 활성화
- **GitHub 연동**: push 시 자동 재배포

### 새 PC에서 로컬 환경 셋업
```bash
git clone https://github.com/peppermint1231/stock-screener-mcp.git
cd stock-screener-mcp
pip install -r requirements.txt
# .env 파일 생성 (KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO)
claude mcp add stock-screener -- python server/mcp_server.py
```

## 스크리닝 로직 (이전 스킬에서 이식)

### 멀티팩터 스코어링
| 팩터 | 가중 | 측정 방법 |
|------|------|----------|
| 거래대금 순위 | 25% | 상위 10위 내 = 10점 |
| 등락률 | 15% | +3% 이상 = 10점 |
| 외국인 순매수 | 20% | 순매수 상위 = 10점 |
| 기관 순매수 | 15% | 순매수 상위 = 10점 |
| 뉴스/테마 연관성 | 15% | AI 분석 |
| 기술적 신호 | 10% | RSI 50-70 = 10점 |

### 피봇 포인트 계산
Standard + Fibonacci 두 방식 → 범위로 제시
→ server/pivot.py에 구현

### 갭 예측 로직
야간선물 vs 주간선물 괴리율:
- > +1.0% → 갭 상승 80%+
- -0.3% ~ +0.3% → 보합
- < -1.0% → 갭 하락 80%+

보조 요소: S&P500 방향(25%), 유가(15%), 환율(10%), OI 변화(10%)

## 보안 주의사항
- .env 파일은 반드시 .gitignore에 포함
- API 키를 코드에 하드코딩하지 않음
- 모의투자 계좌로 먼저 테스트 후 실계좌 연동
- API 호출 rate limit 준수 (초당 20건)
