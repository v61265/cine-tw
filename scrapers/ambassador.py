"""Prototype scraper for 國賓影城 (ambassador.com.tw).

Stage 0 research flagged this as "AJAX-rendered, needs a headless
browser" — that turned out to be wrong (an escaping mistake: the movie
links use a literal `&`, not `&amp;`, so a naive regex missed them). The
homepage and the per-movie schedule page (/home/MovieContent?MID=..&DT=..)
are both plain server-rendered HTML. No headless browser needed here
either.

Flow: scrape the homepage for the list of currently-showing movies (GUID
+ title), then for each movie x each of the next N days, fetch its
MovieContent page and parse the theater-box blocks (one per cinema
branch, nationwide chain).
"""
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE = "https://www.ambassador.com.tw"
UA = "Mozilla/5.0 (research prototype; contact: v61265@gmail.com)"
DAYS_AHEAD = 7

MOVIE_LINK_RE = re.compile(
    r"class='title'><h6><a href='/home/MovieContent\?MID=([a-f0-9-]{36})&DT=[0-9/]{10}'>([^<]+)</a>"
)


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def list_current_movies() -> dict[str, str]:
    html = fetch(f"{BASE}/")
    return dict((mid, title) for mid, title in MOVIE_LINK_RE.findall(html))


def parse_movie_day(movie_id: str, title: str, date: datetime) -> list[dict]:
    dt_param = date.strftime("%Y/%m/%d")
    url = f"{BASE}/home/MovieContent?MID={movie_id}&DT={dt_param}"
    soup = BeautifulSoup(fetch(url), "html.parser")

    screenings = []
    for box in soup.find_all("div", class_="theater-box"):
        h3 = box.find("h3")
        if not h3:
            continue
        cinema_link = h3.find("a")
        cinema_name = cinema_link.get_text(strip=True) if cinema_link else None
        cinema_id_match = re.search(r"ID=([a-f0-9-]{36})", cinema_link["href"]) if cinema_link else None
        cinema_id = cinema_id_match.group(1) if cinema_id_match else None
        spans = h3.find_all("span")
        address = spans[0].get_text(strip=True) if spans else None

        format_tag = box.find("p", class_="tag-seat")
        format_raw = format_tag.get_text(strip=True) if format_tag else None

        for li in box.find_all("li"):
            h6 = li.find("h6")
            if not h6:
                continue
            time_str = h6.get_text(strip=True)
            try:
                hh, mm = map(int, time_str.split(":"))
            except ValueError:
                continue
            dt = date.replace(hour=hh, minute=mm, second=0, microsecond=0)
            screenings.append(
                {
                    "cinema_id": f"ambassador-{cinema_id}",
                    "cinema_name": cinema_name,
                    "cinema_address": address,
                    "chain": "ambassador",
                    "is_indie": False,
                    "raw_title": title,
                    "format_raw": format_raw,
                    "datetime_start": dt.isoformat(),
                    "booking_url": f"{BASE}/home/Showtime?ID={cinema_id}&DT={dt_param}" if cinema_id else None,
                    "booking_platform": "self",
                    "source": "ambassador.com.tw",
                }
            )
    return screenings


def main():
    movies = list_current_movies()
    print(f"found {len(movies)} currently-showing movies")

    today = datetime.now()
    dates = [today + timedelta(days=i) for i in range(DAYS_AHEAD)]

    all_screenings = []
    for movie_id, title in movies.items():
        movie_count = 0
        for date in dates:
            try:
                screenings = parse_movie_day(movie_id, title, date)
                movie_count += len(screenings)
                all_screenings.extend(screenings)
            except Exception as exc:
                print(f"  {title} {date.date()}: FAILED ({exc})")
            time.sleep(0.5)
        print(f"  {title}: {movie_count} screenings across {DAYS_AHEAD} days")

    out = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "ambassador.com.tw",
        "count": len(all_screenings),
        "screenings": all_screenings,
    }
    out_path = "data/ambassador_screenings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(all_screenings)} screenings to {out_path}")


if __name__ == "__main__":
    main()
