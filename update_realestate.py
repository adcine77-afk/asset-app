"""
국토교통부 아파트매매 실거래자료 API → re_prices.json
홍제센트럴아이파크 (서대문구 LAWD_CD: 11170) 최근 3개월치 수집
"""
import os
import json
import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

API_KEY  = os.environ["MOLIT_API_KEY"]
BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
LAWD_CD  = "11170"  # 서울 서대문구
APT_NAME = "홍제센트럴아이파크"

def fetch_month(ym: str) -> list[dict]:
    """ym: YYYYMM"""
    params = {
        "serviceKey": API_KEY,
        "LAWD_CD": LAWD_CD,
        "DEAL_YMD": ym,
        "numOfRows": 1000,
        "pageNo": 1,
        "_type": "json",
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    body = resp.json().get("response", {}).get("body", {})
    items = body.get("items", {})
    if not items:
        return []
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]
    return item_list

def main():
    now = datetime.utcnow() + timedelta(hours=9)  # KST
    months = [(now - relativedelta(months=i)).strftime("%Y%m") for i in range(3)]

    trades = []
    for ym in months:
        items = fetch_month(ym)
        for it in items:
            name = str(it.get("아파트", "")).strip()
            if APT_NAME in name:
                amount_str = str(it.get("거래금액", "0")).replace(",", "").strip()
                area_str   = str(it.get("전용면적", "0")).strip()
                try:
                    amount = int(amount_str) * 10000  # 만원 → 원
                    area   = float(area_str)
                except ValueError:
                    continue
                deal_date = f"{it.get('년','')}-{str(it.get('월','')).zfill(2)}-{str(it.get('일','')).zfill(2)}"
                floor     = it.get("층", "")
                trades.append({
                    "date":   deal_date,
                    "area":   area,
                    "amount": amount,
                    "floor":  floor,
                    "name":   name,
                })

    # 가장 최근 거래부터 정렬
    trades.sort(key=lambda x: x["date"], reverse=True)

    # 우리집 면적(84㎡ 기준)에 가장 가까운 최신 거래 1건을 기준가로
    target_area = 84.99  # 홍제센트럴아이파크 국민평형 (실면적)
    best = None
    for t in trades:
        if abs(t["area"] - target_area) < 5:
            best = t
            break
    if best is None and trades:
        best = trades[0]

    output = {
        "updated": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "apt": {
            "name":      APT_NAME,
            "lawd_cd":   LAWD_CD,
            "reference": best,
            "recent":    trades[:10],
        }
    }

    with open("re_prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ re_prices.json 저장 완료 — 기준가: {best}")

if __name__ == "__main__":
    main()
