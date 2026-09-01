"""Prototype scraper for 真善美劇院 台北 (wonderful.movie.com.tw).

The movie detail page (/movie/inner?id=X) is server-rendered but doesn't
carry showtimes. Those live in a separate server-rendered fragment route
used for the "時刻查詢" lightbox popup: /lightbox/index?id=X. Both are
plain HTTP, no headless browser needed.

Booking goes through a third-party platform (ezding.com.tw), with a
direct per-cinema booking link embedded in the lightbox fragment.

Taipei branch only — 台南真善美劇院 runs on a separate domain
(tainanwonderful.movie.com.tw) with (presumably) the same structure and
would need its own pass to confirm.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE = "https://wonderful.movie.com.tw"
UA = "Mozilla/5.0 (research prototype; contact: v61265@gmail.com)"
MOVIE_ID_RE = re.compile(r"/movie/inner\?id=(\d+)")
DATE_RE = re.compile(r"(\d{2})\s*/\s*(\d{2})")


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def list_movie_ids() -> list[str]:
    html = fetch(f"{BASE}/")
    return sorted(set(MOVIE_ID_RE.findall(html)), key=int)


def get_movie_meta(movie_id: str) -> dict:
    """Title plus whatever's in the label/value info list (導演, 上映日期, ...)."""
    soup = BeautifulSoup(fetch(f"{BASE}/movie/inner?id={movie_id}"), "html.parser")
    h2 = soup.find("h2", class_="page-title-1")
    title = h2.get_text(strip=True) if h2 else None

    info = {}
    for row in soup.select("ul.list_info li.row"):
        label = row.find("div", class_="label_block")
        value = row.find("div", class_="content_block")
        if not label or not value:
            continue
        key = re.sub(r"[\s　：:]+", "", label.get_text())
        info[key] = value.get_text(strip=True)

    film_year = None
    release_date = info.get("上映日期")
    if release_date:
        year_match = re.match(r"(\d{4})", release_date)
        film_year = int(year_match.group(1)) if year_match else None

    return {"title": title, "director": info.get("導演"), "film_year": film_year}


def get_screenings(movie_id: str, title: str, director: str | None, film_year: int | None, year_hint: int) -> list[dict]:
    soup = BeautifulSoup(fetch(f"{BASE}/lightbox/index?id={movie_id}"), "html.parser")

    booking_link = soup.find("a", class_="btn_buy")
    booking_url = booking_link["href"] if booking_link else None

    screenings = []
    for block in soup.find_all("ul", class_="time_list"):
        date_li = block.find("li", class_="time")
        if not date_li:
            continue
        date_match = DATE_RE.search(date_li.get_text())
        if not date_match:
            continue
        month, day = map(int, date_match.groups())

        for li in block.find_all("li"):
            if li is date_li:
                continue
            time_str = li.get_text(strip=True)
            if not re.match(r"^\d{1,2}:\d{2}$", time_str):
                continue
            hh, mm = map(int, time_str.split(":"))
            dt = datetime(year_hint, month, day, hh, mm)
            screenings.append(
                {
                    "cinema_id": "wonderful-taipei",
                    "cinema_name": "真善美劇院（台北）",
                    "chain": None,
                    "is_indie": True,
                    "raw_title": title,
                    "director": director,
                    "film_year": film_year,
                    "datetime_start": dt.isoformat(),
                    "booking_url": booking_url,
                    "booking_platform": "ezding",
                    "source": "wonderful.movie.com.tw",
                }
            )
    return screenings


def main():
    movie_ids = list_movie_ids()
    print(f"found {len(movie_ids)} movies")

    year_hint = datetime.now().year
    all_screenings = []
    for movie_id in movie_ids:
        meta = get_movie_meta(movie_id)
        if not meta["title"]:
            print(f"  id={movie_id}: no title found, skipping")
            continue
        screenings = get_screenings(
            movie_id, meta["title"], meta["director"], meta["film_year"], year_hint
        )
        print(f"  {meta['title']}: {len(screenings)} screenings")
        all_screenings.extend(screenings)

    out = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "wonderful.movie.com.tw",
        "count": len(all_screenings),
        "screenings": all_screenings,
    }
    out_path = "data/wonderful_taipei_screenings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(all_screenings)} screenings to {out_path}")


if __name__ == "__main__":
    main()
