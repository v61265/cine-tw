"""NOT PRODUCTION-READY — see caveat below.

Each screening is embedded as a schema.org ScreeningEvent JSON-LD block
directly in the server-rendered HTML. That part of the pipeline (fetch ->
extract JSON-LD -> normalize -> write JSON) works and is exercised end to
end by this script.

However: the JSON-LD is stale SEO fallback content baked into the static
HTML shell, not live data. Verified 2026-09-01 — a real browser hitting
the same cinema pages shows "目前沒有可預訂的場次" (no bookable screenings)
across multiple branches, fetched via the site's real API at
capi.showtimes.com.tw, while curl/this script's plain HTTP request still
returns a full week of screenings frozen at 2026-08-24. The live API
distinguishes automated clients from real browsers and serves them
different data.

Getting current data would require passing that bot detection, which is
the same category of risk we're deliberately avoiding for 威秀/新光/誠品
(see SOURCES.md). So this source is parked pending an official data
partnership conversation, not patched to evade detection. Kept here as a
reference implementation of the JSON-LD extraction pattern in case a
future source uses the same technique honestly.
"""
import json
import re
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

BASE = "https://www.showtimes.com.tw"
UA = "Mozilla/5.0 (research prototype; contact: v61265@gmail.com)"
JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">(\{"@context":"https://schema\.org","@type":"ScreeningEvent".*?\})</script>'
)
CINEMA_ID_RE = re.compile(r'href="/cinemas/(\d+)/?"')


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def list_cinema_ids() -> list[str]:
    html = fetch(f"{BASE}/cinemas/")
    return sorted(set(CINEMA_ID_RE.findall(html)), key=int)


def parse_cinema_page(cinema_id: str) -> list[dict]:
    html = fetch(f"{BASE}/cinemas/{cinema_id}/")
    events = [json.loads(m) for m in JSONLD_RE.findall(html)]

    screenings = []
    for e in events:
        loc = e.get("location", {})
        screenings.append(
            {
                "cinema_id": f"showtime-{cinema_id}",
                "cinema_name": loc.get("name"),
                "cinema_address": loc.get("address"),
                "chain": "showtime",
                "is_indie": False,
                "raw_title": e.get("name"),
                "datetime_start": e.get("startDate"),
                "format_raw": e.get("videoFormat"),
                "booking_url": e.get("url"),
                "booking_platform": "self",
                "source": "showtimes.com.tw",
            }
        )
    return screenings


def main():
    cinema_ids = list_cinema_ids()
    print(f"found {len(cinema_ids)} cinemas: {cinema_ids}")

    all_screenings = []
    for cid in cinema_ids:
        try:
            screenings = parse_cinema_page(cid)
            print(f"  cinema {cid}: {len(screenings)} screenings")
            all_screenings.extend(screenings)
        except Exception as exc:
            print(f"  cinema {cid}: FAILED ({exc})")
        time.sleep(1)  # be polite

    out = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "showtimes.com.tw",
        "count": len(all_screenings),
        "screenings": all_screenings,
    }
    out_path = "data/showtime_screenings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(all_screenings)} screenings to {out_path}")


if __name__ == "__main__":
    main()
