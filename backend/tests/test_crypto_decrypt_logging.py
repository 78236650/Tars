"""Regression: a corrupt/unrecoverable ciphertext must not flood ERROR logs.

Context (v5.0.5): the field-encryption secret for api_key was rotated without
keeping the old key, so 116 stored `enc::` tokens can never decrypt. Every row
hit logged one ERROR, so a single login (which scans all users) produced
hundreds of identical lines. The data is intentionally left untouched; the fix
is purely to stop the log flooding while preserving decrypt() semantics.
"""

import logging

import pytest

from tars.security import crypto
from tars.security.crypto import (
    DecryptionError,
    decrypt,
    decrypt_or_none,
    encrypt,
)


def _make_corrupt_token() -> str:
    """A value carrying the enc:: prefix that the current key cannot decrypt."""
    return crypto._TOKEN_PREFIX + "gAAAAABnotarealtoken_corrupt_value_=="


def test_roundtrip_still_works():
    token = encrypt("secret-value")
    assert decrypt(token) == "secret-value"


def test_plaintext_and_none_pass_through():
    assert decrypt(None) is None
    assert decrypt("legacy-plaintext") == "legacy-plaintext"


def test_corrupt_token_still_raises():
    with pytest.raises(DecryptionError):
        decrypt(_make_corrupt_token())


def test_decrypt_or_none_returns_none_on_corrupt():
    assert decrypt_or_none(_make_corrupt_token()) is None


def test_repeated_corrupt_decrypt_logs_error_only_once(caplog):
    """The core regression: scanning many bad rows must not flood the log.

    Production reality is many *distinct* corrupt ciphertexts (one per user,
    Fernet is non-deterministic), all failing for the same single root cause
    (the secret was rotated/lost). So distinct tokens must still collapse to a
    single ERROR, not one-per-row.
    """
    crypto._reset_decrypt_failure_log_state()  # fresh state for the assertion

    with caplog.at_level(logging.ERROR, logger="tars.crypto"):
        # 50 *distinct* corrupt tokens, like get_all_users() over 50 bad rows.
        for i in range(50):
            token = crypto._TOKEN_PREFIX + f"gAAAAABnotarealtoken_corrupt_{i}_=="
            assert decrypt_or_none(token) is None

    decrypt_errors = [
        r for r in caplog.records
        if r.name == "tars.crypto" and r.levelno == logging.ERROR
    ]
    assert len(decrypt_errors) == 1, (
        f"expected a single ERROR for the shared root cause, "
        f"got {len(decrypt_errors)}"
    )
