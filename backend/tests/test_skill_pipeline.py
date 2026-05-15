from fastapi import FastAPI
from fastapi.testclient import TestClient

from tars.api.invoke import init_invoke_api, router as invoke_router
from tars.models.base import ModelResponse
from tars.skills.loader import SkillLoader
from tars.skills.pipeline import PipelineLoader, SkillPipelineEngine, SkillPipelineRegistry
from tars.skills.registry import SkillRegistry
from tars.tenant.context import TenantContextCache
from tars.tools.registry import ToolRegistry


class FakePipelineProvider:
    def __init__(self):
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        system_prompt = messages[0].content if messages else ""
        user_prompt = messages[-1].content if messages else ""
        response_format = kwargs.get("response_format")
        if response_format:
            return ModelResponse(
                content='{"summary":"ok","score":0.9}',
                model="fake",
            )
        if "Summarizer" in system_prompt:
            return ModelResponse(content=f"SUM:{user_prompt}", model="fake")
        if "Translator" in system_prompt:
            return ModelResponse(content=f"TR:{user_prompt}", model="fake")
        return ModelResponse(content=user_prompt, model="fake")


class FakeMemoryManager:
    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id

    def for_tenant(self, tenant_id: str):
        return FakeMemoryManager(tenant_id=tenant_id)


def test_skill_loader_parses_extended_frontmatter(tmp_path):
    skill_dir = tmp_path / "skills" / "report_skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: report_skill
description: report skill
depends_on:
  - web_search
outputs:
  type: json
  schema:
    type: object
---

# Report Skill

Do report work.
""",
        encoding="utf-8",
    )

    registry = SkillRegistry()
    loader = SkillLoader(str(tmp_path / "skills"), tool_registry=ToolRegistry(), skill_registry=registry)
    skills = loader.load_all()

    assert len(skills) == 1
    assert skills[0].dependencies == ["web_search"]
    assert skills[0].output_config["type"] == "json"
    assert skills[0].output_config["schema"]["type"] == "object"


def test_pipeline_engine_executes_prompt_steps_in_order(tmp_path):
    skills_dir = tmp_path / "skills"
    pipelines_dir = tmp_path / "pipelines"
    (skills_dir / "summarizer").mkdir(parents=True)
    (skills_dir / "translator").mkdir(parents=True)
    pipelines_dir.mkdir(parents=True)

    (skills_dir / "summarizer" / "SKILL.md").write_text(
        """---
name: summarizer
description: summarizer
---

# Summarizer

Summarizer
""",
        encoding="utf-8",
    )
    (skills_dir / "translator" / "SKILL.md").write_text(
        """---
name: translator
description: translator
---

# Translator

Translator
""",
        encoding="utf-8",
    )
    (pipelines_dir / "report_analysis.yaml").write_text(
        """name: report_analysis
steps:
  - skill: summarizer
    input: "{message}"
    output_as: summary
  - skill: translator
    input: "EN:{summary}"
    output_as: final_report
""",
        encoding="utf-8",
    )

    skill_registry = SkillRegistry()
    tool_registry = ToolRegistry()
    SkillLoader(str(skills_dir), tool_registry=tool_registry, skill_registry=skill_registry).load_all()

    pipeline_registry = SkillPipelineRegistry()
    PipelineLoader(str(pipelines_dir), pipeline_registry).load_all()
    engine = SkillPipelineEngine(
        pipeline_registry=pipeline_registry,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
        provider=FakePipelineProvider(),
    )

    result = engine.execute_sync("report_analysis", {"message": "hello"})

    assert result["pipeline"] == "report_analysis"
    assert result["outputs"]["summary"] == "SUM:hello"
    assert result["outputs"]["final_report"] == "TR:EN:SUM:hello"
    assert result["final_output"] == "TR:EN:SUM:hello"


def test_invoke_api_runs_explicit_pipeline(tmp_path):
    skills_dir = tmp_path / "skills"
    pipelines_dir = tmp_path / "pipelines"
    (skills_dir / "summarizer").mkdir(parents=True)
    (skills_dir / "translator").mkdir(parents=True)
    pipelines_dir.mkdir(parents=True)

    (skills_dir / "summarizer" / "SKILL.md").write_text(
        """---
name: summarizer
description: summarizer
---

# Summarizer

Summarizer
""",
        encoding="utf-8",
    )
    (skills_dir / "translator" / "SKILL.md").write_text(
        """---
name: translator
description: translator
---

# Translator

Translator
""",
        encoding="utf-8",
    )
    (pipelines_dir / "report_analysis.yaml").write_text(
        """name: report_analysis
steps:
  - skill: summarizer
    input: "{message}"
    output_as: summary
  - skill: translator
    input: "EN:{summary}"
    output_as: final_report
""",
        encoding="utf-8",
    )

    skill_registry = SkillRegistry()
    tool_registry = ToolRegistry()
    SkillLoader(str(skills_dir), tool_registry=tool_registry, skill_registry=skill_registry).load_all()

    pipeline_registry = SkillPipelineRegistry()
    PipelineLoader(str(pipelines_dir), pipeline_registry).load_all()
    engine = SkillPipelineEngine(
        pipeline_registry=pipeline_registry,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
        provider=FakePipelineProvider(),
    )

    app = FastAPI()
    app.include_router(invoke_router)
    init_invoke_api(
        agent=None,
        tenant_cache=TenantContextCache(max_size=4),
        memory_manager=FakeMemoryManager(),
        pipeline_engine=engine,
    )

    client = TestClient(app)
    response = client.post(
        "/api/invoke",
        json={
            "message": "hello",
            "pipeline": "report_analysis",
            "stream": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "TR:EN:SUM:hello"
    assert data["pipeline"] == "report_analysis"
    assert data["pipeline_outputs"]["summary"] == "SUM:hello"


def test_pipeline_engine_passes_response_format_and_parses_json(tmp_path):
    skills_dir = tmp_path / "skills"
    pipelines_dir = tmp_path / "pipelines"
    (skills_dir / "report_skill").mkdir(parents=True)
    pipelines_dir.mkdir(parents=True)

    (skills_dir / "report_skill" / "SKILL.md").write_text(
        """---
name: report_skill
description: report skill
outputs:
  type: json
  schema:
    type: object
    properties:
      summary:
        type: string
      score:
        type: number
---

# Report Skill

Report Skill
""",
        encoding="utf-8",
    )
    (pipelines_dir / "report_structured.yaml").write_text(
        """name: report_structured
steps:
  - skill: report_skill
    input: "{message}"
    output_as: final_report
""",
        encoding="utf-8",
    )

    skill_registry = SkillRegistry()
    tool_registry = ToolRegistry()
    SkillLoader(str(skills_dir), tool_registry=tool_registry, skill_registry=skill_registry).load_all()

    pipeline_registry = SkillPipelineRegistry()
    PipelineLoader(str(pipelines_dir), pipeline_registry).load_all()
    provider = FakePipelineProvider()
    engine = SkillPipelineEngine(
        pipeline_registry=pipeline_registry,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
        provider=provider,
    )

    result = engine.execute_sync("report_structured", {"message": "hello"})

    assert result["outputs"]["final_report"] == {"summary": "ok", "score": 0.9}
    assert provider.calls[0]["kwargs"]["response_format"]["type"] == "json_schema"
    assert provider.calls[0]["kwargs"]["response_format"]["schema"]["type"] == "object"
