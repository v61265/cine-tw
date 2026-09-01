"""Fill in missing director/year on films.json using the TMDB API.

Only touches films that don't already have a director or year from their
own source scrape — TMDB is a fallback, not an override, since a source's
own listing (when it has one) usually has better Chinese-localized
director names than TMDB's translation.

Needs a TMDB API key (v4 read access token) in the TMDB_API_KEY env var.
Get one free at https://www.themoviedb.org/settings/api — this is a
legitimate public API meant for exactly this kind of lookup, unlike
scraping an aggregator site (see SOURCES.md for why we don't do that).

Run after pipeline/normalize.py:
    TMDB_API_KEY=... python3 pipeline/enrich_tmdb.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
FILMS_PATH = ROOT / "public" / "data" / "films.json"
API_BASE = "https://api.themoviedb.org/3"
REQUEST_DELAY_SECONDS = 0.3


def tmdb_get(path: str, token: str, params: dict | None = None) -> dict:
    # Supports both TMDB auth styles: a v3 "API Key" (~32-char string) goes
    # as an api_key query param, a v4 "API Read Access Token" (long JWT) goes
    # as a Bearer header.
    params = dict(params or {})
    headers = {"Accept": "application/json"}
    if len(token) > 40:
        headers["Authorization"] = f"Bearer {token}"
    else:
        params["api_key"] = token

    url = f"{API_BASE}{path}"
    if params:
        url += f"?{urlencode(params)}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_movie(title: str, token: str) -> dict | None:
    result = tmdb_get("/search/movie", token, {"query": title, "language": "zh-TW"})
    hits = result.get("results") or []
    return hits[0] if hits else None


def get_director(movie_id: int, token: str) -> str | None:
    credits = tmdb_get(f"/movie/{movie_id}/credits", token, {"language": "zh-TW"})
    for person in credits.get("crew", []):
        if person.get("job") == "Director":
            return person.get("name")
    return None


def main():
    token = os.environ.get("TMDB_API_KEY")
    if not token:
        print("TMDB_API_KEY not set — get a free one at themoviedb.org/settings/api", file=sys.stderr)
        sys.exit(1)

    films = json.loads(FILMS_PATH.read_text(encoding="utf-8"))
    missing = {fid: f for fid, f in films.items() if not f["director"] or not f["year"]}
    print(f"{len(missing)}/{len(films)} films missing director and/or year")

    filled, no_match, errors = 0, 0, 0
    for fid, film in missing.items():
        query = film.get("original_title") or film["normalized_title"]
        try:
            movie = find_movie(query, token)
            if not movie:
                print(f"  no TMDB match: {film['normalized_title']} (queried {query!r})")
                no_match += 1
                continue

            if not film["year"] and movie.get("release_date"):
                film["year"] = int(movie["release_date"][:4])
            if not film["director"]:
                director = get_director(movie["id"], token)
                if director:
                    film["director"] = director
            film["tmdb_id"] = movie["id"]
            filled += 1
            print(f"  {film['normalized_title']} -> {film['director']}, {film['year']}")
        except Exception as exc:
            print(f"  ERROR on {film['normalized_title']}: {exc}")
            errors += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    FILMS_PATH.write_text(json.dumps(films, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nfilled {filled}, no match {no_match}, errors {errors}")
    print(f"wrote {FILMS_PATH}")


if __name__ == "__main__":
    main()
