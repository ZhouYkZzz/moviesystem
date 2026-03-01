# offline/infer_topn_and_writeback_fast.py
import os, json
from datetime import datetime
import warnings

import pymysql
import redis
import torch

from recbole.config import Config
from recbole.data import create_dataset, data_preparation
from recbole.utils import init_seed, get_model

# 可选：隐藏 RecBole 内部 pandas FutureWarning（不影响结果）
warnings.filterwarnings("ignore", category=FutureWarning)

# ====== 参数 ======
CONFIG_YAML = os.environ.get("CONFIG_YAML", "offline/bert4rec_ml1m_seq.yaml")
MODEL_PATH  = os.environ.get("MODEL_PATH", "./saved/BERT4Rec-Feb-27-2026_12-37-44.pth")

TOPN = int(os.environ.get("TOPN", "20"))
REDIS_TTL = int(os.environ.get("REDIS_TTL", str(24 * 3600)))

# 活跃用户窗口（注意：ML-1m 时间很老，不能用 NOW()，必须用数据集最大时间）
ACTIVE_DAYS = int(os.environ.get("ACTIVE_DAYS", "99999"))

# 每批处理多少用户（影响 MySQL executemany 与 Redis pipeline 的批大小）
BATCH_USERS = int(os.environ.get("BATCH_USERS", "200"))

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3307"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PWD  = os.environ.get("MYSQL_PWD", "xz20220429")
MYSQL_DB   = os.environ.get("MYSQL_DB", "movie_system")

REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB   = int(os.environ.get("REDIS_DB", "0"))


def mysql_conn():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PWD,
        database=MYSQL_DB, charset="utf8mb4",
        autocommit=False
    )

def redis_conn():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

def fetch_active_users(conn):
    """
    以数据集 MAX(event_time) 作为“现在”，取最近 ACTIVE_DAYS 的活跃用户。
    解决 MovieLens 1M 时间戳很老导致 NOW() 过滤后 active=0 的问题。
    """
    cur = conn.cursor()

    cur.execute("SELECT MAX(event_time) FROM user_event")
    max_time = cur.fetchone()[0]
    if max_time is None:
        return []

    cur.execute(
        """
        SELECT DISTINCT user_id
        FROM user_event
        WHERE event_time >= %s - INTERVAL %s DAY
        ORDER BY user_id ASC
        """,
        (max_time, ACTIVE_DAYS)
    )
    users = [int(x[0]) for x in cur.fetchall()]

    # 兜底：窗口太小导致 0，就退回全量用户（保证推理一定写回）
    if not users:
        cur.execute("SELECT DISTINCT user_id FROM user_event ORDER BY user_id ASC")
        users = [int(x[0]) for x in cur.fetchall()]

    return users

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def main():
    if not MODEL_PATH:
        raise ValueError("Please set MODEL_PATH to your .pth file")
    if TOPN <= 0:
        raise ValueError("TOPN must be > 0")

    # 1) RecBole config + dataset
    config = Config(model="BERT4Rec", dataset="ml1m_seq", config_file_list=[CONFIG_YAML])
    init_seed(config["seed"], config["reproducibility"])

    dataset = create_dataset(config)
    train_data, valid_data, test_data = data_preparation(config, dataset)

    uid_field = config["USER_ID_FIELD"]
    iid_field = config["ITEM_ID_FIELD"]

    # internal id -> raw token(str)
    i2token = dataset.field2id_token[iid_field]

    # raw uid(str) -> internal uid(int)
    token2u = dataset.field2token_id[uid_field]

    # 2) load model
    model = get_model(config["model"])(config, train_data.dataset).to(config["device"])
    ckpt = torch.load(MODEL_PATH, map_location=config["device"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    # 3) active users
    conn = mysql_conn()
    rds = redis_conn()
    active_raw_uids = fetch_active_users(conn)
    print("active users:", len(active_raw_uids))

    now = datetime.now()

    # 4) batch infer + batch write
    cur = conn.cursor()
    wrote = 0

    # 取一条 interaction 作为“壳”（注意：Interaction 在你这个版本没有 .copy()）
    # 方案A：循环里就地替换 uid，再恢复
    base_inter = test_data.dataset.inter_feat[:1]
    orig_uid = base_inter[uid_field].clone()

    try:
        for raw_batch in chunk(active_raw_uids, BATCH_USERS):
            mysql_rows = []
            pipe = rds.pipeline()

            for raw_uid in raw_batch:
                key = str(raw_uid)
                if key not in token2u:
                    continue
                internal_uid = token2u[key]

                # 就地替换 uid
                base_inter[uid_field] = torch.tensor([internal_uid], device=config["device"])

                # full sort scores: [item_num]
                scores = model.full_sort_predict(base_inter).detach().reshape(-1)

                # 跳过 padding item=0
                if scores.numel() > 0:
                    scores[0] = -1e18

                # 用 torch.topk 提速（避免 argsort 全排序）
                k = min(TOPN, int(scores.numel()) - 1) if scores.numel() > 1 else 0
                if k <= 0:
                    continue

                _, top_idx = torch.topk(scores, k=k, largest=True)
                top_idx = top_idx.detach().cpu().tolist()

                rec = [int(i2token[int(i)]) for i in top_idx]
                rec_json = json.dumps(rec, ensure_ascii=False)

                mysql_rows.append((raw_uid, rec_json, now))
                pipe.setex(f"reco:user:{raw_uid}", REDIS_TTL, rec_json)

            # MySQL 批量写回 + Redis pipeline
            if mysql_rows:
                cur.executemany(
                    "REPLACE INTO user_reco(user_id, reco_json, gen_time) VALUES(%s, CAST(%s AS JSON), %s)",
                    mysql_rows
                )
                conn.commit()
                pipe.execute()

                wrote += len(mysql_rows)
                print("wrote:", wrote)

    finally:
        # 恢复 base_inter 的原 uid，避免潜在副作用
        base_inter[uid_field] = orig_uid
        conn.close()

    print("done, total wrote:", wrote)

if __name__ == "__main__":
    main()
