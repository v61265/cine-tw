"""Prototype scraper for 樂聲影城 LUX Cinema (luxcinema.com.tw).

Old-school PHP site (bare domain does a JS meta-refresh to /web — no
headless browser needed, just follow to that path directly). Schedule is
plain HTML; each showtime is its own booking link
(2020_sel_ticket.php?...&showtime=YYYY-MM-DD&sel_ticket_id=...) which
conveniently embeds the exact date, so no month/day-plus-year-guessing
needed. This gives the most precise direct-to-showtime booking link of
any source scraped so far.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE = "https://www.luxcinema.com.tw/web"
UA = "Mozilla/5.0 (research prototype; contact: v61265@gmail.com)"
FILM_ID_RE = re.compile(r"2020-movie_item\.php\?film_id=(\d+)")
SHOWTIME_LINK_RE = re.compile(r"showtime=(\d{4}-\d{2}-\d{2})")


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def list_film_ids() -> list[str]:
    html = fetch(f"{BASE}/2020.php?type=ShowTimes")
    ids = set(FILM_ID_RE.findall(html))
    if not ids:
        html = fetch(BASE)
        ids = set(FILM_ID_RE.findall(html))
    return sorted(ids, key=int)


def parse_film_page(film_id: str) -> list[dict]:
    soup = BeautifulSoup(fetch(f"{BASE}/2020-movie_item.php?film_id={film_id}"), "html.parser")

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else None
    h3 = h1.find_next("h3") if h1 else None
    original_title = h3.get_text(strip=True) if h3 else None

    screenings = []
    for a in soup.find_all("a", href=SHOWTIME_LINK_RE):
        date_match = SHOWTIME_LINK_RE.search(a["href"])
        time_str = a.get_text(strip=True)
        if not date_match or not re.match(r"^\d{1,2}:\d{2}$", time_str):
            continue
        date_str = date_match.group(1)
        hh, mm = map(int, time_str.split(":"))
        dt = datetime.fromisoformat(date_str).replace(hour=hh, minute=mm)
        booking_url = f"{BASE}/{a['href']}"
        screenings.append(
            {
                "cinema_id": "lux-cinema",
                "cinema_name": "樂聲影城",
                "chain": None,
                "is_indie": True,
                "raw_title": title,
                "original_title": original_title,
                "datetime_start": dt.isoformat(),
                "booking_url": booking_url,
                "booking_platform": "self",
                "source": "luxcinema.com.tw",
            }
        )
    return screenings


def main():
    film_ids = list_film_ids()
    print(f"found {len(film_ids)} films")

    all_screenings = []
    for film_id in film_ids:
        screenings = parse_film_page(film_id)
        title = screenings[0]["raw_title"] if screenings else "?"
        print(f"  {title}: {len(screenings)} screenings")
        all_screenings.extend(screenings)

    out = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "luxcinema.com.tw",
        "count": len(all_screenings),
        "screenings": all_screenings,
    }
    out_path = "data/lux_cinema_screenings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(all_screenings)} screenings to {out_path}")


if __name__ == "__main__":
    main()
