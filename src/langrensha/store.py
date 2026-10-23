"""本机 SQLite 快照与审计；一次事务中完成校验、行动生效和请求去重。"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = str(Path(path))
        if self.path == ":memory:":
            raise ValueError("请使用文件数据库；各事务使用独立连接")
        with self.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS games (id TEXT PRIMARY KEY, state TEXT NOT NULL)"
            )
            db.execute("""CREATE TABLE IF NOT EXISTS rejections (
                id INTEGER PRIMARY KEY, game_id TEXT NOT NULL,
                actor INTEGER NOT NULL, code TEXT NOT NULL, time TEXT NOT NULL
            )""")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def load(db, game_id):
        row = db.execute("SELECT state FROM games WHERE id=?", (game_id,)).fetchone()
        if row is None:
            raise KeyError("game_not_found")
        return json.loads(row[0])

    @staticmethod
    def save(db, state, *, create=False):
        encoded = json.dumps(state, ensure_ascii=False, sort_keys=True)
        if create:
            db.execute("INSERT INTO games(id,state) VALUES (?,?)", (state["id"], encoded))
        else:
            db.execute("UPDATE games SET state=? WHERE id=?", (encoded, state["id"]))
