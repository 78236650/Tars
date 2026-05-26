from pathlib import Path
from typing import Optional


class WikiStore:
    def __init__(self, wiki_dir: Path):
        self.wiki_dir = Path(wiki_dir)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.wiki_dir / "index.md"
        if not index_path.exists():
            index_path.write_text("# Wiki Index\n\n", encoding="utf-8")

    def read_page(self, page_name: str) -> Optional[str]:
        path = self.wiki_dir / f"{page_name}.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_page(self, page_name: str, content: str) -> None:
        path = self.wiki_dir / f"{page_name}.md"
        path.write_text(content, encoding="utf-8")

    def delete_page(self, page_name: str) -> None:
        path = self.wiki_dir / f"{page_name}.md"
        if path.exists():
            path.unlink()

    def list_pages(self) -> list[str]:
        return [
            p.stem for p in self.wiki_dir.glob("*.md")
            if p.stem != "index"
        ]

    def read_index(self) -> str:
        return (self.wiki_dir / "index.md").read_text(encoding="utf-8")

    def update_index(self, summaries: dict[str, str]) -> None:
        lines = ["# Wiki Index\n"]
        for page_name, summary in sorted(summaries.items()):
            lines.append(f"- **[{page_name}]({page_name}.md)** — {summary}")
        (self.wiki_dir / "index.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
