"""SQL 安全校验层"""
import re
import sqlparse
from typing import Set, Tuple


class SQLSecurityChecker:
    """SQL 安全校验器：只允许只读查询"""

    QUERY_STATEMENTS: Set[str] = {"SELECT", "WITH"}
    METADATA_STATEMENTS: Set[str] = {"SHOW", "DESCRIBE", "DESC", "EXPLAIN", "PRAGMA"}
    ALLOWED_STATEMENTS: Set[str] = QUERY_STATEMENTS | METADATA_STATEMENTS
    FORBIDDEN_KEYWORDS: Set[str] = {
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
        "GRANT", "REVOKE", "CREATE", "EXEC", "EXECUTE", "MERGE",
        "REPLACE", "CALL", "LOAD", "COPY", "UNLOAD",
    }

    def __init__(self, max_rows: int = 1000, timeout_seconds: int = 30):
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds

    def _leading_keyword(self, sql: str) -> str:
        stripped = sql.strip()
        if not stripped:
            return ""

        try:
            parsed = sqlparse.parse(stripped)
        except Exception:
            parsed = []

        if parsed:
            for token in parsed[0].tokens:
                if token.is_whitespace:
                    continue
                if token.ttype in (sqlparse.tokens.Comment, sqlparse.tokens.Comment.Multiline):
                    continue
                value = str(token).strip().upper()
                if value:
                    return value.split()[0]

        return stripped.upper().split()[0]

    def _is_query_statement(self, sql: str) -> bool:
        keyword = self._leading_keyword(sql)
        if keyword in self.QUERY_STATEMENTS:
            return True
        try:
            parsed = sqlparse.parse(sql.strip())
            if parsed and parsed[0].get_type().upper() == "SELECT":
                return True
        except Exception:
            pass
        return False

    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        校验 SQL 是否安全
        返回: (是否通过, 错误信息)
        """
        if not sql or not sql.strip():
            return False, "SQL 不能为空"

        stripped = sql.strip()

        # 1. 检查分号（防止多语句注入）
        if ";" in stripped:
            statements = [s.strip() for s in stripped.split(";") if s.strip()]
            if len(statements) > 1:
                return False, "禁止执行多条 SQL 语句"

        # 2. 使用 sqlparse 解析
        try:
            parsed = sqlparse.parse(stripped)
        except Exception as e:
            return False, f"SQL 解析失败: {e}"

        if not parsed:
            return False, "无法解析 SQL"

        keyword = self._leading_keyword(stripped)
        if keyword not in self.ALLOWED_STATEMENTS:
            sql_upper = stripped.upper()
            for forbidden in self.FORBIDDEN_KEYWORDS:
                pattern = r"\b" + forbidden + r"\b"
                if re.search(pattern, sql_upper):
                    return False, f"SQL 包含禁止的操作: {forbidden}"
            return False, f"不支持的 SQL 语句类型: {keyword or '未知'}"

        # 3. 检查注释中的注入（如 /* ... */ 或 --）
        comment_patterns = [
            r"/\*.*?\*/",
            r"--.*?$",
        ]
        for pattern in comment_patterns:
            for match in re.finditer(pattern, stripped, re.MULTILINE | re.DOTALL):
                comment = match.group().upper()
                for forbidden in self.FORBIDDEN_KEYWORDS:
                    if forbidden in comment:
                        return False, f"注释中包含禁止的操作: {forbidden}"

        return True, ""

    def add_limit(self, sql: str) -> str:
        """为 SELECT/WITH 查询添加 LIMIT 限制（元数据语句不加 LIMIT）"""
        if not self._is_query_statement(sql):
            return sql.rstrip(";")

        sql_upper = sql.upper()

        if "LIMIT" in sql_upper:
            return sql

        if "FETCH FIRST" in sql_upper or "TOP " in sql_upper:
            return sql

        return f"{sql.rstrip(';')} LIMIT {self.max_rows}"

    def sanitize(self, sql: str) -> Tuple[str, str]:
        """
        对 SQL 进行安全检查并添加限制
        返回: (处理后的 SQL, 错误信息)
        """
        is_valid, error = self.validate(sql)
        if not is_valid:
            return "", error

        safe_sql = self.add_limit(sql)
        return safe_sql, ""
