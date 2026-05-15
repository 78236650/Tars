"""SQL 安全校验层"""
import re
import sqlparse
from typing import List, Set, Tuple


class SQLSecurityChecker:
    """SQL 安全校验器：只允许只读查询"""

    ALLOWED_STATEMENTS: Set[str] = {"SELECT", "WITH"}
    FORBIDDEN_KEYWORDS: Set[str] = {
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
        "GRANT", "REVOKE", "CREATE", "EXEC", "EXECUTE", "MERGE",
        "REPLACE", "CALL", "LOAD", "COPY", "UNLOAD",
    }

    def __init__(self, max_rows: int = 1000, timeout_seconds: int = 30):
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds

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

        for stmt in parsed:
            # 获取第一个 token 的类型
            first_token = None
            for token in stmt.tokens:
                if not token.is_whitespace:
                    first_token = token
                    break

            if first_token is None:
                continue

            # 检查语句类型
            token_type = getattr(first_token, "ttype", None)
            token_value = str(first_token).upper()

            # 检查是否是允许的语句类型
            is_allowed = False
            for allowed in self.ALLOWED_STATEMENTS:
                if allowed in token_value:
                    is_allowed = True
                    break

            if not is_allowed and token_type is not None:
                # 再次检查关键字
                for allowed in self.ALLOWED_STATEMENTS:
                    if allowed in token_value:
                        is_allowed = True
                        break

            if not is_allowed:
                # 检查是否有禁止的关键字
                sql_upper = stripped.upper()
                for forbidden in self.FORBIDDEN_KEYWORDS:
                    # 使用正则匹配完整单词
                    pattern = r'\b' + forbidden + r'\b'
                    if re.search(pattern, sql_upper):
                        return False, f"SQL 包含禁止的操作: {forbidden}"

        # 3. 检查注释中的注入（如 /* ... */ 或 --）
        # 允许正常注释，但检查是否有可疑内容
        comment_patterns = [
            r'/\*.*?\*/',
            r'--.*?$',
        ]
        for pattern in comment_patterns:
            for match in re.finditer(pattern, stripped, re.MULTILINE | re.DOTALL):
                comment = match.group().upper()
                for forbidden in self.FORBIDDEN_KEYWORDS:
                    if forbidden in comment:
                        return False, f"注释中包含禁止的操作: {forbidden}"

        return True, ""

    def add_limit(self, sql: str) -> str:
        """为 SQL 添加 LIMIT 限制（如果尚未存在）"""
        sql_upper = sql.upper()

        # 检查是否已有 LIMIT
        if "LIMIT" in sql_upper:
            return sql

        # 检查是否已有 FETCH FIRST / TOP (SQL Server/Oracle 风格)
        if "FETCH FIRST" in sql_upper or "TOP " in sql_upper:
            return sql

        # 添加 LIMIT
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
