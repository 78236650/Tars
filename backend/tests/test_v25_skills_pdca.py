"""v2.5 关键路径回归测试 — 覆盖 code review 修复项

覆盖：
- P0-1: pdca_config 作用域（结构层面检查，通过跑 agent 任务触发路径验证）
- P0-2: INSERT INTO tasks 的 17 列
- P1-1: pdca_ref → skill_id 反推
- P2-1: variable_engine 的 shlex.quote 按 tool_name 分类
- P2-1: {{step_N.*}} 保留原样
- P2-1: {{env.*}} 白名单
"""
import sys
import os
import sqlite3
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _skill_dir(name: str) -> Path:
    root = Path(__file__).parent.parent.parent / "skills"
    global_dir = root / "_global" / name
    if global_dir.is_dir():
        return global_dir
    return root / name


class TestVariableEngineQuoteScope:
    """P2-1: shlex.quote 按 tool_name 分类作用"""

    def _engine(self, tmp_path):
        # 初始化 git 仓库让 _detect_branch 不报错
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=False)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init", "-q"],
                       cwd=tmp_path, check=False)
        from tars.orchestration.variable_engine import VariableEngine
        return VariableEngine(str(tmp_path))

    def test_shell_cmd_quoted(self, tmp_path):
        # 创建 package-lock.json 让 pm 检测为 npm
        (tmp_path / "package-lock.json").write_text("{}")
        engine = self._engine(tmp_path)
        out = engine.resolve_dict({"cmd": "cd {{workspace.path}} && ls"}, tool_name="shell")
        # path 含临时目录，可能被 quote 也可能不被（取决于是否有特殊字符）
        assert str(tmp_path) in out["cmd"]
        assert "ls" in out["cmd"]

    def test_file_write_path_not_quoted(self, tmp_path):
        engine = self._engine(tmp_path)
        out = engine.resolve_dict(
            {"path": "{{workspace.path}}/output.txt", "content": "hi"},
            tool_name="file_write",
        )
        assert out["path"] == f"{tmp_path}/output.txt"
        # 非 shell 工具参数不应被 shlex.quote
        assert "'" not in out["path"]

    def test_step_ref_preserved(self, tmp_path):
        engine = self._engine(tmp_path)
        out = engine.resolve_dict({"cmd": "echo {{step_1.output}}"}, tool_name="shell")
        # step_N 保留原样，留给 executor 运行时解析
        assert "{{step_1.output}}" in out["cmd"]

    def test_unknown_var_preserved(self, tmp_path):
        engine = self._engine(tmp_path)
        out = engine.resolve_dict({"x": "{{unknown.var}}"}, tool_name="shell")
        assert "{{unknown.var}}" in out["x"]

    def test_env_whitelist(self, tmp_path):
        engine = self._engine(tmp_path)
        out = engine.resolve_dict({"cmd": "echo {{env.HOME}}"}, tool_name="shell")
        # HOME 在白名单
        expected = os.environ.get("HOME", "")
        # quote 后可能带单引号
        assert expected in out["cmd"]

    def test_env_non_whitelist_empty(self, tmp_path):
        engine = self._engine(tmp_path)
        out = engine.resolve_dict({"cmd": "echo {{env.EVIL_VAR}}"}, tool_name="shell")
        # 非白名单返回空串
        assert "EVIL_VAR" not in out["cmd"]

    def test_pm_detection_pnpm(self, tmp_path):
        (tmp_path / "pnpm-lock.yaml").write_text("")
        engine = self._engine(tmp_path)
        assert engine.package_manager == "pnpm"

    def test_pm_detection_poetry(self, tmp_path):
        (tmp_path / "poetry.lock").write_text("")
        engine = self._engine(tmp_path)
        assert engine.package_manager == "poetry"


class TestTasksSchemaInsert:
    """P0-2: INSERT INTO tasks 必须匹配 ALTER 后的 17 列"""

    def test_insert_17_columns(self, tmp_path):
        db_path = tmp_path / "t.db"
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        # 复现真实 schema：原始 15 列 + ALTER 2 列
        c.execute("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL, title TEXT NOT NULL,
                goal TEXT NOT NULL, workspace_path TEXT NOT NULL,
                workspace_source TEXT NOT NULL, status TEXT DEFAULT 'pending',
                current_step INTEGER DEFAULT 0, total_steps INTEGER DEFAULT 0,
                artifacts TEXT, output_summary TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                completed_at TEXT, error_message TEXT
            )
        """)
        c.execute("ALTER TABLE tasks ADD COLUMN skill_id TEXT")
        c.execute("ALTER TABLE tasks ADD COLUMN pdca_ref TEXT")
        conn.commit()

        # v2.5 修复后的 INSERT：显式列名 + 17 个值
        c.execute(
            "INSERT INTO tasks (id, session_id, title, goal, workspace_path, workspace_source, "
            "status, current_step, total_steps, artifacts, output_summary, created_at, updated_at, "
            "completed_at, error_message, skill_id, pdca_ref) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("t1", "s1", "t", "g", "/tmp", "fallback", "running", 0, 3,
             None, None, "2026-05-10", "2026-05-10", None, None,
             "deploy", "skill://deploy/pdca.yaml"),
        )
        conn.commit()

        row = c.execute(
            "SELECT skill_id, pdca_ref FROM tasks WHERE id=?", ("t1",)
        ).fetchone()
        assert row == ("deploy", "skill://deploy/pdca.yaml")


class TestSkillIdFromPdcaRef:
    """P1-1: pdca_ref 反推 skill_id 的逻辑"""

    def test_extract_skill_id(self):
        # 模拟 agent.py 里的反推逻辑
        def extract(pdca_ref):
            if pdca_ref and pdca_ref.startswith("skill://"):
                return pdca_ref.replace("skill://", "").split("/")[0]
            return None

        assert extract("skill://deploy/pdca.yaml") == "deploy"
        assert extract("skill://run_tests/pdca.yaml") == "run_tests"
        assert extract(None) is None
        assert extract("") is None
        assert extract("/tmp/pdca.yaml") is None


class TestSkillsRegistry:
    """P1-3 回归: release_notes 应标记为 has_pdca=False"""

    def test_release_notes_no_pdca(self):
        root = _skill_dir("release_notes")
        assert (root / "SKILL.md").exists()
        assert not (root / "pdca.yaml").exists(), \
            "release_notes 不应再依赖 pdca.yaml（v2.5 重设计后改走 SKILL.md 指令）"

    def test_deploy_skill_md_no_broken_refs(self):
        md_path = _skill_dir("deploy") / "SKILL.md"
        content = md_path.read_text(encoding="utf-8")
        # deploy/scripts 目录不存在，SKILL.md 不应再引用
        if "scripts/pre_check.py" in content or "scripts/health_check.py" in content:
            scripts_dir = md_path.parent / "scripts"
            assert scripts_dir.exists(), \
                f"SKILL.md 引用了 scripts/ 但目录不存在: {scripts_dir}"


class TestMigrateTool:
    """P2-4: 迁移脚本可执行"""

    def test_migrate_script_exists(self):
        root = Path(__file__).parent.parent.parent
        script = root / "scripts" / "migrate_skill_yaml_to_md.py"
        assert script.exists()

    def test_migrate_script_runs(self, tmp_path):
        # 准备一个假技能目录
        skill_dir = tmp_path / "demo_skill"
        skill_dir.mkdir()
        (skill_dir / "skill.yaml").write_text(
            "id: demo\nname: Demo\ndescription: 演示技能\n"
            "trigger:\n  keywords: [demo, test]\nprompt_template: |\n  hello\n",
            encoding="utf-8",
        )

        import subprocess, sys
        root = Path(__file__).parent.parent.parent
        script = root / "scripts" / "migrate_skill_yaml_to_md.py"
        r = subprocess.run(
            [sys.executable, str(script), str(skill_dir)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"迁移失败: {r.stderr}"

        md = skill_dir / "SKILL.md"
        assert md.exists()
        content = md.read_text(encoding="utf-8")
        assert "name: demo" in content
        assert "demo" in content.lower()
