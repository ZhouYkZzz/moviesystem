#!/usr/bin/env python3
import argparse
import csv
import io
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import pymysql

POSTERS_CSV_URL = (
    "https://raw.githubusercontent.com/"
    "vectorsss/movielens_100k_1m_extension/main/data/ml-1m/movie_posters.csv"
)
LINKS_CSV_URL = (
    "https://raw.githubusercontent.com/"
    "vectorsss/movielens_100k_1m_extension/main/data/ml-1m/links_artificial.csv"
)

OG_IMAGE_RE = re.compile(r'<meta\s+property="og:image"\s+content="([^"]+)"', re.IGNORECASE)
TMDB_ID_RE = re.compile(r"/movie/(\d+)")
INVALID_TMDB_IDS = {"", "0", "-1", "none", "nan", "null"}


def fetch_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_posters_csv(content: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",", 1)
        if len(parts) != 2:
            continue
        try:
            movie_id = int(parts[0])
        except ValueError:
            continue
        poster_url = parts[1].strip()
        if poster_url.startswith("http"):
            out[movie_id] = poster_url
    return out


def parse_links_csv(content: str) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        try:
            movie_id = int((row.get("movie_id") or "").strip())
        except ValueError:
            continue
        out[movie_id] = {
            "title": (row.get("title") or "").strip(),
            "tmdb_id": (row.get("tmdbId") or "").strip(),
        }
    return out


def extract_og_image(html: str) -> str | None:
    m = OG_IMAGE_RE.search(html)
    if not m:
        return None
    url = m.group(1).strip()
    return url if url.startswith("http") else None


def fetch_tmdb_poster_by_tmdb_id(tmdb_id: str, timeout: int = 30) -> str | None:
    if not tmdb_id or tmdb_id.lower() in INVALID_TMDB_IDS:
        return None
    try:
        html = fetch_text(f"https://www.themoviedb.org/movie/{tmdb_id}", timeout=timeout)
    except (urllib.error.URLError, TimeoutError):
        return None
    return extract_og_image(html)


def build_title_queries(title: str) -> list[str]:
    title = (title or "").strip()
    if not title:
        return []

    year_match = re.search(r"\((\d{4})\)\s*$", title)
    year = year_match.group(1) if year_match else ""

    base = re.sub(r"\((\d{4})\)\s*$", "", title).strip()
    no_paren = re.sub(r"\([^)]*\)", "", base).strip()

    variants = [base, no_paren]
    if ", The" in no_paren:
        variants.append("The " + no_paren.replace(", The", ""))
    if ", A" in no_paren:
        variants.append("A " + no_paren.replace(", A", ""))
    if ", An" in no_paren:
        variants.append("An " + no_paren.replace(", An", ""))

    queries = []
    for v in variants:
        v = " ".join(v.split())
        if not v:
            continue
        if v not in queries:
            queries.append(v)
        if year:
            with_year = f"{v} {year}"
            if with_year not in queries:
                queries.append(with_year)
    return queries


def search_tmdb_ids_by_query(query: str, timeout: int = 30) -> list[str]:
    if not query:
        return []
    q = urllib.parse.quote_plus(query)
    url = f"https://www.themoviedb.org/search/movie?query={q}"
    try:
        html = fetch_text(url, timeout=timeout)
    except (urllib.error.URLError, TimeoutError):
        return []

    ids = []
    seen = set()
    for match in TMDB_ID_RE.finditer(html):
        tmdb_id = match.group(1)
        if tmdb_id in seen:
            continue
        seen.add(tmdb_id)
        ids.append(tmdb_id)
    return ids


def fetch_tmdb_poster_by_title(title: str, timeout: int = 30) -> str | None:
    for query in build_title_queries(title):
        for tmdb_id in search_tmdb_ids_by_query(query, timeout=timeout):
            poster = fetch_tmdb_poster_by_tmdb_id(tmdb_id, timeout=timeout)
            if poster:
                return poster
    return None


def ensure_poster_column(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM movie LIKE 'poster_url'")
        exists = cur.fetchone()
        if exists:
            return
        cur.execute("ALTER TABLE movie ADD COLUMN poster_url VARCHAR(512) NULL")
    conn.commit()


def load_db_movie_ids(conn) -> set[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM movie")
        return {int(row[0]) for row in cur.fetchall()}


def update_posters(conn, poster_map: dict[int, str], batch_size: int = 500) -> int:
    rows = [(url, movie_id) for movie_id, url in poster_map.items() if url]
    if not rows:
        return 0

    with conn.cursor() as cur:
        for i in range(0, len(rows), batch_size):
            cur.executemany(
                "UPDATE movie SET poster_url = %s WHERE id = %s",
                rows[i : i + batch_size],
            )
    conn.commit()
    return len(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync MovieLens 1M posters into MySQL movie.poster_url")
    p.add_argument("--mysql-host", default=os.environ.get("MYSQL_HOST", "127.0.0.1"))
    p.add_argument("--mysql-port", type=int, default=int(os.environ.get("MYSQL_PORT", "3307")))
    p.add_argument("--mysql-user", default=os.environ.get("MYSQL_USER", "root"))
    p.add_argument("--mysql-pwd", default=os.environ.get("MYSQL_PWD", "xz20220429"))
    p.add_argument("--mysql-db", default=os.environ.get("MYSQL_DB", "movie_system"))
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--sleep", type=float, default=0.2)
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print("Downloading poster mappings...")
    posters_csv = fetch_text(POSTERS_CSV_URL, timeout=args.timeout)
    links_csv = fetch_text(LINKS_CSV_URL, timeout=args.timeout)
    poster_map = parse_posters_csv(posters_csv)
    links_map = parse_links_csv(links_csv)
    print(f"Poster rows from CSV: {len(poster_map)}")
    print(f"Link rows from CSV:   {len(links_map)}")

    conn = pymysql.connect(
        host=args.mysql_host,
        port=args.mysql_port,
        user=args.mysql_user,
        password=args.mysql_pwd,
        database=args.mysql_db,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.Cursor,
    )

    try:
        ensure_poster_column(conn)
        db_ids = load_db_movie_ids(conn)
        print(f"Movies in DB:         {len(db_ids)}")

        final_map = {mid: url for mid, url in poster_map.items() if mid in db_ids}
        missing_ids = sorted(db_ids - set(final_map.keys()))

        if missing_ids:
            print(f"Missing after CSV:    {len(missing_ids)}")

        from_tmdb_id = 0
        from_tmdb_search = 0
        unresolved = []

        for mid in missing_ids:
            meta = links_map.get(mid, {})
            title = meta.get("title", "")
            tmdb_id = meta.get("tmdb_id", "")

            poster_url = fetch_tmdb_poster_by_tmdb_id(tmdb_id, timeout=args.timeout)
            if poster_url:
                final_map[mid] = poster_url
                from_tmdb_id += 1
                time.sleep(args.sleep)
                continue

            poster_url = fetch_tmdb_poster_by_title(title, timeout=args.timeout)
            if poster_url:
                final_map[mid] = poster_url
                from_tmdb_search += 1
                time.sleep(args.sleep)
                continue

            unresolved.append((mid, title))
            time.sleep(args.sleep)

        print(f"Filled by TMDB ID:    {from_tmdb_id}")
        print(f"Filled by search:     {from_tmdb_search}")
        print(f"Unresolved:           {len(unresolved)}")
        if unresolved:
            for mid, title in unresolved:
                print(f"  - {mid}: {title}")

        coverage = len(final_map)
        print(f"Coverage to update:   {coverage}/{len(db_ids)}")

        if args.dry_run:
            print("Dry run enabled, no database updates written.")
            return

        updated = update_posters(conn, final_map, batch_size=args.batch_size)
        print(f"Rows updated:         {updated}")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM movie WHERE poster_url IS NOT NULL AND poster_url <> ''")
            non_empty = int(cur.fetchone()[0])
        print(f"Rows with poster_url: {non_empty}/{len(db_ids)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
