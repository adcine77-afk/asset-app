"""
국토교통부 아파트매매 실거래자료 API → re_prices.json
홍제센트럴아이파크 (서대문구 LAWD_CD: 11170) 직전 달 실거래가 수집

출력 형식:
{
  "apt": {
    "name": "홍제센트럴아이파크",
    "price": 1480000000,          # 원 단위
    "priceSource": "국토부실거래가",
    "dealDate": "2026-05",        # YYYY-MM
    "updatedAt": "2026-06-01T09:00:00+09:00"
  }
}

거래 없는 달: 기존 re_prices.json 값 유지 (덮어쓰지 않음)
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta

API_KEY  = os.environ["MOLIT_API_KEY"]
BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
LAWD_CD  = "11170"   # 서울 서대문구
APT_NAME = "홍제센트럴아이파크"
OUT_FILE = "re_prices.json"

# 우리집 기준 전용면적 (84㎡ 국민평형, ±5㎡ 허용)
TARGET_AREA  = 84.99
AREA_MARGIN  = 5.0


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


def main():
    now = datetime.utcnow() + timedelta(hours=9)   # KST

    # 직전 달 YYYYMM (매월 1일 실행이므로 당월 데이터는 아직 없음)
    first_of_month = now.replace(day=1)
    prev_month = (first_of_month - timedelta(days=1))
    ym = prev_month.strftime("%Y%m")

    print(f"▶ {ym} 실거래가 조회 중...")
    items  = fetch_month(ym)
    trades = parse_trades(items)
    trade  = best_trade(trades)

    if trade is None:
        print(f"⚠️  {ym} 홍제센트럴아이파크 거래 없음 — 기존 {OUT_FILE} 유지")
        sys.exit(0)   # 파일 건드리지 않고 종료

    output = {
        "apt": {
            "name":        APT_NAME,
            "price":       trade["amount"],
            "priceSource": "국토부실거래가",
            "dealDate":    trade["dealDate"],
            "area":        trade["area"],
            "floor":       trade["floor"],
            "updatedAt":   now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        }
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    price_str = f"{trade['amount'] // 10_000:,}만원"
    print(f"✅ {OUT_FILE} 저장 완료 — {trade['dealDate']} {trade['area']}㎡ {trade['floor']}층 {price_str}")


if __name__ == "__main__":
    main()
