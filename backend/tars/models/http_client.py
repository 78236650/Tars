"""共享的 LLM HTTP 客户端超时配置。

流式/长推理时两次 token 之间间隔可能很长，过短的 read 超时会导致 ReadTimeout 并表现为「模型断连」。
可通过环境变量调整：TARS_LLM_READ_TIMEOUT（默认 600）、TARS_LLM_CONNECT_TIMEOUT（默认 30）。
"""
import os

import httpx


def llm_async_client() -> httpx.AsyncClient:
    read_s = float(os.getenv("TARS_LLM_READ_TIMEOUT", "600"))
    connect_s = float(os.getenv("TARS_LLM_CONNECT_TIMEOUT", "30"))
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=connect_s,
            read=read_s,
            write=120.0,
            pool=30.0,
        )
    )
