"""SQLite 데이터베이스 초기화 및 헬퍼"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "erp.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())

    # 기본 관리자 계정 (비밀번호: admin123 → 실제 운영 시 변경)
    import hashlib
    pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
            ("admin", pw_hash, "관리자", "admin"),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()


def query(sql, params=(), one=False):
    conn = get_db()
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows[0] if one and rows else rows if not one else None


def execute(sql, params=()):
    conn = get_db()
    cur = conn.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def execute_many(sql, params_list):
    conn = get_db()
    conn.executemany(sql, params_list)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"DB initialized: {DB_PATH}")
