#!/usr/bin/env python3
import argparse
import csv
import io
import mimetypes
import os
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

import pymysql

LINKS_CSV_URL = (
    "https://raw.githubusercontent.com/"
    "vectorsss/movielens_100k_1m_extension/main/data/ml-1m/links_artificial.csv"
)

OG_IMAGE_RE = re.compile(r'<meta\s+property="og:image"\s+content="([^"]+)"', re.IGNORECASE)
TMDB_ID_RE = re.compile(r"/movie/(\d+)")
INVALID_TMDB_IDS = {"", "0", "-1", "none", "nan", "null"}

CONTENT_TYPE_TO_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/avif": "avif",
    "image/svg+xml": "svg",
}

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif", "avif", "svg"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Refill default local posters using TMDB")
    p.add_argument("--mysql-host", default=os.environ.get("MYSQL_HOST", "127.0.0.1"))
    p.add_argument("--mysql-port", type=int, default=int(os.environ.get("MYSQL_PORT", "3307")))
    p.add_argument("--mysql-user", default=os.environ.get("MYSQL_USER", "root"))
    p.add_argument("--mysql-pwd", default=os.environ.get("MYSQL_PWD", "xz20220429"))
    p.add_argument("--mysql-db", default=os.environ.get("MYSQL_DB", "movie_system"))
    p.add_argument("--poster-dir", default=os.environ.get("POSTER_DIR", str(Path.home() / ".movie-system" / "posters")))
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--limit", type=int, default=0, help="0 means all fallback rows")
    return p.parse_args()


def fetch_text(url: str, timeout: int = 20) -> str:
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


def fetch_bytes(url: str, timeout: int = 20) -> tuple[bytes, str | None]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.themoviedb.org/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        data = resp.read()
    return data, ctype


def parse_links_map(content: str) -> dict[int, dict[str, str]]:
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


def fetch_tmdb_poster_by_id(tmdb_id: str, timeout: int) -> str | None:
    if not tmdb_id or tmdb_id.lower() in INVALID_TMDB_IDS:
        return None
    try:
        html = fetch_text(f"https://www.themoviedb.org/movie/{tmdb_id}", timeout=timeout)
    except Exception:
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

    queries: list[str] = []
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


def search_tmdb_ids(query: str, timeout: int) -> list[str]:
    if not query:
        return []
    q = urllib.parse.quote_plus(query)
    url = f"https://www.themoviedb.org/search/movie?query={q}"
    try:
        html = fetch_text(url, timeout=timeout)
    except Exception:
        return []

    ids: list[str] = []
    seen = set()
    for m in TMDB_ID_RE.finditer(html):
        tid = m.group(1)
        if tid in seen:
            continue
        seen.add(tid)
        ids.append(tid)
    return ids


def fetch_tmdb_poster_by_title(title: str, timeout: int) -> str | None:
    for query in build_title_queries(title):
        for tid in search_tmdb_ids(query, timeout=timeout):
            url = fetch_tmdb_poster_by_id(tid, timeout=timeout)
            if url:
                return url
    return None


def detect_ext(content_type: str | None, url: str) -> str:
    if content_type in CONTENT_TYPE_TO_EXT:
        return CONTENT_TYPE_TO_EXT[content_type]
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower().lstrip(".")
    if ext in ALLOWED_EXT:
        return "jpg" if ext == "jpeg" else ext
    guessed, _ = mimetypes.guess_type(url)
    if guessed in CONTENT_TYPE_TO_EXT:
        return CONTENT_TYPE_TO_EXT[guessed]
    return "jpg"


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="poster_", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with tmp_path.open("wb") as f:
            f.write(data)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def main() -> None:
    args = parse_args()
    poster_dir = Path(args.poster_dir).expanduser().resolve()
    poster_dir.mkdir(parents=True, exist_ok=True)

    print("Loading TMDB links map...")
    links_map = parse_links_map(fetch_text(LINKS_CSV_URL, timeout=args.timeout))

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
        with conn.cursor() as cur:
            sql = "SELECT id, title FROM movie WHERE poster_url = '/posters/default.svg' ORDER BY id"
            if args.limit > 0:
                sql += f" LIMIT {int(args.limit)}"
            cur.execute(sql)
            rows = cur.fetchall()

        print(f"Fallback rows to process: {len(rows)}")

        updates: list[tuple[str, int]] = []
        fixed = 0
        failed = 0

        for idx, row in enumerate(rows, start=1):
            movie_id = int(row[0])
            title = row[1] or ""

            meta = links_map.get(movie_id, {})
            poster_remote = fetch_tmdb_poster_by_id(meta.get("tmdb_id", ""), timeout=args.timeout)
            if not poster_remote:
                poster_remote = fetch_tmdb_poster_by_title(meta.get("title") or title, timeout=args.timeout)

            if not poster_remote:
                failed += 1
                continue

            try:
                data, ctype = fetch_bytes(poster_remote, timeout=args.timeout)
                if not data:
                    raise ValueError("empty bytes")
                if ctype and not ctype.startswith("image/"):
                    raise ValueError(f"non-image: {ctype}")

                ext = detect_ext(ctype, poster_remote)
                target = poster_dir / f"{movie_id}.{ext}"
                write_atomic(target, data)

                for old in poster_dir.glob(f"{movie_id}.*"):
                    if old != target and old.is_file():
                        old.unlink(missing_ok=True)

                updates.append((f"/posters/{target.name}", movie_id))
                fixed += 1
            except Exception:
                failed += 1

            if idx % 100 == 0 or idx == len(rows):
                print(f"Processed: {idx}/{len(rows)}, fixed={fixed}, failed={failed}")

        if updates:
            with conn.cursor() as cur:
                cur.executemany("UPDATE movie SET poster_url = %s WHERE id = %s", updates)
            conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM movie WHERE poster_url='/posters/default.svg'")
            remain = int(cur.fetchone()[0])

        print(f"Fixed this run: {fixed}")
        print(f"Remaining fallback: {remain}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
