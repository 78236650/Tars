"""v4.0.1 多租户 workspace 隔离测试"""
import pytest
import tempfile
from pathlib import Path
from tars.tools.tenant_workspace import TenantWorkspaceManager


@pytest.fixture
def manager(tmp_path):
    return TenantWorkspaceManager(base_dir=str(tmp_path / "workspaces"))


class TestTenantWorkspaceManager:
    def test_creates_base_dir(self, tmp_path):
        base = tmp_path / "ws"
        TenantWorkspaceManager(base_dir=str(base))
        assert base.exists()
        assert (base / "_shared").exists()

    def test_get_workspace_creates_dir(self, manager):
        ws = manager.get_workspace("user1")
        assert ws.exists()
        assert ws.name == "files"
        assert ws.parent.name == "user1"

    def test_get_tmp_dir(self, manager):
        tmp = manager.get_tmp_dir("user1")
        assert tmp.exists()
        assert tmp.name == "tmp"

    def test_different_tenants_different_dirs(self, manager):
        ws1 = manager.get_workspace("user1")
        ws2 = manager.get_workspace("user2")
        assert ws1 != ws2
        assert "user1" in str(ws1)
        assert "user2" in str(ws2)

    def test_sandbox_restricts_to_tenant(self, manager):
        sandbox = manager.get_sandbox("user1")
        # 可以解析 tenant 内的路径
        resolved = sandbox.resolve("test.txt")
        assert "user1/files" in str(resolved)
        # 不能逃逸
        with pytest.raises(PermissionError):
            sandbox.resolve("../../user2/files/secret.txt")

    def test_allowed_dirs_user(self, manager):
        dirs = manager.get_allowed_dirs("user1", role="user")
        assert len(dirs) == 2
        assert any("user1/files" in d for d in dirs)
        assert any("_shared" in d for d in dirs)

    def test_allowed_dirs_admin(self, manager):
        dirs = manager.get_allowed_dirs("user1", role="admin")
        assert len(dirs) == 3  # workspace + _shared + base

    def test_invalid_tenant_id_rejected(self, manager):
        with pytest.raises(ValueError):
            manager.get_workspace("../escape")
        with pytest.raises(ValueError):
            manager.get_workspace("user/sub")
        with pytest.raises(ValueError):
            manager.get_workspace("")

    def test_cross_tenant_file_isolation(self, manager):
        ws1 = manager.get_workspace("user1")
        ws2 = manager.get_workspace("user2")
        # user1 写文件
        (ws1 / "private.txt").write_text("secret")
        # user2 的 sandbox 无法访问 user1 的文件
        sandbox2 = manager.get_sandbox("user2")
        with pytest.raises(PermissionError):
            sandbox2.resolve(str(ws1 / "private.txt"))
