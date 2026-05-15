"""SQL Agent：生成 + 执行 + 自我修正"""
import json
import traceback
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .security import SQLSecurityChecker


class SQLAgent:
    """SQL 执行 Agent（只读）"""

    def __init__(self, connection_url: str, max_retries: int = 3):
        self.connection_url = connection_url
        self.max_retries = max_retries
        self.security = SQLSecurityChecker(max_rows=1000, timeout_seconds=30)
        self._engine: Optional[Engine] = None

    def _get_engine(self) -> Engine:
        if self._engine is None:
            kwargs = {"pool_pre_ping": True}
            if self.connection_url.startswith("sqlite"):
                kwargs["connect_args"] = {"check_same_thread": False}
            else:
                kwargs["connect_args"] = {"connect_timeout": 10}
                kwargs["execution_options"] = {"isolation_level": "READ COMMITTED"}
            self._engine = create_engine(self.connection_url, **kwargs)
        return self._engine

    def execute(self, sql: str) -> Dict[str, Any]:
        """
        执行 SQL 查询（带安全校验）
        返回: {
            "success": bool,
            "data": List[Dict],
            "columns": List[str],
            "row_count": int,
            "error": str,
            "sql": str
        }
        """
        safe_sql, error = self.security.sanitize(sql)
        if not safe_sql:
            return {
                "success": False,
                "data": [],
                "columns": [],
                "row_count": 0,
                "error": error,
                "sql": sql,
            }

        engine = self._get_engine()
        try:
            with engine.connect() as conn:
                result = conn.execute(text(safe_sql))
                columns = list(result.keys())
                rows = []
                for row in result:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        val = row[i]
                        if val is not None:
                            try:
                                json.dumps(val)
                                row_dict[col] = val
                            except (TypeError, ValueError):
                                row_dict[col] = str(val)
                        else:
                            row_dict[col] = None
                    rows.append(row_dict)
                    if len(rows) >= self.security.max_rows:
                        break

                return {
                    "success": True,
                    "data": rows,
                    "columns": columns,
                    "row_count": len(rows),
                    "error": None,
                    "sql": safe_sql,
                }
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "columns": [],
                "row_count": 0,
                "error": f"{type(e).__name__}: {e}",
                "sql": safe_sql,
            }

    async def execute_with_retry(
        self,
        sql: str,
        llm_provider=None,
        schema_context: str = "",
        user_question: str = "",
    ) -> Dict[str, Any]:
        """
        执行 SQL，失败时通过 LLM 自我修正（最多重试 max_retries 次）
        """
        result = self.execute(sql)
        if result["success"]:
            return result

        if llm_provider is None:
            return result

        current_sql = sql
        for attempt in range(self.max_retries):
            fix_prompt = self._build_fix_prompt(
                user_question=user_question,
                schema_context=schema_context,
                failed_sql=current_sql,
                error=result["error"],
            )
            try:
                fixed_sql = await self._call_llm_for_sql(llm_provider, fix_prompt)
                if fixed_sql and fixed_sql != current_sql:
                    current_sql = fixed_sql
                    result = self.execute(current_sql)
                    if result["success"]:
                        return result
            except Exception as e:
                traceback.print_exc()
                continue

        return result

    def _build_fix_prompt(
        self,
        user_question: str,
        schema_context: str,
        failed_sql: str,
        error: str,
    ) -> str:
        return f"""你是一位 SQL 专家。之前的 SQL 查询执行失败，请修正它。

用户问题：{user_question}

数据库 Schema：
{schema_context}

执行失败的 SQL：
```sql
{failed_sql}
```

错误信息：
{error}

请只返回修正后的 SQL 语句，不要包含任何解释。确保 SQL 是安全的只读查询（SELECT/WITH）。"""

    async def _call_llm_for_sql(self, llm_provider, prompt: str) -> str:
        """调用 LLM 获取 SQL"""
        from ..models.base import ChatMessage
        msg = ChatMessage(role="user", content=prompt)
        response = await llm_provider.chat([msg])
        content = response.content if hasattr(response, "content") else str(response)
        sql = content.strip()
        if sql.startswith("```sql"):
            sql = sql[6:]
        if sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        return sql.strip()

    def close(self):
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
