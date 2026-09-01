"""Prototype scraper for 光點台北 SPOT Taipei (spot.org.tw).

Old-school nested-table HTML, hand-published per listing page. No JSON-LD,
no JS rendering, no anti-bot signs (see SOURCES.md) — plain HTTP +
BeautifulSoup is enough. The homepage links out to the currently-active
listing pages (e.g. /movies/202608/m7/movies202608_m7.html); each page
holds one or more film blocks with a schedule table.
"""
import json
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE = "https://www.spot.org.tw"
UA = "Mozilla/5.0 (research prototype; contact: v61265@gmail.com)"
LISTING_PAGE_RE = re.compile(r"/movies/\d{6}/m\d/movies\d{6}_m\d\.html")
DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})")
FILM_YEAR_RE = re.compile(r"^(19|20)\d{2}(?=\s*\|)")


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def list_current_pages() -> list[str]:
    html = fetch(f"{BASE}/")
    paths = sorted(set(LISTING_PAGE_RE.findall(html)))
    return [f"{BASE}{p}" for p in paths]


def parse_listing_page(url: str, year_hint: int) -> list[dict]:
    soup = BeautifulSoup(fetch(url), "html.parser")
    screenings = []

    for title_cell in soup.find_all("td", class_="movie_title"):
        raw_title = title_cell.get_text(strip=True)
        if not raw_title:
            continue

        eng_cell = title_cell.find_next(class_="movie_title_eng")
        original_title = eng_cell.get_text(strip=True) if eng_cell else None

        director_cell = title_cell.find_next("p", class_="movie_dir")
        director = director_cell.get_text(strip=True) if director_cell else None

        # the "2025 | Japanese | Color | Japan | 127min | ..." line
        meta_line = title_cell.find_next(
            string=lambda s: s and FILM_YEAR_RE.match(s.strip())
        )
        film_year = int(meta_line.strip()[:4]) if meta_line else None

        # schedule table is the next <table> after a "本片放映時刻" marker
        marker = title_cell.find_next(string=re.compile("本片放映時刻"))
        schedule_rows = []
        if marker:
            schedule_table = marker.find_parent("table").find_next("table")
            if schedule_table:
                for row in schedule_table.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all("td")]
                    if len(cells) == 2 and DATE_RE.match(cells[0]):
                        schedule_rows.append(cells)

        for date_str, time_str in schedule_rows:
            m, d = DATE_RE.match(date_str).groups()
            try:
                dt = datetime(year_hint, int(m), int(d),
                               *map(int, time_str.split(":")))
            except ValueError:
                continue
            screenings.append(
                {
                    "cinema_id": "spot-taipei",
                    "cinema_name": "光點台北",
                    "chain": None,
                    "is_indie": True,
                    "raw_title": raw_title,
                    "original_title": original_title,
                    "director": director,
                    "film_year": film_year,
                    "datetime_start": dt.isoformat(),
                    "booking_url": None,
                    "booking_platform": "onsite",
                    "source_page": url,
                    "source": "spot.org.tw",
                }
            )
    return screenings


def main():
    pages = list_current_pages()
    print(f"found {len(pages)} active listing pages")

    all_screenings = []
    for url in pages:
        year_hint = int(re.search(r"movies/(\d{4})", url).group(1))
        screenings = parse_listing_page(url, year_hint)
        print(f"  {url}: {len(screenings)} screenings")
        all_screenings.extend(screenings)

    out = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "spot.org.tw",
        "count": len(all_screenings),
        "screenings": all_screenings,
    }
    out_path = "data/spot_taipei_screenings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(all_screenings)} screenings to {out_path}")


if __name__ == "__main__":
    main()
