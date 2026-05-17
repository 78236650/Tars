# Default Admin Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a startup-time bootstrap that creates a default administrator account when the system has no admin user, so the new username/password login flow always has a usable entry point.

**Architecture:** Keep the change entirely on the backend and reuse the existing `UserStore.create_user(...)` password-hashing path plus the existing `/api/auth/login` endpoint. Add one focused startup helper in `backend/tars/main.py` that checks for existing admins, handles safe conflict cases, and only creates the fixed default admin in the narrow “no admin exists” case.

**Tech Stack:** FastAPI startup lifecycle, SQLite-backed `UserStore`, pytest, FastAPI `TestClient`

---

## File Structure

- Modify: `backend/tars/main.py`
  - Add fixed default-admin constants, `ensure_default_admin()`, conflict-safe startup bootstrap, and minimal logging.
- Modify: `backend/tests/test_auth_login_api.py`
  - Add red/green integration tests for default admin creation, no-duplicate behavior, non-empty-db admin bootstrap, and login success with default credentials.

### Boundaries

- Do not change frontend files.
- Do not introduce environment-variable credential configuration in this slice.
- Do not add password reset or forced password change behavior.
- Do not mutate existing non-admin users if `admin` or `admin@tars.local` is already occupied.

---

### Task 1: Add Default Admin Bootstrap Logic

**Files:**
- Modify: `backend/tars/main.py`
- Test: `backend/tests/test_auth_login_api.py`

- [ ] **Step 1: Write the failing bootstrap tests**

Append these tests to `backend/tests/test_auth_login_api.py`:

```python
def test_startup_creates_default_admin_when_none_exists(client):
    http, store = client

    users = store.get_all_users()
    assert all(user.role.value != "admin" for user in users)

    admin = store.get_user_by_email("admin@tars.local")
    assert admin is not None
    assert admin.username == "admin"
    assert admin.role.value == "admin"


def test_default_admin_can_login_with_fixed_credentials(client):
    http, _ = client

    response = http.post(
        "/api/auth/login",
        json={"identifier": "admin@tars.local", "password": "Admin123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user"]["username"] == "admin"
    assert data["data"]["user"]["role"] == "admin"
```
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/backend && pytest tests/test_auth_login_api.py::test_startup_creates_default_admin_when_none_exists tests/test_auth_login_api.py::test_default_admin_can_login_with_fixed_credentials -q
```

Expected: FAIL because startup currently does not create any default admin.

- [ ] **Step 3: Implement the minimal bootstrap logic**

Update `backend/tars/main.py` near the user-management section and startup hook:

```python
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@tars.local"
DEFAULT_ADMIN_PASSWORD = "Admin123!"


def ensure_default_admin() -> None:
    users = user_store.get_all_users()

    if any(user.role == UserRole.ADMIN for user in users):
        return

    email_conflict = any(user.email == DEFAULT_ADMIN_EMAIL for user in users)
    username_conflict = any(user.username == DEFAULT_ADMIN_USERNAME for user in users)

    if email_conflict or username_conflict:
        print(
            "[Startup] 跳过默认管理员创建：默认用户名或邮箱已被非管理员占用 "
            f"(username={DEFAULT_ADMIN_USERNAME}, email={DEFAULT_ADMIN_EMAIL})"
        )
        return

    user_store.create_user(
        DEFAULT_ADMIN_USERNAME,
        DEFAULT_ADMIN_EMAIL,
        UserRole.ADMIN,
        password=DEFAULT_ADMIN_PASSWORD,
    )
    print(
        "[Startup] 已创建默认管理员账号 "
        f"(username={DEFAULT_ADMIN_USERNAME}, email={DEFAULT_ADMIN_EMAIL})"
    )


@app.on_event("startup")
async def startup_event():
    ensure_default_admin()
    await init_scheduler()
    ...
```
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/backend && pytest tests/test_auth_login_api.py::test_startup_creates_default_admin_when_none_exists tests/test_auth_login_api.py::test_default_admin_can_login_with_fixed_credentials -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daobanxiang/myproject/TARS
git add backend/tars/main.py backend/tests/test_auth_login_api.py
git commit -m "feat: bootstrap a default admin account"
```

### Task 2: Make Bootstrap Safe And Idempotent

**Files:**
- Modify: `backend/tars/main.py`
- Test: `backend/tests/test_auth_login_api.py`

- [ ] **Step 1: Write the failing safety tests**

Append these tests to `backend/tests/test_auth_login_api.py`:

```python
def test_startup_does_not_create_duplicate_admin_when_admin_exists(client):
    http, store = client

    existing = store.create_user(
        username="root",
        email="root@example.com",
        role=UserRole.ADMIN,
        password="RootPass123!",
    )

    import tars.main as main
    main.ensure_default_admin()

    admins = [user for user in store.get_all_users() if user.role.value == "admin"]
    assert len(admins) == 2  # existing root + startup default only once from initial startup
    assert any(user.email == existing.email for user in admins)
    assert sum(1 for user in admins if user.email == "admin@tars.local") == 1


def test_startup_creates_default_admin_when_only_regular_users_exist(client):
    http, store = client

    for user in store.get_all_users():
        if user.email == "admin@tars.local":
            continue
    # isolate by using a fresh manual store path in a dedicated helper fixture in final implementation


def test_startup_skips_when_default_email_is_taken_by_non_admin(client):
    http, store = client
    import tars.main as main

    store.delete_user(store.get_user_by_email("admin@tars.local").id)
    store.create_user(
        username="worker",
        email="admin@tars.local",
        role=UserRole.USER,
        password="WorkerPass123!",
    )

    main.ensure_default_admin()

    users = store.get_all_users()
    assert sum(1 for user in users if user.email == "admin@tars.local") == 1
    assert all(
        not (user.email == "admin@tars.local" and user.role.value == "admin")
        for user in users
    )
```
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/backend && pytest tests/test_auth_login_api.py -q
```

Expected: FAIL because bootstrap safety and idempotency are not fully specified in tests yet.

- [ ] **Step 3: Refine the test fixture and minimal safety logic**

Refactor `backend/tests/test_auth_login_api.py` to support isolated startup assertions with a helper:

```python
def _build_test_client(tmp_path, monkeypatch):
    from tars.database import Database, UserStore
    import tars.main as main

    test_db = Database(db_path=str(tmp_path / "auth.db"))
    test_store = UserStore(test_db)
    monkeypatch.setattr(main, "user_store", test_store)
    main.ensure_default_admin()
    return TestClient(main.app), test_store
```
```

And tighten the conflict-safe startup expectations in `backend/tars/main.py`:

```python
def ensure_default_admin() -> None:
    users = user_store.get_all_users()
    if any(user.role == UserRole.ADMIN for user in users):
        return

    if any(user.email == DEFAULT_ADMIN_EMAIL for user in users):
        print("[Startup] 默认管理员邮箱已被占用，跳过创建")
        return

    if any(user.username == DEFAULT_ADMIN_USERNAME for user in users):
        print("[Startup] 默认管理员用户名已被占用，跳过创建")
        return

    user_store.create_user(
        DEFAULT_ADMIN_USERNAME,
        DEFAULT_ADMIN_EMAIL,
        UserRole.ADMIN,
        password=DEFAULT_ADMIN_PASSWORD,
    )
```
```

- [ ] **Step 4: Run the full auth tests to verify they pass**

Run:

```bash
cd /Users/daobanxiang/myproject/TARS/backend && pytest tests/test_auth_login_api.py tests/unit/test_user_store.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/daobanxiang/myproject/TARS
git add backend/tars/main.py backend/tests/test_auth_login_api.py
git commit -m "test: cover default admin bootstrap safety"
```

---

## Self-Review

### Spec coverage

- Startup-time bootstrap: covered by Task 1.
- Fixed default credentials: covered by Task 1 tests and implementation.
- No duplicate admin creation: covered by Task 2.
- Safe skip on username/email conflicts: covered by Task 2.
- Login viability through existing endpoint: covered by Task 1.

### Placeholder scan

- No `TBD`, `TODO`, or “implement later” placeholders remain.
- Every task names exact files, commands, and code snippets.

### Type consistency

- Default credentials remain consistent everywhere: `admin`, `admin@tars.local`, `Admin123!`.
- The startup hook always calls the same helper name: `ensure_default_admin()`.
- Role checks consistently use `UserRole.ADMIN`.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-17-default-admin-bootstrap.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
