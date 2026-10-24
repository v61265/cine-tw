"""國家電影及視聽文化中心 (TFAI) screenings, via the 文化部 open-data API.

TFAI's own site (tfai.org.tw) sits behind a Cloudflare bot check, so it's
not scraped (see SOURCES.md). Its programme is, however, published as
government open data: the 全國藝文活動資訊系統 API (data.gov.tw dataset
6010, category 8 = 電影), which is meant to be consumed by third parties.
Each record carries per-session times, the 新莊 venue (大影格 / 小影格),
and a direct OPENTIX booking link — no browser tricks involved.

The same feed also lists other film venues (光點華山, 府中15, festival
screenings, ...); this scraper deliberately takes TFAI only for now.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

API_URL = "https://cloud.culture.tw/frontsite/trans/SearchShowAction.do?method=doFindTypeJ&category=8"
UA = "Mozilla/5.0 (research prototype; contact: v61265@gmail.com)"
VENUE_KEY = "國家電影及視聽文化中心"


def fetch_records() -> list[dict]:
    req = Request(API_URL, headers={"User-Agent": UA})
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse(records: list[dict]) -> list[dict]:
    screenings = []
    for rec in records:
        for session in rec.get("showInfo", []):
            venue_name = session.get("locationName") or ""
            if VENUE_KEY not in venue_name:
                continue
            dt = datetime.strptime(session["time"], "%Y/%m/%d %H:%M:%S")
            screenings.append(
                {
                    "cinema_id": "tfai-xinzhuang",
                    "cinema_name": "國家電影及視聽文化中心",
                    "cinema_address": session.get("location"),
                    "venue": venue_name.split("-", 1)[-1],  # 大影格 / 小影格
                    "chain": None,
                    "is_indie": True,
                    "raw_title": rec["title"],
                    "datetime_start": dt.isoformat(),
                    "booking_url": rec.get("webSales") or rec.get("sourceWebPromote") or None,
                    "booking_platform": "opentix",
                    "source": "cloud.culture.tw",
                }
            )
    return screenings


def main():
    records = fetch_records()
    print(f"fetched {len(records)} film-category records")
    screenings = parse(records)
    print(f"{len(screenings)} TFAI sessions")

    out = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "cloud.culture.tw",
        "count": len(screenings),
        "screenings": screenings,
    }
    out_path = "data/tfai_screenings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(screenings)} screenings to {out_path}")


if __name__ == "__main__":
    main()
