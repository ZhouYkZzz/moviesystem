import os, re
from datetime import datetime
import pymysql

ML1M_PATH = os.environ.get("ML1M_PATH", "./ml-1m")

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3307"))          # 你本地映射端口
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PWD  = os.environ.get("MYSQL_PWD", "xz20220429")          # 你的密码
MYSQL_DB   = os.environ.get("MYSQL_DB", "movie_system")         # 你的库名

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5000"))

def connect():
    # 关键：关闭autocommit，批量提交
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PWD,
        database=MYSQL_DB, charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.Cursor
    )

def parse_year(title: str):
    m = re.search(r"\((\d{4})\)\s*$", title)
    return int(m.group(1)) if m else None

def import_movies(conn):
    cur = conn.cursor()
    path = os.path.join(ML1M_PATH, "movies.dat")

    rows = []
    with open(path, "r", encoding="latin-1") as f:
        for line in f:
            mid, title, genres = line.strip().split("::")
            mid = int(mid)
            year = parse_year(title)
            rows.append((mid, title, genres, year))
            if len(rows) >= BATCH_SIZE:
                cur.executemany(
                    """
                    INSERT INTO movie(id,title,genres,year) VALUES(%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                        title = VALUES(title),
                        genres = VALUES(genres),
                        year = VALUES(year)
                    """,
                    rows
                )
                conn.commit()
                rows.clear()

    if rows:
        cur.executemany(
            """
            INSERT INTO movie(id,title,genres,year) VALUES(%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                genres = VALUES(genres),
                year = VALUES(year)
            """,
            rows
        )
        conn.commit()

def import_ratings_as_events(conn):
    cur = conn.cursor()
    path = os.path.join(ML1M_PATH, "ratings.dat")

    user_rows = []
    rate_rows = []
    view_rows = []
    count = 0

    with open(path, "r", encoding="latin-1") as f:
        for line in f:
            uid, mid, rating, ts = line.strip().split("::")
            uid = int(uid); mid = int(mid); rating = float(rating); ts = int(ts)
            dt = datetime.fromtimestamp(ts)

            user_rows.append((uid,))
            rate_rows.append((uid, mid, "rate", rating, dt))
            view_rows.append((uid, mid, "view", dt))

            count += 1
            if count % BATCH_SIZE == 0:
                # 1) 批量插入用户（ignore）
                cur.executemany("INSERT IGNORE INTO ml_user(id) VALUES(%s)", user_rows)
                # 2) 批量插入 rate
                cur.executemany(
                    "INSERT INTO user_event(user_id,movie_id,event_type,score,event_time) VALUES(%s,%s,%s,%s,%s)",
                    rate_rows
                )
                # 3) 批量插入 view
                cur.executemany(
                    "INSERT INTO user_event(user_id,movie_id,event_type,event_time) VALUES(%s,%s,%s,%s)",
                    view_rows
                )

                conn.commit()
                user_rows.clear(); rate_rows.clear(); view_rows.clear()

                if count % (BATCH_SIZE * 10) == 0:
                    print(f"processed ratings: {count}")

    # flush
    if user_rows:
        cur.executemany("INSERT IGNORE INTO ml_user(id) VALUES(%s)", user_rows)
        cur.executemany(
            "INSERT INTO user_event(user_id,movie_id,event_type,score,event_time) VALUES(%s,%s,%s,%s,%s)",
            rate_rows
        )
        cur.executemany(
            "INSERT INTO user_event(user_id,movie_id,event_type,event_time) VALUES(%s,%s,%s,%s)",
            view_rows
        )
        conn.commit()

    print(f"done. total ratings processed: {count}")

def main():
    conn = connect()
    try:
        print("Import movies...")
        import_movies(conn)
        print("Import ratings/events...")
        import_ratings_as_events(conn)
    finally:
        conn.close()
    print("ml-1m import finished.")

if __name__ == "__main__":
    main()
