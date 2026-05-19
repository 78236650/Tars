#!/usr/bin/env python3
"""Reset default admin credentials (for lockout recovery)."""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tars.database import Database, UserStore
from tars.gateway.permission import UserRole

DEFAULT_EMAIL = "admin@tars.local"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "Admin123!"


def main():
    parser = argparse.ArgumentParser(description="Reset TARS admin account")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--db", default=None, help="Path to tars.db (default: backend/data/tars.db)")
    args = parser.parse_args()

    db_path = args.db
    if not db_path:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        db_path = os.path.join(data_dir, "tars.db")

    db = Database(db_path=db_path)
    store = UserStore(db)
    user = store.get_user_by_email(args.email) or next(
        (u for u in store.get_all_users() if u.username == DEFAULT_USERNAME),
        None,
    )
    if not user:
        user = store.create_user(DEFAULT_USERNAME, args.email, UserRole.ADMIN, password=args.password)
        print(f"Created admin: {args.email}")
    else:
        store.update_user(
            user.id,
            role=UserRole.ADMIN,
            password_hash=store._hash_password(args.password),
        )
        print(f"Reset admin: {user.email} (role=admin)")
    print(f"Login with: {args.email} / {args.password}")
    db.close()


if __name__ == "__main__":
    main()
