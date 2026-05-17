from tars.database import Database, UserStore
from tars.gateway.permission import UserRole


def test_create_user_stores_password_as_hash_not_plaintext():
    db = Database(":memory:")
    store = UserStore(db)

    user = store.create_user(
        "alice",
        "alice@example.com",
        role=UserRole.USER,
        password="S3cret!Pass",
    )

    cursor = db._get_conn().cursor()
    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,))
    row = cursor.fetchone()

    assert row is not None
    assert row[0] is not None
    assert row[0] != "S3cret!Pass"
    assert row[0].startswith("pbkdf2_sha256$")

    db.close()


def test_verify_password_accepts_correct_password_and_rejects_wrong_password():
    db = Database(":memory:")
    store = UserStore(db)

    user = store.create_user(
        "alice",
        "alice@example.com",
        role=UserRole.USER,
        password="S3cret!Pass",
    )

    assert store.verify_password(user.id, "S3cret!Pass") is True
    assert store.verify_password(user.id, "wrong-password") is False

    db.close()
