"""Merge the per-source scraper outputs into the unified schema.

Reads data/<source>_screenings.json for every trusted source (see
SOURCE_FILES — 秀泰's output is intentionally excluded, see SOURCES.md)
and writes three normalized tables to data/normalized/:

- cinemas.json:   cinema_id -> {name, chain, is_indie, address}
- films.json:     film_id   -> {normalized_title, raw_titles seen, sources}
- screenings.json: flat list of {film_id, cinema_id, datetime_start,
                    format_raw, booking_url, booking_platform, source}

Title matching is intentionally simple for this MVP pass: strip
leading/trailing bracketed tags (language/format markers like "（國語）"
or "（DBOX特別場）"), strip a trailing English title appended without a
separator (e.g. 高雄市電影館 titles like "橡樹街末日 The End of Oak
Street"), and collapse whitespace. This is a heuristic, not a proper
bilingual-title parser — it can misfire on a title that's genuinely
Latin-only or ends with a Latin proper noun. Fine for now; revisit if it
causes visible mis-merges in the frontend.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
# public/ (not data/) so CI can commit the merged output for the frontend
# to fetch, while raw per-source scrapes in data/ stay gitignored.
OUT_DIR = ROOT / "public" / "data"

# 秀泰 (showtime_screenings.json) deliberately excluded — see SOURCES.md.
SOURCE_FILES = [
    "spot_taipei_screenings.json",
    "ambassador_screenings.json",
    "wonderful_taipei_screenings.json",
    "kaohsiung_film_archive_screenings.json",
    "lux_cinema_screenings.json",
]

BRACKET_GROUP = r"[\(（][^\(\)（）]*[\)）]"
LEADING_BRACKETS = re.compile(rf"^(?:{BRACKET_GROUP}\s*)+")
TRAILING_BRACKETS = re.compile(rf"(?:\s*{BRACKET_GROUP})+$")
# A CJK char, then a space, then a Latin-starting tail running to the end —
# the "inline original title" pattern (no brackets, no other separator).
TRAILING_LATIN_TITLE = re.compile(
    r"^(.*[一-鿿぀-ヿ])\s+[A-Za-z][A-Za-z0-9 ,.:'’\-]*$"
)


def clean_title(raw: str) -> str:
    text = unicodedata.normalize("NFKC", raw)
    text = LEADING_BRACKETS.sub("", text)
    text = TRAILING_BRACKETS.sub("", text)
    match = TRAILING_LATIN_TITLE.match(text)
    if match:
        text = match.group(1)
    return re.sub(r"\s+", " ", text).strip()


def film_id_for(normalized_title: str) -> str:
    return hashlib.md5(normalized_title.encode("utf-8")).hexdigest()[:12]


def main():
    cinemas: dict[str, dict] = {}
    films: dict[str, dict] = {}
    screenings: list[dict] = []
    source_meta: dict[str, dict] = {}

    for filename in SOURCE_FILES:
        path = DATA_DIR / filename
        if not path.exists():
            print(f"skip (missing): {filename}")
            continue

        payload = json.loads(path.read_text(encoding="utf-8"))
        source_meta[payload["source"]] = {
            "scraped_at": payload["scraped_at"],
            "screening_count": payload["count"],
        }
        for s in payload["screenings"]:
            cinema_id = s["cinema_id"]
            cinemas.setdefault(
                cinema_id,
                {
                    "name": s.get("cinema_name"),
                    "chain": s.get("chain"),
                    "is_indie": s.get("is_indie"),
                    "address": s.get("cinema_address"),
                },
            )

            raw_title = s["raw_title"]
            normalized_title = clean_title(raw_title)
            fid = film_id_for(normalized_title)
            film = films.setdefault(
                fid,
                {"normalized_title": normalized_title, "raw_titles": [], "sources": []},
            )
            if raw_title not in film["raw_titles"]:
                film["raw_titles"].append(raw_title)
            if s["source"] not in film["sources"]:
                film["sources"].append(s["source"])

            screenings.append(
                {
                    "film_id": fid,
                    "cinema_id": cinema_id,
                    "datetime_start": s["datetime_start"],
                    "format_raw": s.get("format_raw"),
                    "booking_url": s.get("booking_url"),
                    "booking_platform": s.get("booking_platform"),
                    "source": s["source"],
                }
            )

        print(f"{filename}: {len(payload['screenings'])} screenings merged")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "cinemas.json").write_text(
        json.dumps(cinemas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "films.json").write_text(
        json.dumps(films, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "screenings.json").write_text(
        json.dumps(screenings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "meta.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sources": source_meta,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n{len(cinemas)} cinemas, {len(films)} distinct films, {len(screenings)} screenings")
    print(f"wrote to {OUT_DIR}")


if __name__ == "__main__":
    main()
