"""SSRF validation for external DB URLs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from tars.utils.url_safety import validate_external_db_url


def test_valid_mysql_url():
    validate_external_db_url("mysql+pymysql://user:pass@localhost:3306/mydb", allow_private=True)


def test_valid_postgresql_url():
    validate_external_db_url("postgresql://user:pass@localhost/mydb", allow_private=True)


def test_sqlite_always_allowed():
    validate_external_db_url("sqlite:///path/to/db.sqlite")


def test_file_scheme_rejected():
    with pytest.raises(ValueError, match="Scheme"):
        validate_external_db_url("file:///etc/passwd")


def test_http_scheme_rejected():
    with pytest.raises(ValueError, match="Scheme"):
        validate_external_db_url("http://example.com/api")


def test_loopback_rejected():
    with pytest.raises(ValueError, match="private"):
        validate_external_db_url("mysql://user:pass@127.0.0.1/db", allow_private=False)


def test_link_local_rejected():
    with pytest.raises(ValueError, match="private"):
        validate_external_db_url("mysql://user:pass@169.254.169.254/db", allow_private=False)


def test_private_rfc1918_rejected():
    with pytest.raises(ValueError, match="private"):
        validate_external_db_url("mysql://user:pass@10.0.0.1/db", allow_private=False)


def test_private_allowed_when_flag_set():
    validate_external_db_url("mysql://user:pass@127.0.0.1/db", allow_private=True)


def test_no_host_rejected():
    with pytest.raises(ValueError, match="No host"):
        validate_external_db_url("mysql:///db")
