#!/usr/bin/env python3
import argparse
import mimetypes
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pymysql

DEFAULT_POSTER_SVG = """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"400\" height=\"600\" viewBox=\"0 0 400 600\" role=\"img\" aria-labelledby=\"title desc\">
  <title id=\"title\">Movie Poster</title>
  <desc id=\"desc\">Local fallback poster image.</desc>
  <defs>
    <linearGradient id=\"bg\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\">
      <stop offset=\"0\" stop-color=\"#1f254a\"/>
      <stop offset=\"1\" stop-color=\"#253a7a\"/>
    </linearGradient>
  </defs>
  <rect width=\"400\" height=\"600\" fill=\"url(#bg)\"/>
  <rect x=\"35\" y=\"35\" width=\"330\" height=\"530\" rx=\"18\" fill=\"none\" stroke=\"#b7c4f7\" stroke-opacity=\"0.5\" stroke-width=\"3\"/>
  <text x=\"200\" y=\"290\" text-anchor=\"middle\" font-size=\"34\" font-family=\"Arial, Helvetica, sans-serif\" fill=\"#eef3ff\">Movie</text>
  <text x=\"200\" y=\"332\" text-anchor=\"middle\" font-size=\"34\" font-family=\"Arial, Helvetica, sans-serif\" fill=\"#eef3ff\">Poster</text>
</svg>
"""

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
    p = argparse.ArgumentParser(description="Download movie posters to local disk and rewrite DB to /posters/* paths")
    p.add_argument("--mysql-host", default=os.environ.get("MYSQL_HOST", "127.0.0.1"))
    p.add_argument("--mysql-port", type=int, default=int(os.environ.get("MYSQL_PORT", "3307")))
    p.add_argument("--mysql-user", default=os.environ.get("MYSQL_USER", "root"))
    p.add_argument("--mysql-pwd", default=os.environ.get("MYSQL_PWD", "xz20220429"))
    p.add_argument("--mysql-db", default=os.environ.get("MYSQL_DB", "movie_system"))
    p.add_argument(
        "--poster-dir",
        default=os.environ.get("POSTER_DIR", str(Path.home() / ".movie-system" / "posters")),
        help="Local poster directory served by backend at /posters/**",
    )
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--force", action="store_true", help="Re-download even when a local file already exists")
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def db_connect(args: argparse.Namespace):
    return pymysql.connect(
        host=args.mysql_host,
        port=args.mysql_port,
        user=args.mysql_user,
        password=args.mysql_pwd,
        database=args.mysql_db,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.Cursor,
    )


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM movie LIKE 'poster_url'")
        if cur.fetchone() is None:
            cur.execute("ALTER TABLE movie ADD COLUMN poster_url VARCHAR(512) NULL")
    conn.commit()


def ensure_default_poster(poster_dir: Path) -> str:
    poster_dir.mkdir(parents=True, exist_ok=True)
    default_path = poster_dir / "default.svg"
    if not default_path.exists():
        default_path.write_text(DEFAULT_POSTER_SVG, encoding="utf-8")
    return "/posters/default.svg"


def fetch_movies(conn) -> list[tuple[int, str, str | None]]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, title, poster_url FROM movie ORDER BY id")
        rows = cur.fetchall()
    return [(int(r[0]), r[1] or "", r[2]) for r in rows]


def guess_ext_from_url(url: str) -> str | None:
    try:
        path = urllib.parse.urlparse(url).path
    except Exception:
        return None
    ext = Path(path).suffix.lower().lstrip(".")
    if ext in ALLOWED_EXT:
        return "jpg" if ext == "jpeg" else ext
    guessed, _ = mimetypes.guess_type(path)
    if guessed and guessed in CONTENT_TYPE_TO_EXT:
        return CONTENT_TYPE_TO_EXT[guessed]
    return None


def choose_existing_local_file(movie_id: int, poster_dir: Path) -> Path | None:
    candidates = sorted(poster_dir.glob(f"{movie_id}.*"))
    for p in candidates:
        if p.is_file():
            return p
    return None


def download_image(url: str, timeout: int) -> tuple[bytes, str | None]:
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
        content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        data = resp.read()
    return data, content_type


def detect_ext(content_type: str | None, url: str) -> str:
    if content_type in CONTENT_TYPE_TO_EXT:
        return CONTENT_TYPE_TO_EXT[content_type]
    from_url = guess_ext_from_url(url)
    return from_url or "jpg"


def write_image_atomically(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="poster_", suffix=".tmp", dir=str(target.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with tmp_path.open("wb") as f:
            f.write(data)
        tmp_path.replace(target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def local_url_from_file(path: Path, poster_dir: Path) -> str:
    rel = path.relative_to(poster_dir)
    return "/posters/" + str(rel).replace("\\", "/")


def process_one(movie_id: int, title: str, poster_url: str | None, poster_dir: Path, default_url: str,
                timeout: int, retries: int, force: bool) -> tuple[int, str, str]:
    """
    Returns: (movie_id, local_url, status)
    status in {downloaded, reused, fallback, kept_local}
    """
    existing_file = choose_existing_local_file(movie_id, poster_dir)

    if isinstance(poster_url, str) and poster_url.startswith("/posters/") and existing_file:
        if not force:
            return movie_id, local_url_from_file(existing_file, poster_dir), "kept_local"

    if existing_file and not force:
        return movie_id, local_url_from_file(existing_file, poster_dir), "reused"

    source_url = (poster_url or "").strip()
    if not source_url or not re.match(r"^https?://", source_url, re.IGNORECASE):
        return movie_id, default_url, "fallback"

    last_error = None
    for _ in range(retries + 1):
        try:
            data, content_type = download_image(source_url, timeout)
            if not data:
                raise ValueError("empty body")
            if content_type and not content_type.startswith("image/"):
                raise ValueError(f"non-image content type: {content_type}")

            ext = detect_ext(content_type, source_url)
            target = poster_dir / f"{movie_id}.{ext}"
            write_image_atomically(target, data)

            for old in poster_dir.glob(f"{movie_id}.*"):
                if old != target and old.is_file():
                    old.unlink(missing_ok=True)

            return movie_id, f"/posters/{target.name}", "downloaded"
        except Exception as e:  # noqa: BLE001
            last_error = e

    _ = last_error, title
    return movie_id, default_url, "fallback"


def batch_update_db(conn, updates: list[tuple[str, int]], batch_size: int) -> None:
    with conn.cursor() as cur:
        for i in range(0, len(updates), batch_size):
            cur.executemany(
                "UPDATE movie SET poster_url = %s WHERE id = %s",
                updates[i : i + batch_size],
            )
    conn.commit()


def main() -> None:
    args = parse_args()
    poster_dir = Path(args.poster_dir).expanduser().resolve()

    conn = db_connect(args)
    try:
        ensure_schema(conn)
        default_url = ensure_default_poster(poster_dir)
        movies = fetch_movies(conn)
        print(f"Poster dir:            {poster_dir}")
        print(f"Movies total:          {len(movies)}")

        updates: list[tuple[str, int]] = []
        stats = {"downloaded": 0, "reused": 0, "kept_local": 0, "fallback": 0}

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = [
                executor.submit(
                    process_one,
                    mid,
                    title,
                    url,
                    poster_dir,
                    default_url,
                    args.timeout,
                    args.retries,
                    args.force,
                )
                for mid, title, url in movies
            ]

            done = 0
            for f in as_completed(futures):
                mid, local_url, status = f.result()
                updates.append((local_url, mid))
                stats[status] = stats.get(status, 0) + 1
                done += 1
                if done % 300 == 0 or done == len(futures):
                    print(f"Processed: {done}/{len(futures)}")

        if args.dry_run:
            print("Dry run enabled, DB will not be updated.")
        else:
            batch_update_db(conn, updates, batch_size=args.batch_size)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM movie WHERE poster_url LIKE '/posters/%'")
            local_rows = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM movie WHERE poster_url = '/posters/default.svg'")
            fallback_rows = int(cur.fetchone()[0])

        print(f"Downloaded new:        {stats['downloaded']}")
        print(f"Reused existing:       {stats['reused'] + stats['kept_local']}")
        print(f"Fallback assigned:     {stats['fallback']}")
        print(f"DB local path rows:    {local_rows}/{len(movies)}")
        print(f"DB fallback rows:      {fallback_rows}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
