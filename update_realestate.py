"""
국토교통부 아파트매매 실거래자료 API → re_prices.json
홍제센트럴아이파크 (서대문구 LAWD_CD: 11170) 실거래가 수집

출력 형식:
{
  "apt": {
    "name": "홍제센트럴아이파크",
    "price": 1480000000,          # 원 단위
    "priceSource": "국토부실거래가",
    "dealDate": "2026-05",        # YYYY-MM (실거래 없으면 null)
    "updatedAt": "2026-06-01T09:00:00+09:00"
  }
}

거래 없는 달: 최근 6개월까지 조회 범위를 넓혀서 재시도.
그래도 없으면(최초 실행 등) 초기 추정값으로 파일을 새로 생성.
기존 파일이 있고 이번에도 거래가 없으면 기존 값 그대로 유지.
"""
import os
import json
import requests
from datetime import datetime, timedelta, UTC

API_KEY  = os.environ["MOLIT_API_KEY"]
BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
LAWD_CD  = "11170"   # 서울 서대문구
APT_NAME = "홍제센트럴아이파크"
OUT_FILE = "re_prices.json"

# 우리집 기준 전용면적 (84㎡ 국민평형, ±5㎡ 허용)
TARGET_AREA  = 84.99
AREA_MARGIN  = 5.0

# 거래가 없을 때 조회 범위를 넓힐 개월 수 (직전 달 포함 총 6개월)
LOOKBACK_MONTHS = 6

# 실거래 데이터가 전혀 없을 때 사용할 초기 추정값 (financial-forecast.jsx 기준)
FALLBACK_PRICE = 1_400_000_000


def fetch_month(ym: str) -> list[dict]:
    """YYYYMM 월의 서대문구 전체 아파트 거래 목록 반환"""
    params = {
        "serviceKey": API_KEY,
        "LAWD_CD":    LAWD_CD,
        "DEAL_YMD":   ym,
        "numOfRows":  1000,
        "pageNo":     1,
        "_type":      "json",
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    body  = resp.json().get("response", {}).get("body", {})
    items = body.get("items", {})
    if not items:
        return []
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]
    return item_list


def parse_trades(items: list[dict]) -> list[dict]:
    """홍제센트럴아이파크 거래만 필터링해 정규화 반환"""
    trades = []
    for it in items:
        if APT_NAME not in str(it.get("아파트", "")):
            continue
        try:
            amount = int(str(it.get("거래금액", "0")).replace(",", "")) * 10_000  # 만원→원
            area   = float(str(it.get("전용면적", "0")))
        except ValueError:
            continue
        yy = str(it.get("년", ""))
        mm = str(it.get("월", "")).zfill(2)
        trades.append({
            "amount":    amount,
            "area":      area,
            "dealDate":  f"{yy}-{mm}",
            "dealDay":   str(it.get("일", "")).zfill(2),
            "floor":     str(it.get("층", "")),
        })
    return trades


def best_trade(trades: list[dict]) -> dict | None:
    """84㎡±5에 가장 가까운 거래 1건, 없으면 임의 최신 1건"""
    if not trades:
        return None
    near = [t for t in trades if abs(t["area"] - TARGET_AREA) <= AREA_MARGIN]
    return near[0] if near else trades[0]


def find_recent_trade(start_month: datetime) -> dict | None:
    """start_month부터 과거로 최대 LOOKBACK_MONTHS개월 범위에서 가장 최근 거래를 찾는다"""
    for i in range(LOOKBACK_MONTHS):
        # start_month 기준으로 정확히 i개월 전 달을 계산
        target = start_month.replace(day=1)
        for _ in range(i):
            target = (target - timedelta(days=1)).replace(day=1)
        ym = target.strftime("%Y%m")

        print(f"▶ {ym} 실거래가 조회 중...")
        items  = fetch_month(ym)
        trades = parse_trades(items)
        trade  = best_trade(trades)
        if trade:
            return trade
    return None


def write_output(price: int, price_source: str, deal_date: str | None, now: datetime):
    output = {
        "apt": {
            "name":        APT_NAME,
            "price":       price,
            "priceSource": price_source,
            "dealDate":    deal_date,
            "updatedAt":   now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        }
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def main():
    now = datetime.now(UTC) + timedelta(hours=9)   # KST

    # 직전 달부터 시작해 최대 LOOKBACK_MONTHS개월 범위에서 최근 거래 탐색
    prev_month = now.replace(day=1) - timedelta(days=1)
    trade = find_recent_trade(prev_month)

    if trade:
        write_output(
            price=trade["amount"],
            price_source="국토부실거래가",
            deal_date=trade["dealDate"],
            now=now,
        )
        price_str = f"{trade['amount'] // 10_000:,}만원"
        print(f"✅ {OUT_FILE} 저장 완료 — {trade['dealDate']} {trade['area']}㎡ {trade['floor']}층 {price_str}")
        return

    # 최근 LOOKBACK_MONTHS개월 내 실거래 없음
    if os.path.exists(OUT_FILE):
        print(f"⚠️  최근 {LOOKBACK_MONTHS}개월간 {APT_NAME} 거래 없음 — 기존 {OUT_FILE} 유지")
        return

    # 최초 실행 등으로 기존 파일이 없으면 초기 추정값으로 새로 생성
    print(f"⚠️  최근 {LOOKBACK_MONTHS}개월간 거래 없음 + 기존 {OUT_FILE} 없음 → 초기 추정값으로 생성")
    write_output(
        price=FALLBACK_PRICE,
        price_source="초기값(실거래 데이터 없음, 사용자 입력 기준)",
        deal_date=None,
        now=now,
    )
    print(f"✅ {OUT_FILE} 초기값으로 생성 완료 — {FALLBACK_PRICE // 10_000:,}만원")


if __name__ == "__main__":
    main()
