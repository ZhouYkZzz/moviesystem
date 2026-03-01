import os
import pymysql
from pymysql.cursors import SSCursor

OUT_DIR = os.environ.get("OUT_DIR", "./recbole_data/ml1m_seq")
DATASET = "ml1m_seq"

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3307"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PWD  = os.environ.get("MYSQL_PWD", "xz20220429")
MYSQL_DB   = os.environ.get("MYSQL_DB", "movie_system")

def connect():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PWD,
        database=MYSQL_DB, charset="utf8mb4",
        autocommit=True,
        cursorclass=SSCursor  # 关键：流式
    )

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{DATASET}.inter")

    conn = connect()
    cur = conn.cursor()

    # 只用 view 构建序列（你导入时每条rating都写了view）
    cur.execute("""
        SELECT user_id, movie_id, UNIX_TIMESTAMP(event_time) AS ts
        FROM user_event FORCE INDEX (idx_user_time)
        WHERE event_type='view'
        ORDER BY user_id ASC, event_time ASC
    """)

    n = 0
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("user_id:token\titem_id:token\ttimestamp:float\n")
        for uid, mid, ts in cur:
            f.write(f"{uid}\t{mid}\t{float(ts)}\n")
            n += 1
            if n % 200000 == 0:
                print("written:", n)

    conn.close()
    print("done:", out_path, "rows:", n)

if __name__ == "__main__":
    main()
