"""주도주 스크리닝 로직 — 멀티팩터 스코어링"""


def score_stock(stock: dict, volume_ranks: list, gainer_ranks: list) -> dict:
    """개별 종목 스코어 계산

    팩터 가중치:
        거래대금 순위 25%, 등락률 15%, 외국인 순매수 20%,
        기관 순매수 15%, 뉴스/테마 15%, 기술적 신호 10%

    Args:
        stock: get_stock_price() 결과 + investor 데이터
        volume_ranks: 거래량 순위 리스트
        gainer_ranks: 상승률 순위 리스트
    """
    code = stock.get("code", "")
    scores = {}

    # 1. 거래대금 순위 (25%)
    vol_rank = next((r["rank"] for r in volume_ranks if r["code"] == code), 999)
    if vol_rank <= 5:
        scores["거래대금"] = 10
    elif vol_rank <= 10:
        scores["거래대금"] = 8
    elif vol_rank <= 20:
        scores["거래대금"] = 5
    else:
        scores["거래대금"] = 0

    # 2. 등락률 (15%)
    change_pct = stock.get("change_pct", 0)
    if change_pct >= 5:
        scores["등락률"] = 10
    elif change_pct >= 3:
        scores["등락률"] = 8
    elif change_pct >= 1:
        scores["등락률"] = 5
    elif change_pct >= 0:
        scores["등락률"] = 2
    else:
        scores["등락률"] = 0

    # 3. 외국인 순매수 (20%)
    investors = stock.get("investors", {})
    foreign_net = 0
    for key, val in investors.items():
        if "외국인" in key:
            foreign_net = val.get("net", 0)
            break
    if foreign_net > 0:
        scores["외국인"] = min(10, 5 + int(foreign_net / 10000))
    else:
        scores["외국인"] = 0

    # 4. 기관 순매수 (15%)
    inst_net = 0
    for key, val in investors.items():
        if "기관" in key:
            inst_net = val.get("net", 0)
            break
    if inst_net > 0:
        scores["기관"] = min(10, 5 + int(inst_net / 10000))
    else:
        scores["기관"] = 0

    # 5. 기술적 신호 (10%) — 간단한 프록시로 상승률 순위 활용
    gain_rank = next((r["rank"] for r in gainer_ranks if r["code"] == code), 999)
    if gain_rank <= 10:
        scores["기술적"] = 8
    elif gain_rank <= 30:
        scores["기술적"] = 5
    else:
        scores["기술적"] = 2

    # 가중 합산
    weights = {"거래대금": 0.25, "등락률": 0.15, "외국인": 0.20, "기관": 0.15, "기술적": 0.10}
    total = sum(scores.get(k, 0) * w for k, w in weights.items())
    # 뉴스/테마 15%는 AI 분석 영역이므로 기본 5점 부여
    total += 5 * 0.15

    return {
        "code": code,
        "name": stock.get("name", ""),
        "price": stock.get("price", 0),
        "change_pct": change_pct,
        "total_score": round(total, 2),
        "factor_scores": scores,
        "foreign_net": foreign_net,
        "institution_net": inst_net,
    }


def predict_gap(night_futures_price: float, day_close: float,
                sp500_change_pct: float = 0, usd_krw_change_pct: float = 0) -> dict:
    """야간선물 vs 주간선물 괴리율 기반 갭 예측

    Args:
        night_futures_price: 야간선물 현재가
        day_close: 주간선물 종가
        sp500_change_pct: S&P500 등락률
        usd_krw_change_pct: 환율 등락률
    """
    if day_close == 0:
        return {"error": "주간선물 종가가 0입니다"}

    gap_pct = (night_futures_price - day_close) / day_close * 100

    # 기본 판단
    if gap_pct > 1.0:
        direction = "갭 상승"
        probability = min(95, 80 + gap_pct * 3)
    elif gap_pct > 0.3:
        direction = "소폭 상승"
        probability = 55 + gap_pct * 10
    elif gap_pct > -0.3:
        direction = "보합"
        probability = 50
    elif gap_pct > -1.0:
        direction = "소폭 하락"
        probability = 55 + abs(gap_pct) * 10
    else:
        direction = "갭 하락"
        probability = min(95, 80 + abs(gap_pct) * 3)

    # 보조 요소 반영
    if sp500_change_pct > 0.5:
        probability = min(95, probability + 5)
    elif sp500_change_pct < -0.5:
        probability = max(50, probability - 5)

    return {
        "gap_pct": round(gap_pct, 2),
        "direction": direction,
        "probability": round(probability, 1),
        "night_futures": night_futures_price,
        "day_close": day_close,
    }
