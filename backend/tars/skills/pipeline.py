import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from string import Formatter
from typing import Any, Dict, List, Optional

import yaml

from ..models.base import ChatMessage, ModelResponse
from ..tools.base import ToolResult
from ..tools.registry import ToolRegistry
from .base import Skill, SkillType
from .registry import SkillRegistry


@dataclass
class PipelineStep:
    skill: str
    input: Any = ""
    output_as: Optional[str] = None


@dataclass
class SkillPipeline:
    name: str
    steps: List[PipelineStep] = field(default_factory=list)


class SkillPipelineRegistry:
    def __init__(self):
        self._pipelines: Dict[str, SkillPipeline] = {}

    def register(self, pipeline: SkillPipeline) -> None:
        self._pipelines[pipeline.name] = pipeline

    def get(self, name: str) -> Optional[SkillPipeline]:
        return self._pipelines.get(name)

    def list_all(self) -> List[SkillPipeline]:
        return list(self._pipelines.values())


class PipelineLoader:
    def __init__(self, pipelines_dir: str, pipeline_registry: SkillPipelineRegistry):
        self.pipelines_dir = Path(pipelines_dir)
        self.pipeline_registry = pipeline_registry

    def load_all(self) -> List[SkillPipeline]:
        loaded: List[SkillPipeline] = []
        if not self.pipelines_dir.exists():
            return loaded

        for path in sorted(self.pipelines_dir.glob("*.yaml")):
            pipeline = self._load_file(path)
            if pipeline:
                self.pipeline_registry.register(pipeline)
                loaded.append(pipeline)
        return loaded

    def _load_file(self, path: Path) -> Optional[SkillPipeline]:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not data or "name" not in data:
            return None
        steps = [
            PipelineStep(
                skill=step["skill"],
                input=step.get("input", ""),
                output_as=step.get("output_as"),
            )
            for step in data.get("steps", [])
        ]
        return SkillPipeline(name=data["name"], steps=steps)


class SkillPipelineEngine:
    def __init__(
        self,
        pipeline_registry: SkillPipelineRegistry,
        skill_registry: SkillRegistry,
        tool_registry: ToolRegistry,
        provider=None,
    ):
        self.pipeline_registry = pipeline_registry
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry
        self.provider = provider

    def execute_sync(self, pipeline_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return asyncio.run(self.execute(pipeline_name, inputs))

    async def execute(self, pipeline_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        pipeline = self.pipeline_registry.get(pipeline_name)
        if not pipeline:
            raise ValueError(f"Pipeline '{pipeline_name}' 不存在")

        context: Dict[str, Any] = dict(inputs)
        outputs: Dict[str, Any] = {}
        last_output: Any = ""

        for step in pipeline.steps:
            skill = self.skill_registry.get(step.skill)
            if not skill:
                raise ValueError(f"Skill '{step.skill}' 不存在")

            rendered_input = self._render_value(step.input, context)
            result = await self._run_step(skill, rendered_input)
            output_key = step.output_as or step.skill
            outputs[output_key] = result
            context[output_key] = result
            last_output = result

        return {
            "pipeline": pipeline.name,
            "outputs": outputs,
            "final_output": last_output,
        }

    async def _run_step(self, skill: Skill, rendered_input: Any) -> Any:
        if skill.type == SkillType.PLUGIN:
            tool = self.tool_registry.get(skill.id) or self.tool_registry.get(skill.name)
            if not tool:
                raise ValueError(f"Pipeline skill '{skill.id}' 没有关联 tool")
            kwargs = self._normalize_tool_input(tool, rendered_input)
            tool_result: ToolResult = await tool.execute(**kwargs)
            if not tool_result.success:
                raise ValueError(tool_result.error or f"Skill '{skill.id}' 执行失败")
            return tool_result.output

        if self.provider is None:
            raise ValueError("Pipeline prompt skill 执行需要 provider")

        user_prompt = rendered_input if isinstance(rendered_input, str) else json.dumps(rendered_input, ensure_ascii=False)
        response_format = self._build_response_format(skill)
        response = await self.provider.chat(
            [
                ChatMessage(role="system", content=skill.prompt_template or ""),
                ChatMessage(role="user", content=user_prompt),
            ],
            stream=False,
            response_format=response_format,
        )
        content = self._extract_response_text(response)
        if response_format:
            return self._parse_structured_output(content)
        return content

    def _normalize_tool_input(self, tool, rendered_input: Any) -> Dict[str, Any]:
        if isinstance(rendered_input, dict):
            return rendered_input
        schema = getattr(tool, "parameters_schema", {}) or {}
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        if len(required) == 1:
            return {required[0]: rendered_input}
        if len(properties) == 1:
            key = next(iter(properties))
            return {key: rendered_input}
        raise ValueError(f"Tool '{tool.name}' 需要对象输入")

    def _render_value(self, value: Any, context: Dict[str, Any]) -> Any:
        if isinstance(value, str):
            return self._render_string(value, context)
        if isinstance(value, dict):
            return {k: self._render_value(v, context) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render_value(item, context) for item in value]
        return value

    def _render_string(self, template: str, context: Dict[str, Any]) -> str:
        formatter = Formatter()
        rendered = template
        for _, field_name, _, _ in formatter.parse(template):
            if not field_name:
                continue
            replacement = context.get(field_name, "")
            if not isinstance(replacement, str):
                replacement = json.dumps(replacement, ensure_ascii=False)
            rendered = rendered.replace("{" + field_name + "}", replacement)
        return rendered

    def _build_response_format(self, skill: Skill) -> Optional[Dict[str, Any]]:
        output_config = getattr(skill, "output_config", {}) or {}
        schema = output_config.get("schema")
        if not schema:
            return None
        return {
            "type": "json_schema",
            "schema": schema,
        }

    def _extract_response_text(self, response: Any) -> str:
        if isinstance(response, ModelResponse):
            return response.content
        if isinstance(response, dict):
            if "content" in response:
                return response["content"]
            return response.get("message", {}).get("content", "")
        return str(response)

    def _parse_structured_output(self, content: str) -> Any:
        if not content:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        fenced = self._extract_fenced_json(content)
        if fenced is not None:
            return fenced
        return content

    def _extract_fenced_json(self, content: str) -> Optional[Any]:
        marker = "```json"
        start = content.find(marker)
        if start == -1:
            return None
        start = content.find("\n", start)
        end = content.rfind("```")
        if start == -1 or end == -1 or end <= start:
            return None
        block = content[start:end].strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            return None
