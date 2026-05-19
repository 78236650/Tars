"""Validate external database URLs against SSRF."""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"mysql", "mysql+pymysql", "mysql+aiomysql", "postgresql", "postgresql+asyncpg", "sqlite", "mssql", "mssql+pyodbc"}
ALLOW_PRIVATE = os.environ.get("TARS_INSIGHT_ALLOW_PRIVATE_HOSTS", "").strip() in ("1", "true")


def validate_external_db_url(url: str, *, allowed_schemes: set[str] | None = None, allow_private: bool | None = None) -> None:
    """Raise ValueError if url is unsafe (SSRF risk)."""
    if allow_private is None:
        allow_private = ALLOW_PRIVATE
    if allowed_schemes is None:
        allowed_schemes = ALLOWED_SCHEMES

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in allowed_schemes:
        raise ValueError(f"Scheme {scheme!r} not in allowed list: {sorted(allowed_schemes)}")

    if scheme == "sqlite":
        return

    host = parsed.hostname
    if not host:
        raise ValueError("No host in URL")

    try:
        infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve host {host!r}: {e}")

    if not allow_private:
        for _family, _type, _proto, _canonname, sockaddr in infos:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(f"Host {host!r} resolves to private/reserved IP {ip}")
