"""피봇 포인트 계산 (Standard + Fibonacci)"""


def calculate_pivot_points(high: float, low: float, close: float) -> dict:
    """Standard 및 Fibonacci 피봇 포인트 계산

    Args:
        high: 고가
        low: 저가
        close: 종가

    Returns:
        standard, fibonacci 피봇 포인트 + 두 방식의 범위
    """
    pivot = (high + low + close) / 3
    range_ = high - low

    # Standard Pivot Points
    standard = {
        "R3": round(high + 2 * (pivot - low), 2),
        "R2": round(pivot + range_, 2),
        "R1": round(2 * pivot - low, 2),
        "P": round(pivot, 2),
        "S1": round(2 * pivot - high, 2),
        "S2": round(pivot - range_, 2),
        "S3": round(low - 2 * (high - pivot), 2),
    }

    # Fibonacci Pivot Points
    fibonacci = {
        "R3": round(pivot + 1.000 * range_, 2),
        "R2": round(pivot + 0.618 * range_, 2),
        "R1": round(pivot + 0.382 * range_, 2),
        "P": round(pivot, 2),
        "S1": round(pivot - 0.382 * range_, 2),
        "S2": round(pivot - 0.618 * range_, 2),
        "S3": round(pivot - 1.000 * range_, 2),
    }

    # 두 방식의 범위 (Standard ~ Fibonacci)
    combined_range = {}
    for level in ["R3", "R2", "R1", "P", "S1", "S2", "S3"]:
        lo = min(standard[level], fibonacci[level])
        hi = max(standard[level], fibonacci[level])
        if lo == hi:
            combined_range[level] = f"{lo}"
        else:
            combined_range[level] = f"{lo:.2f}~{hi:.2f}"

    return {
        "standard": standard,
        "fibonacci": fibonacci,
        "range": combined_range,
        "input": {"high": high, "low": low, "close": close},
    }
