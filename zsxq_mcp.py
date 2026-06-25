#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识星球 SQLite MCP 服务。

将此文件作为 MCP stdio 服务运行后，AI 客户端可以只读分析本地
ZSXQCrawler 数据库，不会修改原始数据。
"""

from __future__ import annotations

import argparse
import fnmatch
import html
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote, unquote


PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "zsxq-data-mcp"
SERVER_VERSION = "1.0.0"
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DB_ROOT = PROJECT_ROOT / "output" / "databases"
MAX_TEXT_CHARS = 12000
DEFAULT_LIMIT = 20
MAX_LIMIT = 200


TOPICS_SCHEMA: Dict[str, List[str]] = {
    "groups": ["group_id", "name", "type", "background_url", "created_at"],
    "users": [
        "user_id",
        "name",
        "alias",
        "avatar_url",
        "location",
        "description",
        "ai_comment_url",
        "created_at",
    ],
    "topics": [
        "topic_id",
        "group_id",
        "type",
        "title",
        "create_time",
        "digested",
        "sticky",
        "likes_count",
        "tourist_likes_count",
        "rewards_count",
        "comments_count",
        "reading_count",
        "readers_count",
        "answered",
        "silenced",
        "annotation",
        "user_liked",
        "user_subscribed",
        "imported_at",
    ],
    "talks": ["id", "topic_id", "owner_user_id", "text", "created_at"],
    "articles": [
        "id",
        "topic_id",
        "title",
        "article_id",
        "article_url",
        "inline_article_url",
        "created_at",
    ],
    "images": [
        "image_id",
        "topic_id",
        "comment_id",
        "type",
        "thumbnail_url",
        "thumbnail_width",
        "thumbnail_height",
        "large_url",
        "large_width",
        "large_height",
        "original_url",
        "original_width",
        "original_height",
        "original_size",
        "created_at",
    ],
    "likes": ["id", "topic_id", "user_id", "create_time", "imported_at"],
    "like_emojis": ["id", "topic_id", "emoji_key", "likes_count", "created_at"],
    "user_liked_emojis": ["id", "topic_id", "emoji_key", "created_at"],
    "comments": [
        "comment_id",
        "topic_id",
        "owner_user_id",
        "parent_comment_id",
        "repliee_user_id",
        "text",
        "create_time",
        "likes_count",
        "rewards_count",
        "replies_count",
        "sticky",
        "imported_at",
    ],
    "questions": [
        "id",
        "topic_id",
        "owner_user_id",
        "questionee_user_id",
        "text",
        "expired",
        "anonymous",
        "owner_questions_count",
        "owner_join_time",
        "owner_status",
        "owner_location",
        "created_at",
    ],
    "answers": ["id", "topic_id", "owner_user_id", "text", "created_at"],
    "tags": ["tag_id", "group_id", "tag_name", "hid", "topic_count", "created_at"],
    "topic_tags": ["id", "topic_id", "tag_id", "created_at"],
    "topic_files": [
        "id",
        "topic_id",
        "file_id",
        "name",
        "hash",
        "size",
        "duration",
        "download_count",
        "create_time",
        "created_at",
    ],
}

FILES_SCHEMA: Dict[str, List[str]] = {
    "api_responses": [
        "id",
        "succeeded",
        "index_value",
        "files_count",
        "request_url",
        "request_params",
        "created_at",
    ],
    "files": [
        "file_id",
        "name",
        "hash",
        "size",
        "duration",
        "download_count",
        "create_time",
        "imported_at",
        "download_status",
        "local_path",
        "download_time",
    ],
    "groups": ["group_id", "name", "type", "background_url", "imported_at"],
    "users": [
        "user_id",
        "name",
        "alias",
        "avatar_url",
        "description",
        "location",
        "ai_comment_url",
        "imported_at",
    ],
    "topics": [
        "topic_id",
        "group_id",
        "type",
        "title",
        "annotation",
        "likes_count",
        "tourist_likes_count",
        "rewards_count",
        "comments_count",
        "reading_count",
        "readers_count",
        "digested",
        "sticky",
        "create_time",
        "modify_time",
        "user_liked",
        "user_subscribed",
        "imported_at",
    ],
    "file_topic_relations": ["id", "file_id", "topic_id", "created_at"],
    "talks": ["id", "topic_id", "owner_user_id", "text", "created_at"],
    "images": [
        "image_id",
        "topic_id",
        "type",
        "thumbnail_url",
        "thumbnail_width",
        "thumbnail_height",
        "large_url",
        "large_width",
        "large_height",
        "original_url",
        "original_width",
        "original_height",
        "original_size",
        "created_at",
    ],
    "topic_files": [
        "id",
        "topic_id",
        "file_id",
        "name",
        "hash",
        "size",
        "duration",
        "download_count",
        "create_time",
        "created_at",
    ],
    "latest_likes": ["id", "topic_id", "owner_user_id", "create_time", "created_at"],
    "comments": [
        "comment_id",
        "topic_id",
        "owner_user_id",
        "parent_comment_id",
        "repliee_user_id",
        "text",
        "create_time",
        "likes_count",
        "rewards_count",
        "replies_count",
        "sticky",
        "created_at",
    ],
    "like_emojis": ["id", "topic_id", "emoji_key", "likes_count", "created_at"],
    "user_liked_emojis": ["id", "topic_id", "emoji_key", "created_at"],
    "columns": ["column_id", "name", "created_at"],
    "topic_columns": ["id", "topic_id", "column_id", "created_at"],
    "solutions": ["id", "topic_id", "task_id", "owner_user_id", "text", "created_at"],
    "solution_files": [
        "id",
        "solution_id",
        "file_id",
        "name",
        "hash",
        "size",
        "duration",
        "download_count",
        "create_time",
        "created_at",
    ],
    "collection_log": [
        "id",
        "start_time",
        "end_time",
        "total_files",
        "new_files",
        "status",
        "created_at",
    ],
}

COLUMNS_SCHEMA: Dict[str, List[str]] = {
    "columns": [
        "column_id",
        "group_id",
        "name",
        "cover_url",
        "topics_count",
        "create_time",
        "last_topic_attach_time",
        "imported_at",
    ],
    "column_topics": [
        "topic_id",
        "column_id",
        "group_id",
        "title",
        "text",
        "create_time",
        "attached_to_column_time",
        "imported_at",
    ],
    "topic_details": [
        "topic_id",
        "group_id",
        "type",
        "title",
        "full_text",
        "likes_count",
        "comments_count",
        "readers_count",
        "digested",
        "sticky",
        "create_time",
        "modify_time",
        "raw_json",
        "imported_at",
        "updated_at",
    ],
    "users": ["user_id", "name", "alias", "avatar_url", "description", "location", "imported_at"],
    "topic_owners": ["id", "topic_id", "user_id", "owner_type"],
    "images": [
        "image_id",
        "topic_id",
        "comment_id",
        "type",
        "thumbnail_url",
        "thumbnail_width",
        "thumbnail_height",
        "large_url",
        "large_width",
        "large_height",
        "original_url",
        "original_width",
        "original_height",
        "original_size",
        "local_path",
        "imported_at",
    ],
    "files": [
        "file_id",
        "topic_id",
        "name",
        "hash",
        "size",
        "duration",
        "download_count",
        "create_time",
        "download_status",
        "local_path",
        "download_time",
        "imported_at",
    ],
    "comments": [
        "comment_id",
        "topic_id",
        "owner_user_id",
        "parent_comment_id",
        "repliee_user_id",
        "text",
        "create_time",
        "likes_count",
        "rewards_count",
        "replies_count",
        "sticky",
        "imported_at",
    ],
    "videos": [
        "video_id",
        "topic_id",
        "size",
        "duration",
        "cover_url",
        "cover_width",
        "cover_height",
        "cover_local_path",
        "video_url",
        "download_status",
        "local_path",
        "download_time",
        "imported_at",
    ],
    "crawl_log": [
        "id",
        "group_id",
        "crawl_type",
        "start_time",
        "end_time",
        "columns_count",
        "topics_count",
        "details_count",
        "files_count",
        "status",
        "error_message",
    ],
}

EXPECTED_SCHEMAS = {
    "topics": TOPICS_SCHEMA,
    "files": FILES_SCHEMA,
    "columns": COLUMNS_SCHEMA,
}

CONTENT_DB_PATTERNS = [
    "zsxq_topics_*.db",
    "zsxq_files_*.db",
    "zsxq_columns_*.db",
]
DB_SUFFIXES = {".db", ".sqlite", ".sqlite3"}

SQL_DENY_ACTIONS = {
    sqlite3.SQLITE_ATTACH,
    sqlite3.SQLITE_ALTER_TABLE,
    sqlite3.SQLITE_CREATE_INDEX,
    sqlite3.SQLITE_CREATE_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_INDEX,
    sqlite3.SQLITE_CREATE_TEMP_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
    sqlite3.SQLITE_CREATE_TEMP_VIEW,
    sqlite3.SQLITE_CREATE_TRIGGER,
    sqlite3.SQLITE_CREATE_VIEW,
    sqlite3.SQLITE_DELETE,
    sqlite3.SQLITE_DETACH,
    sqlite3.SQLITE_DROP_INDEX,
    sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_DROP_TEMP_INDEX,
    sqlite3.SQLITE_DROP_TEMP_TABLE,
    sqlite3.SQLITE_DROP_TEMP_TRIGGER,
    sqlite3.SQLITE_DROP_TEMP_VIEW,
    sqlite3.SQLITE_DROP_TRIGGER,
    sqlite3.SQLITE_DROP_VIEW,
    sqlite3.SQLITE_INSERT,
    sqlite3.SQLITE_REINDEX,
    sqlite3.SQLITE_TRANSACTION,
    sqlite3.SQLITE_UPDATE,
}
ALLOWED_PRAGMAS = {
    "database_list",
    "foreign_key_list",
    "index_info",
    "index_list",
    "quick_check",
    "schema_version",
    "table_info",
    "table_xinfo",
    "user_version",
}


class MCPError(Exception):
    """MCP 工具层错误。"""


class ServerConfig:
    def __init__(self, default_db: Optional[Path], allow_any_db: bool, max_rows: int) -> None:
        self.default_db = default_db.resolve() if default_db else None
        self.allow_any_db = allow_any_db or os.environ.get("ZSXQ_MCP_ALLOW_ANY_DB") == "1"
        self.max_rows = max(1, min(max_rows, MAX_LIMIT))
        self.explicit_allowed = {self.default_db} if self.default_db else set()


CONFIG = ServerConfig(None, False, MAX_LIMIT)


def stderr(message: str) -> None:
    """MCP stdio 期间只能向 stderr 写诊断信息。"""
    print(message, file=sys.stderr, flush=True)


def clamp_limit(value: Any, default: int = DEFAULT_LIMIT) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, CONFIG.max_rows))


def shorten_text(value: Any, max_chars: int = MAX_TEXT_CHARS) -> Any:
    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars] + "... [truncated]"
    return value


def row_to_dict(cursor: sqlite3.Cursor, row: Sequence[Any]) -> Dict[str, Any]:
    columns = [desc[0] for desc in cursor.description or []]
    return {column: shorten_text(row[index]) for index, column in enumerate(columns)}


def normalize_db_path(path: Path) -> Path:
    return path.expanduser().resolve()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def is_content_db_name(path: Path) -> bool:
    name = path.name
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in CONTENT_DB_PATTERNS)


def is_project_workspace() -> bool:
    """判断当前目录是否是完整项目，而不是单文件 MCP 分发目录。"""
    return any(
        marker.exists()
        for marker in (
            PROJECT_ROOT / "backend",
            PROJECT_ROOT / "frontend",
            PROJECT_ROOT / "output",
            PROJECT_ROOT / "pyproject.toml",
            PROJECT_ROOT / "package.json",
        )
    )


def is_allowed_db_path(path: Path) -> bool:
    path = normalize_db_path(path)
    if CONFIG.allow_any_db:
        return True
    if path in CONFIG.explicit_allowed:
        return True
    if path.parent == PROJECT_ROOT and path.suffix.lower() in DB_SUFFIXES and not is_project_workspace():
        return True
    if not is_relative_to(path, OUTPUT_DB_ROOT):
        return False
    return is_content_db_name(path)


def output_database_paths(pattern: str = "*.db") -> List[Path]:
    if not OUTPUT_DB_ROOT.exists():
        return []
    return sorted(OUTPUT_DB_ROOT.rglob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)


def root_database_paths() -> List[Path]:
    paths: List[Path] = []
    for suffix in DB_SUFFIXES:
        paths.extend(PROJECT_ROOT.glob(f"*{suffix}"))
    return sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True)


def sqlite_table_count(path: Path, table_name: str) -> int:
    try:
        uri_path = quote(str(path).replace("\\", "/"), safe="/:")
        with sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True, timeout=5.0) as conn:
            row = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def choose_default_database_path() -> Optional[Path]:
    """选择默认数据库：显式 --db > output/databases 中有数据的话题库 > 最新输出库。

    项目模式下只从 output/databases 自动发现；只有单文件分发目录
    （没有 backend/frontend/output 等项目标记）才把脚本同目录 SQLite 当作兜底。
    """
    if CONFIG.default_db and CONFIG.default_db.exists():
        return normalize_db_path(CONFIG.default_db)

    topics_databases = output_database_paths("zsxq_topics_*.db")
    if topics_databases:
        for database_path in topics_databases:
            if sqlite_table_count(database_path, "topics") > 0:
                return normalize_db_path(database_path)

    all_output_databases = [path for path in output_database_paths("*.db") if is_content_db_name(path)]
    if all_output_databases:
        return normalize_db_path(all_output_databases[0])

    # 独立交付模式：目录中只有脚本 + 数据库时仍可开箱使用。
    if not is_project_workspace():
        root_databases = root_database_paths()
        if root_databases:
            return normalize_db_path(root_databases[0])

    return None


def candidate_database_paths() -> List[Path]:
    candidates: List[Path] = []
    default_path = choose_default_database_path()
    if default_path:
        candidates.append(default_path)
    if CONFIG.default_db and CONFIG.default_db.exists():
        candidates.append(CONFIG.default_db)
    output_databases = output_database_paths("*.db")
    candidates.extend(output_databases)
    if not output_databases and not is_project_workspace():
        candidates.extend(root_database_paths())
    return candidates


def discover_databases() -> List[Dict[str, Any]]:
    seen = set()
    databases = []
    for candidate in candidate_database_paths():
        path = normalize_db_path(candidate)
        if path in seen or not path.exists() or not is_allowed_db_path(path):
            continue
        seen.add(path)
        try:
            stat = path.stat()
            schema = get_schema(path, include_counts=False)
            comparison = compare_schema_data(schema)
            databases.append(
                {
                    "id": db_identifier(path),
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "modified_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(stat.st_mtime)),
                    "best_schema_match": comparison["best_match"]["name"],
                    "compatibility": comparison["best_match"]["status"],
                    "tables": sorted(schema.keys()),
                }
            )
        except Exception as exc:
            databases.append({"id": db_identifier(path), "path": str(path), "error": str(exc)})
    return databases


def db_identifier(path: Path) -> str:
    path = normalize_db_path(path)
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def resolve_db_path(value: Optional[str]) -> Path:
    if not value:
        default_path = choose_default_database_path()
        if default_path:
            return default_path
        raise MCPError(
            "No database found. Create project output/databases/*.db files, "
            "or pass --db for an explicit SQLite database."
        )

    requested = Path(str(value)).expanduser()
    if not requested.is_absolute():
        direct = PROJECT_ROOT / requested
        if direct.exists():
            requested = direct
        else:
            matches = [Path(item["path"]) for item in discover_databases() if item.get("id") == str(value)]
            if matches:
                requested = matches[0]

    path = normalize_db_path(requested)
    if not path.exists() or not path.is_file():
        raise MCPError(f"Database not found: {path}")
    if path.suffix.lower() not in DB_SUFFIXES:
        raise MCPError("Only SQLite database files are allowed.")
    if not is_allowed_db_path(path):
        raise MCPError("Database path is not allowed. Use --db or ZSXQ_MCP_ALLOW_ANY_DB=1.")
    return path


def readonly_authorizer(action: int, arg1: str, arg2: str, db_name: str, source: str) -> int:
    if action in SQL_DENY_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA:
        pragma_name = (arg1 or "").lower()
        if pragma_name not in ALLOWED_PRAGMAS:
            return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def connect_readonly(path: Path, timeout_seconds: float = 8.0) -> sqlite3.Connection:
    # 使用 file URI 的只读模式，并额外开启 query_only 与 authorizer 双保险。
    uri_path = quote(str(path).replace("\\", "/"), safe="/:")
    conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True, timeout=timeout_seconds)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.set_authorizer(readonly_authorizer)
    return conn


def apply_query_timeout(conn: sqlite3.Connection, timeout_seconds: float = 8.0) -> None:
    deadline = time.monotonic() + timeout_seconds

    def progress_handler() -> int:
        return 1 if time.monotonic() > deadline else 0

    conn.set_progress_handler(progress_handler, 10000)


def get_table_names(path: Path) -> List[str]:
    with connect_readonly(path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [row["name"] for row in rows]


def get_schema(path: Path, include_counts: bool = True) -> Dict[str, Dict[str, Any]]:
    schema: Dict[str, Dict[str, Any]] = {}
    with connect_readonly(path) as conn:
        apply_query_timeout(conn)
        tables = conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for table in tables:
            name = table["name"]
            columns = conn.execute(f'PRAGMA table_info("{name}")').fetchall()
            entry = {
                "sql": table["sql"],
                "columns": [
                    {
                        "name": column["name"],
                        "type": column["type"],
                        "not_null": bool(column["notnull"]),
                        "default": column["dflt_value"],
                        "primary_key": bool(column["pk"]),
                    }
                    for column in columns
                ],
            }
            if include_counts:
                entry["row_count"] = conn.execute(f'SELECT COUNT(*) AS count FROM "{name}"').fetchone()["count"]
            schema[name] = entry
    return schema


def compare_schema_data(actual_schema: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    comparisons = []
    actual_tables = set(actual_schema.keys())
    for expected_name, expected_schema in EXPECTED_SCHEMAS.items():
        expected_tables = set(expected_schema.keys())
        missing_tables = sorted(expected_tables - actual_tables)
        extra_tables = sorted(actual_tables - expected_tables)
        column_diffs = []
        matched_columns = 0
        expected_columns_total = 0

        for table_name, expected_columns in expected_schema.items():
            expected_columns_total += len(expected_columns)
            actual_columns = [
                column["name"] for column in actual_schema.get(table_name, {}).get("columns", [])
            ]
            actual_column_set = set(actual_columns)
            expected_column_set = set(expected_columns)
            matched_columns += len(expected_column_set & actual_column_set)
            missing_columns = [column for column in expected_columns if column not in actual_column_set]
            extra_columns = [column for column in actual_columns if column not in expected_column_set]
            if missing_columns or extra_columns:
                column_diffs.append(
                    {
                        "table": table_name,
                        "missing_columns": missing_columns,
                        "extra_columns": extra_columns,
                    }
                )

        table_score = len(expected_tables & actual_tables) / max(len(expected_tables), 1)
        column_score = matched_columns / max(expected_columns_total, 1)
        score = round((table_score * 0.45) + (column_score * 0.55), 4)
        exact = not missing_tables and not extra_tables and not column_diffs
        compatible = not missing_tables and not any(item["missing_columns"] for item in column_diffs)
        status = "exact" if exact else "compatible" if compatible else "mismatch"
        comparisons.append(
            {
                "name": expected_name,
                "score": score,
                "status": status,
                "missing_tables": missing_tables,
                "extra_tables": extra_tables,
                "column_diffs": column_diffs,
            }
        )

    comparisons.sort(key=lambda item: (item["score"], item["status"] == "exact"), reverse=True)
    return {"best_match": comparisons[0], "comparisons": comparisons}


def plain_text(text: Any) -> str:
    if text is None:
        return ""
    value = str(text)

    def replace_title(match: re.Match[str]) -> str:
        return unquote(match.group(1) or "")

    value = re.sub(r'<e\b[^>]*\btitle="([^"]*)"[^>]*\/?>', replace_title, value)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def snippet(text: Any, keyword: str = "", max_chars: int = 240) -> str:
    value = plain_text(text)
    if not value:
        return ""
    if keyword:
        index = value.lower().find(keyword.lower())
        if index >= 0:
            start = max(0, index - max_chars // 3)
            value = value[start : start + max_chars]
            if start:
                value = "..." + value
    if len(value) > max_chars:
        value = value[:max_chars].rstrip() + "..."
    return value


def has_table(path: Path, table_name: str) -> bool:
    return table_name in get_table_names(path)


def extract_group_id_from_path(path: Path) -> Optional[str]:
    """从输出数据库文件名或父目录中提取群组 ID。"""
    match = re.search(r"zsxq_(?:topics|files|columns)_(\d+)\.db$", path.name, re.I)
    if match:
        return match.group(1)
    if path.parent.name.isdigit():
        return path.parent.name
    return None


def database_kind(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("zsxq_topics_"):
        return "topics"
    if name.startswith("zsxq_files_"):
        return "files"
    if name.startswith("zsxq_columns_"):
        return "columns"
    return "sqlite"


def output_topic_database_paths(group_ids: Optional[Sequence[str]] = None) -> List[Path]:
    allowed = {str(group_id) for group_id in group_ids} if group_ids else None
    paths = []
    for path in output_database_paths("zsxq_topics_*.db"):
        group_id = extract_group_id_from_path(path)
        if allowed is None or (group_id and group_id in allowed):
            paths.append(path)
    return paths


def scalar_count(path: Path, table_name: str, where_sql: str = "", params: Sequence[Any] = ()) -> int:
    try:
        with connect_readonly(path) as conn:
            apply_query_timeout(conn)
            sql = f'SELECT COUNT(*) AS count FROM "{table_name}" {where_sql}'
            row = conn.execute(sql, params).fetchone()
        return int(row["count"]) if row else 0
    except Exception:
        return 0


def first_group_record(path: Path, group_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not has_table(path, "groups"):
        return None
    try:
        with connect_readonly(path) as conn:
            apply_query_timeout(conn)
            row = None
            if group_id:
                row = conn.execute("SELECT * FROM groups WHERE group_id = ? LIMIT 1", [group_id]).fetchone()
            if row is None:
                row = conn.execute("SELECT * FROM groups LIMIT 1").fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def discover_groups() -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for path in output_database_paths("*.db"):
        group_id = extract_group_id_from_path(path)
        if not group_id:
            continue
        kind = database_kind(path)
        entry = groups.setdefault(
            group_id,
            {
                "group_id": group_id,
                "name": None,
                "type": None,
                "databases": {},
                "stats": {
                    "topics": 0,
                    "users": 0,
                    "comments": 0,
                    "files": 0,
                    "columns": 0,
                    "column_details": 0,
                },
            },
        )
        entry["databases"][kind] = db_identifier(path)

        stat = entry["stats"]
        if kind == "topics":
            stat["topics"] = scalar_count(path, "topics")
            stat["users"] = scalar_count(path, "users")
            stat["comments"] = scalar_count(path, "comments")
        elif kind == "files":
            stat["files"] = scalar_count(path, "files")
        elif kind == "columns":
            stat["columns"] = scalar_count(path, "columns")
            stat["column_details"] = scalar_count(path, "topic_details")

        group_record = first_group_record(path, group_id)
        if group_record:
            entry["name"] = entry["name"] or group_record.get("name")
            entry["type"] = entry["type"] or group_record.get("type")

    return sorted(
        groups.values(),
        key=lambda item: (
            int(item["stats"].get("topics", 0) or 0)
            + int(item["stats"].get("files", 0) or 0)
            + int(item["stats"].get("column_details", 0) or 0)
        ),
        reverse=True,
    )


def resolve_group_ids(value: Any) -> Optional[List[str]]:
    if value is None or value == "":
        return None
    if isinstance(value, (str, int)):
        return [str(value)]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    raise MCPError("group_ids must be a string, number, or array.")


def database_stats(path: Path) -> Dict[str, Any]:
    schema = get_schema(path, include_counts=True)
    comparison = compare_schema_data(schema)
    stats: Dict[str, Any] = {
        "database": db_identifier(path),
        "path": str(path),
        "schema_match": comparison["best_match"],
        "tables": {name: item["row_count"] for name, item in schema.items()},
    }

    with connect_readonly(path) as conn:
        apply_query_timeout(conn)
        table_names = set(schema.keys())
        if "groups" in table_names:
            stats["groups"] = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM groups ORDER BY group_id LIMIT 50"
                ).fetchall()
            ]
        if "topics" in table_names:
            stats["topics"] = {
                "total": conn.execute("SELECT COUNT(*) AS count FROM topics").fetchone()["count"],
                "time_range": dict(
                    conn.execute(
                        "SELECT MIN(create_time) AS oldest, MAX(create_time) AS newest FROM topics"
                    ).fetchone()
                ),
                "by_type": [
                    dict(row)
                    for row in conn.execute(
                        "SELECT type, COUNT(*) AS count FROM topics GROUP BY type ORDER BY count DESC"
                    ).fetchall()
                ],
            }
        if "topic_details" in table_names:
            stats["column_topics"] = {
                "total": conn.execute("SELECT COUNT(*) AS count FROM topic_details").fetchone()["count"],
                "time_range": dict(
                    conn.execute(
                        "SELECT MIN(create_time) AS oldest, MAX(create_time) AS newest FROM topic_details"
                    ).fetchone()
                ),
            }
        if "files" in table_names:
            columns = [column["name"] for column in schema["files"]["columns"]]
            if "download_status" in columns:
                stats["files"] = {
                    "total": conn.execute("SELECT COUNT(*) AS count FROM files").fetchone()["count"],
                    "by_status": [
                        dict(row)
                        for row in conn.execute(
                            "SELECT download_status, COUNT(*) AS count "
                            "FROM files GROUP BY download_status ORDER BY count DESC"
                        ).fetchall()
                    ],
                }
    return stats


def validate_readonly_sql(sql: str) -> str:
    statement = (sql or "").strip()
    if not statement:
        raise MCPError("SQL is required.")
    if "\x00" in statement:
        raise MCPError("SQL contains invalid characters.")
    if ";" in statement.rstrip(";"):
        raise MCPError("Only one SQL statement is allowed.")
    first_token = re.match(r"^\s*(?:--[^\n]*\n|\s|/\*.*?\*/)*([A-Za-z]+)", statement, re.S)
    keyword = first_token.group(1).lower() if first_token else ""
    if keyword not in {"select", "with", "pragma", "explain"}:
        raise MCPError("Only read-only SELECT, WITH, EXPLAIN, and safe PRAGMA statements are allowed.")
    return statement.rstrip(";")


def execute_readonly_sql(
    path: Path, sql: str, params: Any = None, limit: int = DEFAULT_LIMIT
) -> Dict[str, Any]:
    statement = validate_readonly_sql(sql)
    limit = clamp_limit(limit)
    if params is None:
        params = []
    if not isinstance(params, (list, tuple, dict)):
        raise MCPError("Params must be an array or object.")

    with connect_readonly(path) as conn:
        apply_query_timeout(conn)
        cursor = conn.execute(statement, params)
        rows = cursor.fetchmany(limit + 1)
        columns = [desc[0] for desc in cursor.description or []]
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {
            "database": db_identifier(path),
            "columns": columns,
            "rows": [row_to_dict(cursor, row) for row in rows],
            "row_count": len(rows),
            "has_more": has_more,
        }


def search_topics(path: Path, query: str, limit: int = DEFAULT_LIMIT, offset: int = 0) -> Dict[str, Any]:
    if not query or not str(query).strip():
        raise MCPError("Query is required.")
    if not has_table(path, "topics"):
        raise MCPError("The selected database does not contain a topics table.")

    limit = clamp_limit(limit)
    offset = max(0, int(offset or 0))
    like = f"%{query}%"
    sql = """
        SELECT
            t.topic_id,
            t.group_id,
            t.type,
            t.title,
            t.create_time,
            t.likes_count,
            t.comments_count,
            t.reading_count,
            (SELECT text FROM talks WHERE topic_id = t.topic_id LIMIT 1) AS talk_text,
            (SELECT text FROM questions WHERE topic_id = t.topic_id LIMIT 1) AS question_text,
            (SELECT text FROM answers WHERE topic_id = t.topic_id LIMIT 1) AS answer_text
        FROM topics t
        WHERE
            COALESCE(t.title, '') LIKE ?
            OR EXISTS (SELECT 1 FROM talks WHERE topic_id = t.topic_id AND COALESCE(text, '') LIKE ?)
            OR EXISTS (SELECT 1 FROM questions WHERE topic_id = t.topic_id AND COALESCE(text, '') LIKE ?)
            OR EXISTS (SELECT 1 FROM answers WHERE topic_id = t.topic_id AND COALESCE(text, '') LIKE ?)
            OR EXISTS (SELECT 1 FROM comments WHERE topic_id = t.topic_id AND COALESCE(text, '') LIKE ?)
        ORDER BY t.create_time DESC
        LIMIT ? OFFSET ?
    """

    with connect_readonly(path) as conn:
        apply_query_timeout(conn, timeout_seconds=12.0)
        rows = conn.execute(sql, [like, like, like, like, like, limit + 1, offset]).fetchall()
    has_more = len(rows) > limit
    results = []
    for row in rows[:limit]:
        text_source = row["talk_text"] or row["question_text"] or row["answer_text"] or row["title"]
        results.append(
            {
                "topic_id": str(row["topic_id"]) if row["topic_id"] is not None else None,
                "group_id": row["group_id"],
                "type": row["type"],
                "title": row["title"],
                "create_time": row["create_time"],
                "likes_count": row["likes_count"],
                "comments_count": row["comments_count"],
                "reading_count": row["reading_count"],
                "snippet": snippet(text_source, query),
            }
        )
    return {"database": db_identifier(path), "query": query, "results": results, "has_more": has_more}


def get_topic_detail(path: Path, topic_id: Any, comments_limit: int = 50) -> Dict[str, Any]:
    if topic_id is None or str(topic_id).strip() == "":
        raise MCPError("topic_id is required.")
    if not has_table(path, "topics"):
        raise MCPError("The selected database does not contain a topics table.")

    comments_limit = clamp_limit(comments_limit, default=50)
    with connect_readonly(path) as conn:
        apply_query_timeout(conn)
        topic_row = conn.execute("SELECT * FROM topics WHERE topic_id = ?", [topic_id]).fetchone()
        if not topic_row:
            raise MCPError("Topic not found.")
        detail = {"topic": dict(topic_row)}

        if "groups" in get_table_names(path):
            group_row = conn.execute("SELECT * FROM groups WHERE group_id = ?", [topic_row["group_id"]]).fetchone()
            detail["group"] = dict(group_row) if group_row else None

        detail["talk"] = first_row(conn, "SELECT * FROM talks WHERE topic_id = ? ORDER BY id LIMIT 1", [topic_id])
        if detail["talk"] and detail["talk"].get("owner_user_id"):
            detail["talk_owner"] = first_row(
                conn, "SELECT * FROM users WHERE user_id = ?", [detail["talk"]["owner_user_id"]]
            )
        detail["question"] = first_row(conn, "SELECT * FROM questions WHERE topic_id = ? LIMIT 1", [topic_id])
        detail["answer"] = first_row(conn, "SELECT * FROM answers WHERE topic_id = ? LIMIT 1", [topic_id])
        detail["articles"] = all_rows(conn, "SELECT * FROM articles WHERE topic_id = ? ORDER BY id", [topic_id])
        detail["images"] = all_rows(conn, "SELECT * FROM images WHERE topic_id = ? ORDER BY image_id", [topic_id])
        detail["files"] = all_rows(conn, "SELECT * FROM topic_files WHERE topic_id = ? ORDER BY id", [topic_id])
        detail["like_emojis"] = all_rows(
            conn, "SELECT emoji_key, likes_count FROM like_emojis WHERE topic_id = ? ORDER BY likes_count DESC", [topic_id]
        )
        detail["comments"] = all_rows(
            conn,
            """
            SELECT c.*, u.name AS owner_name, r.name AS repliee_name
            FROM comments c
            LEFT JOIN users u ON c.owner_user_id = u.user_id
            LEFT JOIN users r ON c.repliee_user_id = r.user_id
            WHERE c.topic_id = ?
            ORDER BY c.create_time ASC
            LIMIT ?
            """,
            [topic_id, comments_limit],
        )
        if has_table(path, "tags"):
            detail["tags"] = all_rows(
                conn,
                """
                SELECT tg.*
                FROM tags tg
                JOIN topic_tags tt ON tt.tag_id = tg.tag_id
                WHERE tt.topic_id = ?
                ORDER BY tg.topic_count DESC, tg.tag_name ASC
                """,
                [topic_id],
            )
    return {"database": db_identifier(path), "detail": detail}


def first_row(conn: sqlite3.Connection, sql: str, params: Sequence[Any]) -> Optional[Dict[str, Any]]:
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    return row_to_dict(cursor, row) if row else None


def all_rows(conn: sqlite3.Connection, sql: str, params: Sequence[Any]) -> List[Dict[str, Any]]:
    cursor = conn.execute(sql, params)
    return [row_to_dict(cursor, row) for row in cursor.fetchall()]


def tool_list_databases(arguments: Dict[str, Any]) -> Dict[str, Any]:
    return {"project_root": str(PROJECT_ROOT), "databases": discover_databases()}


def tool_list_groups(arguments: Dict[str, Any]) -> Dict[str, Any]:
    groups = discover_groups()
    return {"project_root": str(PROJECT_ROOT), "groups": groups, "total": len(groups)}


def tool_group_database_stats(arguments: Dict[str, Any]) -> Dict[str, Any]:
    group_id = str(arguments.get("group_id", "")).strip()
    if not group_id:
        raise MCPError("group_id is required.")

    groups = {item["group_id"]: item for item in discover_groups()}
    if group_id not in groups:
        raise MCPError(f"Group not found in output/databases: {group_id}")

    group = groups[group_id]
    detailed: Dict[str, Any] = {}
    for kind, db_id in group.get("databases", {}).items():
        try:
            detailed[kind] = database_stats(resolve_db_path(db_id))
        except Exception as exc:
            detailed[kind] = {"error": str(exc), "database": db_id}

    return {"group": group, "databases": detailed}


def tool_database_stats(arguments: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_db_path(arguments.get("db_path"))
    return database_stats(path)


def tool_schema_summary(arguments: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_db_path(arguments.get("db_path"))
    include_counts = bool(arguments.get("include_counts", True))
    schema = get_schema(path, include_counts=include_counts)
    return {
        "database": db_identifier(path),
        "path": str(path),
        "schema": schema,
        "comparison": compare_schema_data(schema),
    }


def tool_compare_project_schema(arguments: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_db_path(arguments.get("db_path"))
    schema = get_schema(path, include_counts=False)
    return {"database": db_identifier(path), "path": str(path), **compare_schema_data(schema)}


def tool_query_sql(arguments: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_db_path(arguments.get("db_path"))
    return execute_readonly_sql(
        path,
        arguments.get("sql", ""),
        arguments.get("params"),
        clamp_limit(arguments.get("limit"), default=DEFAULT_LIMIT),
    )


def tool_search_topics(arguments: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_db_path(arguments.get("db_path"))
    return search_topics(
        path,
        str(arguments.get("query", "")),
        clamp_limit(arguments.get("limit"), default=DEFAULT_LIMIT),
        int(arguments.get("offset", 0) or 0),
    )


def tool_search_topics_all_groups(arguments: Dict[str, Any]) -> Dict[str, Any]:
    group_ids = resolve_group_ids(arguments.get("group_ids"))
    query = str(arguments.get("query", ""))
    if not query.strip():
        raise MCPError("Query is required.")

    limit = clamp_limit(arguments.get("limit"), default=DEFAULT_LIMIT)
    offset = max(0, int(arguments.get("offset", 0) or 0))
    per_database_limit = clamp_limit(limit + offset, default=DEFAULT_LIMIT)
    topic_databases = output_topic_database_paths(group_ids)

    results: List[Dict[str, Any]] = []
    searched_groups = []
    for path in topic_databases:
        group_id = extract_group_id_from_path(path)
        searched_groups.append(group_id)
        try:
            search_result = search_topics(path, query, limit=per_database_limit, offset=0)
        except Exception as exc:
            results.append(
                {
                    "group_id": group_id,
                    "database": db_identifier(path),
                    "error": str(exc),
                }
            )
            continue

        for item in search_result.get("results", []):
            item["database"] = db_identifier(path)
            item["source_group_id"] = group_id
            results.append(item)

    successful_results = [item for item in results if "error" not in item]
    errors = [item for item in results if "error" in item]
    successful_results.sort(key=lambda item: item.get("create_time") or "", reverse=True)
    paged_results = successful_results[offset : offset + limit]

    return {
        "query": query,
        "searched_groups": [group_id for group_id in searched_groups if group_id],
        "results": paged_results,
        "errors": errors,
        "total_matched_returned": len(successful_results),
        "has_more": len(successful_results) > offset + limit,
    }


def tool_get_topic_detail(arguments: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_db_path(arguments.get("db_path"))
    return get_topic_detail(path, arguments.get("topic_id"), clamp_limit(arguments.get("comments_limit"), default=50))


def tool_get_topic_detail_any_group(arguments: Dict[str, Any]) -> Dict[str, Any]:
    topic_id = arguments.get("topic_id")
    if topic_id is None or str(topic_id).strip() == "":
        raise MCPError("topic_id is required.")

    group_ids = resolve_group_ids(arguments.get("group_ids"))
    comments_limit = clamp_limit(arguments.get("comments_limit"), default=50)
    matches = []
    for path in output_topic_database_paths(group_ids):
        try:
            detail = get_topic_detail(path, topic_id, comments_limit)
        except MCPError as exc:
            if "Topic not found" in str(exc):
                continue
            matches.append({"database": db_identifier(path), "error": str(exc)})
            continue
        detail["source_group_id"] = extract_group_id_from_path(path)
        matches.append(detail)

    if not matches:
        raise MCPError("Topic not found in output/databases topic databases.")

    return {"topic_id": str(topic_id), "matches": matches, "count": len(matches)}


TOOLS: Dict[str, Dict[str, Any]] = {
    "list_databases": {
        "description": "List ZSXQCrawler content databases discovered under output/databases.",
        "handler": tool_list_databases,
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "list_groups": {
        "description": "List groups discovered under output/databases with their topics/files/columns databases and counts.",
        "handler": tool_list_groups,
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "group_database_stats": {
        "description": "Return combined topics/files/columns database stats for one group id.",
        "handler": tool_group_database_stats,
        "inputSchema": {
            "type": "object",
            "required": ["group_id"],
            "properties": {"group_id": {"type": "string", "description": "Knowledge Planet group id."}},
            "additionalProperties": False,
        },
    },
    "database_stats": {
        "description": "Return table counts and high-level content statistics for a database.",
        "handler": tool_database_stats,
        "inputSchema": {
            "type": "object",
            "properties": {"db_path": {"type": "string", "description": "Database id or path. Defaults to an output/databases content database."}},
            "additionalProperties": False,
        },
    },
    "schema_summary": {
        "description": "Inspect SQLite tables, columns, row counts, and project schema compatibility.",
        "handler": tool_schema_summary,
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string", "description": "Database id or path. Defaults to an output/databases content database."},
                "include_counts": {"type": "boolean", "default": True},
            },
            "additionalProperties": False,
        },
    },
    "compare_project_schema": {
        "description": "Compare a database against ZSXQCrawler topics/files/columns schemas.",
        "handler": tool_compare_project_schema,
        "inputSchema": {
            "type": "object",
            "properties": {"db_path": {"type": "string", "description": "Database id or path. Defaults to an output/databases content database."}},
            "additionalProperties": False,
        },
    },
    "query_sql": {
        "description": "Run a read-only SQL query with authorizer protection and row limits.",
        "handler": tool_query_sql,
        "inputSchema": {
            "type": "object",
            "required": ["sql"],
            "properties": {
                "db_path": {"type": "string", "description": "Database id or path. Defaults to an output/databases content database."},
                "sql": {"type": "string", "description": "Read-only SELECT/WITH/EXPLAIN/safe PRAGMA SQL."},
                "params": {
                    "description": "Optional SQLite positional array or named object parameters.",
                    "oneOf": [{"type": "array"}, {"type": "object"}],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": DEFAULT_LIMIT},
            },
            "additionalProperties": False,
        },
    },
    "search_topics": {
        "description": "Search topic title, body, questions, answers, and comments.",
        "handler": tool_search_topics,
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "db_path": {"type": "string", "description": "Database id or path. Defaults to an output/databases content database."},
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": DEFAULT_LIMIT},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            },
            "additionalProperties": False,
        },
    },
    "search_topics_all_groups": {
        "description": "Search topics across all output/databases topic databases, optionally restricted by group ids.",
        "handler": tool_search_topics_all_groups,
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "group_ids": {
                    "description": "Optional group id or array of group ids.",
                    "oneOf": [{"type": "string"}, {"type": "number"}, {"type": "array"}],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": DEFAULT_LIMIT},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            },
            "additionalProperties": False,
        },
    },
    "get_topic_detail": {
        "description": "Return a topic with talk/question/answer/comments/images/files/tags.",
        "handler": tool_get_topic_detail,
        "inputSchema": {
            "type": "object",
            "required": ["topic_id"],
            "properties": {
                "db_path": {"type": "string", "description": "Database id or path. Defaults to an output/databases content database."},
                "topic_id": {"description": "Topic id as string or number."},
                "comments_limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": 50},
            },
            "additionalProperties": False,
        },
    },
    "get_topic_detail_any_group": {
        "description": "Find a topic id across output/databases topic databases and return matching details.",
        "handler": tool_get_topic_detail_any_group,
        "inputSchema": {
            "type": "object",
            "required": ["topic_id"],
            "properties": {
                "topic_id": {"description": "Topic id as string or number."},
                "group_ids": {
                    "description": "Optional group id or array of group ids.",
                    "oneOf": [{"type": "string"}, {"type": "number"}, {"type": "array"}],
                },
                "comments_limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": 50},
            },
            "additionalProperties": False,
        },
    },
}


def content_text(payload: Any) -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ]
    }


def handle_initialize(message: Dict[str, Any]) -> Dict[str, Any]:
    params = message.get("params") or {}
    requested_version = params.get("protocolVersion")
    return {
        "protocolVersion": requested_version or PROTOCOL_VERSION,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


def handle_tools_list(message: Dict[str, Any]) -> Dict[str, Any]:
    tools = []
    for name, definition in TOOLS.items():
        tools.append(
            {
                "name": name,
                "description": definition["description"],
                "inputSchema": definition["inputSchema"],
            }
        )
    return {"tools": tools}


def handle_tools_call(message: Dict[str, Any]) -> Dict[str, Any]:
    params = message.get("params") or {}
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if name not in TOOLS:
        raise MCPError(f"Unknown tool: {name}")
    handler: Callable[[Dict[str, Any]], Any] = TOOLS[name]["handler"]
    return content_text(handler(arguments))


def handle_request(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = message.get("method")
    if method == "initialize":
        return handle_initialize(message)
    if method == "tools/list":
        return handle_tools_list(message)
    if method == "tools/call":
        return handle_tools_call(message)
    if method == "ping":
        return {}
    if method and method.startswith("notifications/"):
        return None
    raise MCPError(f"Unsupported method: {method}")


def jsonrpc_response(message_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def jsonrpc_error(message_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": message_id, "error": error}


def serve_stdio() -> int:
    for raw_line in sys.stdin.buffer:
        line = raw_line.decode("utf-8-sig", errors="replace").strip()
        if not line:
            continue
        message_id = None
        try:
            message = json.loads(line)
            message_id = message.get("id")
            result = handle_request(message)
            if message_id is not None and result is not None:
                emit(jsonrpc_response(message_id, result))
        except MCPError as exc:
            if message_id is not None:
                emit(jsonrpc_error(message_id, -32000, str(exc)))
        except sqlite3.DatabaseError as exc:
            if message_id is not None:
                emit(jsonrpc_error(message_id, -32001, "Database error.", str(exc)))
        except Exception as exc:  # noqa: BLE001
            stderr(f"Unhandled error: {exc}")
            if message_id is not None:
                emit(jsonrpc_error(message_id, -32603, "Internal error.", str(exc)))
    return 0


def emit(payload: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZSXQCrawler SQLite MCP stdio server")
    parser.add_argument(
        "--db",
        default=None,
        help=(
            "Explicit default SQLite database path. When omitted, project mode "
            "auto-discovers output/databases; standalone mode auto-discovers a same-folder SQLite file."
        ),
    )
    parser.add_argument(
        "--allow-any-db",
        action="store_true",
        help="Allow tools to open any SQLite path passed by the client.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=MAX_LIMIT,
        help=f"Maximum rows returned by query tools. Default: {MAX_LIMIT}.",
    )
    return parser.parse_args(argv)


def configure_from_args(args: argparse.Namespace) -> None:
    global CONFIG
    default_db = Path(args.db).expanduser() if args.db else None
    if default_db and not default_db.is_absolute():
        default_db = PROJECT_ROOT / default_db
    CONFIG = ServerConfig(default_db, bool(args.allow_any_db), int(args.max_rows or MAX_LIMIT))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_from_args(args)
    if CONFIG.default_db and not CONFIG.default_db.exists():
        stderr(f"Default database does not exist: {CONFIG.default_db}")
    return serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())

