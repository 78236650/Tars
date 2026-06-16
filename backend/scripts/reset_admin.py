#!/usr/bin/env python3
"""Reset default admin credentials (for lockout recovery).

Usage:
  .venv/bin/python scripts/reset_admin.py              # reset password + regen API key
  .venv/bin/python scripts/reset_admin.py --regenerate  # also regenerate API key
"""
import argparse
import os
import sys
from pathlib import Path

# Load .env before any TARS imports so crypto picks up stable keys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
_dotenv_path = Path(__file__).resolve().parent.parent / ".env"
if _dotenv_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path)

from tars.database import Database, UserStore
from tars.gateway.permission import UserRole
from tars.security.crypto import encrypt, lookup_hash

DEFAULT_EMAIL = "admin@tars.local"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "Admin123!"


def main():
    parser = argparse.ArgumentParser(description="Reset TARS admin account")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--regenerate", action="store_true",
                        help="Regenerate API key (fix key broken by encryption secret change)")
    parser.add_argument("--db", default=None, help="Path to tars.db (default: backend/data/tars.db)")
    args = parser.parse_args()

    db_path = args.db
    if not db_path:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        db_path = os.path.join(data_dir, "tars.db")

    if not os.path.exists(db_path):
        print(f"Error: database not found at {db_path}")
        sys.exit(1)

    db = Database(db_path=db_path)
    store = UserStore(db)
    user = store.get_user_by_email(args.email) or next(
        (u for u in store.get_all_users() if u.username == DEFAULT_USERNAME),
        None,
    )

    update_kwargs = {
        "role": UserRole.ADMIN,
        "password_hash": store._hash_password(args.password),
    }

    if not user:
        user = store.create_user(
            DEFAULT_USERNAME, args.email,
            UserRole.ADMIN, password=args.password,
        )
        print(f"[OK] Created admin: {args.email}")
    else:
        # Check if API key is broken (None when it should be set)
        if user.api_key is None or args.regenerate:
            new_key = store._generate_api_key()
            encrypted_key = encrypt(new_key)
            key_hash = lookup_hash(new_key)
            store.update_user(user.id, api_key=encrypted_key, api_key_hash=key_hash, **update_kwargs)
            print(f"[OK] Reset admin + regenerated API key: {user.email} (role=admin)")
            print(f"  New API key: {new_key}")
        else:
            store.update_user(user.id, **update_kwargs)
            print(f"[OK] Reset admin password: {user.email} (role=admin)")

    print(f"Login: {args.email} / {args.password}")
    db.close()


if __name__ == "__main__":
    main()
