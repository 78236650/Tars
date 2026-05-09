"""skill.yaml → SKILL.md 迁移工具（v2.5）

用法：
    python scripts/migrate_skill_yaml_to_md.py <skill_dir>
    python scripts/migrate_skill_yaml_to_md.py --all  # 扫描 skills/ 下所有

只生成 SKILL.md，不删除原 skill.yaml（由人工复核后删除）。
"""
import sys
import yaml
from pathlib import Path


def build_description(data: dict) -> str:
    """把 description + trigger.keywords 合并为 pushy 风格的 SKILL.md description"""
    base = data.get("description", "").strip()
    trigger = data.get("trigger") or {}
    keywords = trigger.get("keywords") or []
    intents = trigger.get("intents") or []

    if not base:
        base = f"{data.get('name', data.get('id', 'unknown'))} 技能"

    hints = []
    if keywords:
        hints.append(f"用户提到 {', '.join(keywords[:5])} 等关键词时")
    if intents:
        hints.append(f"意图属于 {', '.join(intents)} 类时")

    if hints:
        return f"{base}。使用此技能当{'或'.join(hints)}。"
    return base


def migrate_one(skill_dir: Path) -> bool:
    yaml_path = skill_dir / "skill.yaml"
    md_path = skill_dir / "SKILL.md"

    if not yaml_path.exists():
        print(f"[skip] {skill_dir}: 无 skill.yaml")
        return False
    if md_path.exists():
        print(f"[skip] {skill_dir}: SKILL.md 已存在")
        return False

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    name = data.get("id") or data.get("name") or skill_dir.name
    description = build_description(data)

    frontmatter = {"name": name, "description": description}
    if data.get("permissions"):
        frontmatter["permissions"] = data["permissions"]
    if data.get("tars_version_min"):
        frontmatter["tars_version_min"] = data["tars_version_min"]
    if data.get("requires_packages"):
        frontmatter["requires_packages"] = data["requires_packages"]

    body_parts = [f"# {data.get('name', name)}", ""]
    if data.get("prompt_template"):
        body_parts.extend([data["prompt_template"].strip(), ""])
    elif data.get("usage"):
        body_parts.extend([data["usage"].strip(), ""])
    else:
        body_parts.append(description)

    content = "---\n" + yaml.dump(frontmatter, allow_unicode=True, sort_keys=False) + "---\n\n" + "\n".join(body_parts)

    md_path.write_text(content, encoding="utf-8")
    print(f"[ok] {skill_dir}: 生成 SKILL.md（人工复核后请删除 skill.yaml）")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    if sys.argv[1] == "--all":
        root = Path("skills")
        if not root.exists():
            print(f"目录不存在: {root}")
            return 1
        count = sum(1 for d in root.iterdir() if d.is_dir() and migrate_one(d))
        print(f"\n共迁移 {count} 个技能")
        return 0

    skill_dir = Path(sys.argv[1])
    return 0 if migrate_one(skill_dir) else 1


if __name__ == "__main__":
    sys.exit(main())
