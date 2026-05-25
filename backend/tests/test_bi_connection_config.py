"""Tests for BI connection config builder."""
import pytest

from tars.bi.connection_config import (
    ConnectionConfig,
    build_connection_url,
    config_from_payload,
    parse_connection_url,
    to_public_dict,
)


class TestBuildConnectionUrl:
    def test_mysql(self):
        cfg = ConnectionConfig(
            db_type="mysql",
            host="192.168.1.10",
            port=3306,
            username="root",
            password="p@ss",
            database="analytics",
        )
        url = build_connection_url(cfg)
        assert url.startswith("mysql+pymysql://")
        assert "192.168.1.10:3306/analytics" in url
        assert "charset=utf8mb4" in url
        assert "root" in url

    def test_postgresql_default_port(self):
        cfg = ConnectionConfig(
            db_type="postgresql",
            host="db.local",
            username="pg",
            password="secret",
            database="warehouse",
        )
        url = build_connection_url(cfg)
        assert "postgresql+psycopg2://" in url
        assert "db.local:5432/warehouse" in url

    def test_sqlite_path(self):
        cfg = ConnectionConfig(db_type="sqlite", database="/tmp/demo.db")
        assert build_connection_url(cfg) == "sqlite:////tmp/demo.db"

    def test_round_trip_mysql(self):
        original = ConnectionConfig(
            db_type="mysql",
            host="10.0.0.8",
            port=3307,
            username="bi_user",
            password="x/y",
            database="orders",
        )
        url = build_connection_url(original)
        parsed = parse_connection_url(url, "mysql")
        assert parsed.host == "10.0.0.8"
        assert parsed.port == 3307
        assert parsed.username == "bi_user"
        assert parsed.password == "x/y"
        assert parsed.database == "orders"


class TestConfigFromPayload:
    def test_structured_fields(self):
        cfg, url = config_from_payload(
            db_type="mysql",
            host="127.0.0.1",
            port=3306,
            username="root",
            password="pwd",
            database="demo",
        )
        assert cfg.database == "demo"
        assert "mysql+pymysql://" in url

    def test_legacy_url(self):
        cfg, url = config_from_payload(
            db_type="sqlite",
            connection_url="sqlite:////tmp/legacy.db",
        )
        assert cfg.normalized_db_type() == "sqlite"
        assert url.endswith("/tmp/legacy.db")

    def test_public_dict_masks_password(self):
        cfg = ConnectionConfig(db_type="mysql", password="secret", database="d", host="h")
        public = to_public_dict(cfg)
        assert "password" not in public
        assert public["has_password"] is True
