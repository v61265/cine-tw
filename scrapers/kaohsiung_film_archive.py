"""Prototype scraper for 高雄市電影館 (kfa.kcg.gov.tw).

Plain server-rendered HTML, a straightforward <table> for the schedule
(場次日期/放映時間/放映地點/售票金額) with a direct booking link to a
third-party ticketing system (ticket.com.tw). No headless browser needed.

Note: requests must follow redirects (the bare domain 404s without the
`/tw/` path redirect).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE = "https://kfa.kcg.gov.tw"
UA = "Mozilla/5.0 (research prototype; contact: v61265@gmail.com)"
MOVIE_LINK_RE = re.compile(r"/tw/movies-content/[a-zA-Z0-9]+")
DATE_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def list_movie_urls() -> list[str]:
    html = fetch(f"{BASE}/tw/now-showing")
    paths = sorted(set(MOVIE_LINK_RE.findall(html)))
    return [f"{BASE}{p}" for p in paths]


def parse_movie_page(url: str) -> list[dict]:
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = None
    if title_tag:
        parts = title_tag.get_text().split("|")
        title = parts[-1].strip() if parts else None

    table = soup.find("table", class_="film-price__table")
    if not table:
        return []

    booking_link = soup.find("a", href=re.compile(r"ticket\.com\.tw"))
    booking_url = booking_link["href"] if booking_link else None

    screenings = []
    for row in table.find("tbody").find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cells) < 3:
            continue
        date_str, time_str, venue = cells[0], cells[1], cells[2]
        date_match = DATE_RE.match(date_str)
        if not date_match or not re.match(r"^\d{1,2}:\d{2}$", time_str):
            continue
        year, month, day = map(int, date_match.groups())
        hh, mm = map(int, time_str.split(":"))
        dt = datetime(year, month, day, hh, mm)
        screenings.append(
            {
                "cinema_id": "kaohsiung-film-archive",
                "cinema_name": "高雄市電影館",
                "venue": venue,
                "chain": None,
                "is_indie": True,
                "raw_title": title,
                "datetime_start": dt.isoformat(),
                "booking_url": booking_url,
                "booking_platform": "ticket.com.tw",
                "source": "kfa.kcg.gov.tw",
            }
        )
    return screenings


def main():
    movie_urls = list_movie_urls()
    print(f"found {len(movie_urls)} movies")

    all_screenings = []
    for url in movie_urls:
        screenings = parse_movie_page(url)
        title = screenings[0]["raw_title"] if screenings else "?"
        print(f"  {title}: {len(screenings)} screenings")
        all_screenings.extend(screenings)

    out = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "kfa.kcg.gov.tw",
        "count": len(all_screenings),
        "screenings": all_screenings,
    }
    out_path = "data/kaohsiung_film_archive_screenings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(all_screenings)} screenings to {out_path}")


if __name__ == "__main__":
    main()
