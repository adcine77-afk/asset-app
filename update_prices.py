"""
자산관리앱 시세 자동 수집 스크립트
- 국내 주식/ETF: 네이버 금융 모바일 API (m.stock.naver.com)
- 해외 주식: Yahoo Finance 공개 API (query2.finance.yahoo.com)

[주의] 네이버 금융 API는 페이지 구조 변경 시 작동이 멈출 수 있습니다.
       안 될 때는 NAVER_HEADERS 또는 NAVER_URL 형식을 재확인하세요.
       종목 코드(KOREAN_TICKERS)가 맞는지 네이버 금융에서 직접 검색 후 확인해주세요.

[실행법] python update_prices.py
[출력]  prices.json (현재 폴더에 저장)
"""

import json
import time
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# ──────────────────────────────────────────────────────────────────────────────
# 종목 코드 매핑
# [중요] 아래 종목 코드는 네이버 금융 검색으로 직접 확인해주세요.
#        https://finance.naver.com/ 에서 종목명 검색 → URL의 code= 숫자
# ──────────────────────────────────────────────────────────────────────────────
KOREAN_TICKERS = {
    # 개별주
    "삼성전자":                      "005930",
    "SK하이닉스":                    "000660",
    "두산에너빌리티":                 "034020",
    # ETF - 직접 코드 확인 필요한 항목에 주석 표시
    "TIGER 미국나스닥100":           "133690",   # ✅ 확인됨
    "TIGER 나스닥100":               "133690",   # ✅ 위와 동일 코드
    "KODEX 미국S&P500":             "379800",   # ✅ 확인됨
    "KODEX 미국10년국채액티브(H)":    "304660",   # ⚠️ 코드 재확인 권장
    "ACE 반도체TOP4Plus":            "396500",   # ⚠️ 코드 재확인 권장
    "KODEX SMR":                    "411060",   # ⚠️ 코드 재확인 권장
    "KODEX200":                     "069500",   # ✅ 확인됨
    "RISE 코리아밸류업":              "466920",   # ⚠️ 코드 재확인 권장
}

# 해외 주식 (Yahoo Finance 티커 심볼)
US_TICKERS = ["NVDA", "PLTR", "IONQ"]

# ──────────────────────────────────────────────────────────────────────────────
# 네이버 금융 시세 조회
# ──────────────────────────────────────────────────────────────────────────────
NAVER_API_URL = "https://m.stock.naver.com/api/stock/{code}/basic"
NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json",
}

def fetch_korean_price(name: str, code: str) -> dict | None:
    """네이버 금융에서 국내 종목 현재가 조회"""
    url = NAVER_API_URL.format(code=code)
    try:
        resp = requests.get(url, headers=NAVER_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # closePrice: 종가 (장 마감 후), currentPrice: 현재가 (장중)
        raw = data.get("closePrice") or data.get("currentPrice") or data.get("stockEndPrice")
        if raw is None:
            print(f"  ⚠️  {name}({code}): 가격 필드 없음. API 응답: {list(data.keys())[:5]}")
            return None
        # 문자열 콤마 제거 후 숫자 변환 (예: "75,000" → 75000)
        price = float(str(raw).replace(",", ""))
        print(f"  ✅ {name}({code}): {price:,.0f}원 (네이버금융)")
        return {"price": price, "currency": "KRW", "code": code, "source": "네이버금융"}
    except Exception as e:
        print(f"  ❌ {name}({code}) 실패: {e}")
        return None

# ──────────────────────────────────────────────────────────────────────────────
# Yahoo Finance 시세 조회
# ──────────────────────────────────────────────────────────────────────────────
YAHOO_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

def fetch_us_price(ticker: str) -> dict | None:
    """Yahoo Finance에서 해외 주식 현재가 조회"""
    url = YAHOO_URL.format(ticker=ticker)
    try:
        resp = requests.get(url, headers=YAHOO_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        meta = data["chart"]["result"][0]["meta"]
        # regularMarketPrice: 가장 최근 거래가 (장중 or 종가)
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        if price is None:
            print(f"  ⚠️  {ticker}: 가격 필드 없음")
            return None
        print(f"  ✅ {ticker}: ${price:.2f} USD (Yahoo Finance)")
        return {"price": round(price, 4), "currency": "USD", "source": "Yahoo Finance"}
    except Exception as e:
        print(f"  ❌ {ticker} 실패: {e}")
        return None

# ──────────────────────────────────────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────────────────────────────────────
def main():
    now_kst = datetime.now(KST)
    updated_str = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    print(f"\n📡 시세 수집 시작 — {now_kst.strftime('%Y-%m-%d %H:%M')} KST\n")

    prices = {}

    print("🇰🇷 국내 종목 (네이버 금융)")
    for name, code in KOREAN_TICKERS.items():
        result = fetch_korean_price(name, code)
        if result:
            prices[name] = result
        time.sleep(0.5)   # 과도한 요청 방지 (0.5초 간격)

    print("\n🌏 해외 종목 (Yahoo Finance)")
    for ticker in US_TICKERS:
        result = fetch_us_price(ticker)
        if result:
            prices[ticker] = result
        time.sleep(0.5)

    output = {
        "updated": updated_str,
        "note": "본 데이터는 자동 수집된 참고용 데이터입니다. 지연되거나 부정확할 수 있습니다.",
        "sources": {
            "korea": "네이버 금융 모바일 API (m.stock.naver.com)",
            "us":    "Yahoo Finance 공개 API (query2.finance.yahoo.com)"
        },
        "prices": prices
    }

    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    success = len(prices)
    total   = len(KOREAN_TICKERS) + len(US_TICKERS)
    print(f"\n✅ 완료 — {success}/{total}개 종목 저장 → prices.json")

if __name__ == "__main__":
    main()
