"""BI 数据源连接配置 — 表单字段 ↔ SQLAlchemy URL"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote, unquote, urlparse, urlunparse, urlencode

DEFAULT_PORTS: dict[str, int] = {
    "mysql": 3306,
    "doris": 9030,
    "postgresql": 5432,
    "oracle": 1521,
    "sqlserver": 1433,
    "clickhouse": 8123,
    "sqlite": 0,
    "jdbc": 0,
}

DB_TYPE_ALIASES = {
    "mysql": "mysql",
    "mariadb": "mysql",
    "doris": "doris",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "oracle": "oracle",
    "sqlserver": "sqlserver",
    "mssql": "sqlserver",
    "clickhouse": "clickhouse",
    "sqlite": "sqlite",
    "jdbc": "jdbc",
}


@dataclass
class ConnectionConfig:
    db_type: str
    host: str = "127.0.0.1"
    port: Optional[int] = None
    username: str = ""
    password: str = ""
    database: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def normalized_db_type(self) -> str:
        return DB_TYPE_ALIASES.get((self.db_type or "").lower(), (self.db_type or "mysql").lower())

    def resolved_port(self) -> Optional[int]:
        if self.port is not None:
            return self.port
        return DEFAULT_PORTS.get(self.normalized_db_type())

    def validate(self) -> None:
        db_type = self.normalized_db_type()
        if db_type == "sqlite":
            if not (self.database or "").strip():
                raise ValueError("SQLite 请填写数据库文件路径")
            return
        if not (self.host or "").strip():
            raise ValueError("请填写服务器地址")
        if not (self.database or "").strip():
            raise ValueError("请填写数据库名")


def build_connection_url(config: ConnectionConfig) -> str:
    """从传统连接字段构建 SQLAlchemy URL。"""
    config.validate()
    db_type = config.normalized_db_type()

    if db_type == "sqlite":
        path = config.database.strip()
        if path.startswith("sqlite:"):
            return path
        if path.startswith("/"):
            return f"sqlite:///{path}"
        return f"sqlite:///{path}"

    user = quote(config.username or "", safe="")
    password = quote(config.password or "", safe="")
    host = (config.host or "127.0.0.1").strip()
    port = config.resolved_port()
    database = quote(config.database.strip(), safe="")

    auth = ""
    if user or password:
        auth = f"{user}:{password}@"

    if db_type == "mysql":
        driver = "mysql+pymysql"
    elif db_type == "doris":
        driver = "mysql+pymysql"
    elif db_type == "postgresql":
        driver = "postgresql+psycopg2"
    elif db_type == "oracle":
        driver = "oracle+cx_oracle"
    elif db_type == "sqlserver":
        driver = "mssql+pyodbc"
    elif db_type == "clickhouse":
        driver = "clickhouse+http"
    elif db_type == "jdbc":
        driver = "jdbc"
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")

    if db_type == "oracle":
        service = config.database.strip()
        netloc = f"{auth}{host}:{port}" if port else f"{auth}{host}"
        query = f"service_name={quote(service, safe='')}"
        return urlunparse((driver, netloc, "", "", query, ""))

    if db_type == "sqlserver":
        netloc = f"{auth}{host}:{port}" if port else f"{auth}{host}"
        query = "driver=ODBC+Driver+17+for+SQL+Server"
        return urlunparse((driver, netloc, f"/{database}", "", query, ""))

    netloc = f"{auth}{host}:{port}" if port else f"{auth}{host}"
    path = f"/{database}"
    if db_type in ("mysql", "doris"):
        query = urlencode({"charset": "utf8mb4"})
        return urlunparse((driver, netloc, path, "", query, ""))
    return urlunparse((driver, netloc, path, "", "", ""))


def parse_connection_url(connection_url: str, db_type: str = "") -> ConnectionConfig:
    """从已有 URL 反解析连接字段（用于编辑/展示）。"""
    url = (connection_url or "").strip()
    hint = DB_TYPE_ALIASES.get((db_type or "").lower(), (db_type or "").lower())

    if url.startswith("sqlite:"):
        parsed = urlparse(url)
        if parsed.path:
            db_path = parsed.path
        else:
            db_path = url.replace("sqlite:///", "").replace("sqlite://", "")
        return ConnectionConfig(db_type="sqlite", database=unquote(db_path))

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").split("+")[0].lower()
    resolved_type = hint or scheme
    if scheme == "mysql" and hint == "doris":
        resolved_type = "doris"
    elif scheme in ("postgresql", "postgres"):
        resolved_type = "postgresql"
    elif scheme in ("mssql", "sqlserver"):
        resolved_type = "sqlserver"

    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    database = unquote((parsed.path or "").lstrip("/"))

    if resolved_type == "oracle" and not database and parsed.query:
        for part in parsed.query.split("&"):
            if part.startswith("service_name="):
                database = unquote(part.split("=", 1)[1])

    return ConnectionConfig(
        db_type=resolved_type or "mysql",
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
    )


def config_from_payload(
    *,
    db_type: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    connection_url: Optional[str] = None,
) -> tuple[ConnectionConfig, str]:
    """解析 API 请求：优先结构化字段，兼容 legacy connection_url。"""
    if connection_url and not any(v is not None for v in (host, port, username, password, database)):
        cfg = parse_connection_url(connection_url, db_type)
        return cfg, connection_url.strip()

    cfg = ConnectionConfig(
        db_type=db_type,
        host=(host or "127.0.0.1").strip(),
        port=port,
        username=(username or "").strip(),
        password=password or "",
        database=(database or "").strip(),
    )
    return cfg, build_connection_url(cfg)


def to_public_dict(config: ConnectionConfig, *, mask_password: bool = True) -> dict[str, Any]:
    """返回可安全下发前端的连接信息（默认不返回明文密码）。"""
    data: dict[str, Any] = {
        "db_type": config.normalized_db_type(),
        "host": config.host,
        "port": config.resolved_port(),
        "username": config.username,
        "database": config.database,
        "has_password": bool(config.password),
    }
    if not mask_password:
        data["password"] = config.password
    return data


def serialize_stored_config(raw: Optional[str], connection_url: str, db_type: str) -> dict[str, Any]:
    if raw:
        import json

        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                cfg = ConnectionConfig(
                    db_type=data.get("db_type") or db_type,
                    host=data.get("host") or "",
                    port=data.get("port"),
                    username=data.get("username") or "",
                    password="",
                    database=data.get("database") or "",
                )
                return to_public_dict(cfg, mask_password=True)
        except (json.JSONDecodeError, TypeError):
            pass
    cfg = parse_connection_url(connection_url, db_type)
    return to_public_dict(cfg, mask_password=True)
