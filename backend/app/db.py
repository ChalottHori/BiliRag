"""数据层：SQLAlchemy engine/session、`create_all`、FTS5 原生 DDL 与默认配置种子。

FTS5 说明（Part 0.7 第 1 条）：`chat_message_fts` 不是普通 SQLAlchemy 模型，用原生 SQL
建虚拟表 + 触发器（同步 `chat_session.title` 与 `chat_message.content`）。中文检索采用
`trigram` 分词（SQLite >= 3.34）。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import defaults, get_data_dir
from .models.base import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


# --------------------------------------------------------------------------- FTS5 DDL
_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS chat_message_fts USING fts5(
    session_id UNINDEXED,
    ref_id UNINDEXED,
    doc_type UNINDEXED,
    title,
    content,
    tokenize = 'trigram'
);
"""

# 会话标题同步
_SESSION_AI = """
CREATE TRIGGER IF NOT EXISTS trg_chat_session_fts_ai
AFTER INSERT ON chat_session BEGIN
    INSERT INTO chat_message_fts(session_id, ref_id, doc_type, title, content)
    VALUES (new.id, new.id, 'title', new.title, '');
END;
"""
_SESSION_AU = """
CREATE TRIGGER IF NOT EXISTS trg_chat_session_fts_au
AFTER UPDATE OF title ON chat_session BEGIN
    DELETE FROM chat_message_fts WHERE doc_type = 'title' AND ref_id = old.id;
    INSERT INTO chat_message_fts(session_id, ref_id, doc_type, title, content)
    VALUES (new.id, new.id, 'title', new.title, '');
END;
"""
_SESSION_AD = """
CREATE TRIGGER IF NOT EXISTS trg_chat_session_fts_ad
AFTER DELETE ON chat_session BEGIN
    DELETE FROM chat_message_fts WHERE session_id = old.id;
END;
"""

# 消息内容同步
_MESSAGE_AI = """
CREATE TRIGGER IF NOT EXISTS trg_chat_message_fts_ai
AFTER INSERT ON chat_message BEGIN
    INSERT INTO chat_message_fts(session_id, ref_id, doc_type, title, content)
    VALUES (new.session_id, new.id, 'message', '', new.content);
END;
"""
_MESSAGE_AU = """
CREATE TRIGGER IF NOT EXISTS trg_chat_message_fts_au
AFTER UPDATE OF content ON chat_message BEGIN
    DELETE FROM chat_message_fts WHERE doc_type = 'message' AND ref_id = old.id;
    INSERT INTO chat_message_fts(session_id, ref_id, doc_type, title, content)
    VALUES (new.session_id, new.id, 'message', '', new.content);
END;
"""
_MESSAGE_AD = """
CREATE TRIGGER IF NOT EXISTS trg_chat_message_fts_ad
AFTER DELETE ON chat_message BEGIN
    DELETE FROM chat_message_fts WHERE doc_type = 'message' AND ref_id = old.id;
END;
"""

_FTS_STATEMENTS = (
    _FTS_TABLE,
    _SESSION_AI,
    _SESSION_AU,
    _SESSION_AD,
    _MESSAGE_AI,
    _MESSAGE_AU,
    _MESSAGE_AD,
)


# --------------------------------------------------------------------------- engine
def _ensure_data_dirs(data_dir: Path) -> None:
    for sub in ("chroma", "thumbnails", "exports", "logs"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        data_dir = get_data_dir()
        _ensure_data_dirs(data_dir)
        db_path = data_dir / "app.db"
        _engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            future=True,
        )

        @event.listens_for(_engine, "connect")
        def _set_pragmas(dbapi_conn: object, _record: object) -> None:
            cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


# --------------------------------------------------------------------------- init
def _create_fts5(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in _FTS_STATEMENTS:
            conn.execute(text(statement))


def _seed_settings(engine: Engine) -> None:
    from .models import Folder, Setting

    factory = get_session_factory()
    with factory() as session:
        if session.get(Setting, "1") is None:
            data = defaults().model_dump()
            session.add(Setting(id="1", **data))
        if session.query(Folder).filter(Folder.kind == "uncategorized").first() is None:
            session.add(Folder(title="未分类", kind="uncategorized", fid=None))
        session.commit()


def _migrate_schema(engine: Engine) -> None:
    """幂等迁移：`create_all` 不会给已存在的表加列，这里补齐历史库缺失的列。"""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("item")}
    if "batch_id" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE item ADD COLUMN batch_id VARCHAR(36)"))

    settings_columns = {col["name"] for col in inspector.get_columns("settings")}
    if "chat_use_llm_router" not in settings_columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE settings ADD COLUMN chat_use_llm_router BOOLEAN DEFAULT 0")
            )
    if "chat_use_react" not in settings_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE settings ADD COLUMN chat_use_react BOOLEAN DEFAULT 0"))


def init_db() -> None:
    """启动建表：`create_all` 建普通表，再建 FTS5 虚拟表 + 触发器，并种入默认配置。"""
    from . import models  # noqa: F401  确保所有模型注册到 Base.metadata

    engine = get_engine()
    Base.metadata.create_all(engine)
    _create_fts5(engine)
    _migrate_schema(engine)
    _seed_settings(engine)
