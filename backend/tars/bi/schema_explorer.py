"""Schema 抓取与理解"""
import json
from typing import Dict, Any, List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


class SchemaExplorer:
    """使用 SQLAlchemy 抓取数据库 Schema"""

    SUPPORTED_TYPES = {
        "mysql", "postgresql", "oracle", "sqlserver", "clickhouse", "sqlite", "doris", "jdbc",
    }

    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self._engine: Optional[Engine] = None

    def _get_engine(self) -> Engine:
        if self._engine is None:
            kwargs = {}
            if self.connection_url.startswith("sqlite"):
                kwargs["connect_args"] = {"check_same_thread": False}
            else:
                kwargs["connect_args"] = {"connect_timeout": 10}
                kwargs["execution_options"] = {"isolation_level": "READ COMMITTED"}
            self._engine = create_engine(self.connection_url, **kwargs)
        return self._engine

    def test_connection(self) -> Tuple[bool, str]:
        """测试数据库连接"""
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, "连接成功"
        except Exception as e:
            return False, str(e)

    def explore(self) -> Dict[str, Any]:
        """
        抓取数据库 Schema 信息
        返回: {
            "tables": {
                "table_name": {
                    "columns": [{"name": "...", "type": "...", "nullable": true, "default": "...", "comment": "..."}],
                    "primary_key": ["column_name"],
                    "foreign_keys": [{"column": "...", "referred_table": "...", "referred_column": "..."}],
                    "indexes": [{"name": "...", "columns": ["..."], "unique": false}],
                    "comment": "..."
                }
            }
        }
        """
        engine = self._get_engine()
        inspector = inspect(engine)
        result: Dict[str, Any] = {"tables": {}}

        try:
            table_names = inspector.get_table_names()
        except Exception as e:
            return {"tables": {}, "error": str(e)}

        for table_name in table_names:
            table_info: Dict[str, Any] = {
                "columns": [],
                "primary_key": [],
                "foreign_keys": [],
                "indexes": [],
                "comment": "",
            }

            # 列信息
            try:
                columns = inspector.get_columns(table_name)
                for col in columns:
                    table_info["columns"].append({
                        "name": col.get("name", ""),
                        "type": str(col.get("type", "")),
                        "nullable": col.get("nullable", True),
                        "default": str(col.get("default", "")) if col.get("default") is not None else None,
                        "comment": col.get("comment", ""),
                    })
            except Exception:
                pass

            # 主键
            try:
                pk = inspector.get_pk_constraint(table_name)
                table_info["primary_key"] = pk.get("constrained_columns", [])
            except Exception:
                pass

            # 外键
            try:
                fks = inspector.get_foreign_keys(table_name)
                for fk in fks:
                    referred_table = fk.get("referred_table", "")
                    referred_columns = fk.get("referred_columns", [])
                    constrained_columns = fk.get("constrained_columns", [])
                    for i, col in enumerate(constrained_columns):
                        ref_col = referred_columns[i] if i < len(referred_columns) else ""
                        table_info["foreign_keys"].append({
                            "column": col,
                            "referred_table": referred_table,
                            "referred_column": ref_col,
                        })
            except Exception:
                pass

            # 索引
            try:
                indexes = inspector.get_indexes(table_name)
                for idx in indexes:
                    table_info["indexes"].append({
                        "name": idx.get("name", ""),
                        "columns": idx.get("column_names", []),
                        "unique": idx.get("unique", False),
                    })
            except Exception:
                pass

            # 表注释
            try:
                if hasattr(inspector, "get_table_comment"):
                    comment = inspector.get_table_comment(table_name)
                    if comment:
                        table_info["comment"] = comment.get("text", "")
            except Exception:
                pass

            result["tables"][table_name] = table_info

        return result

    def close(self):
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


from typing import Tuple
